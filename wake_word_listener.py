import os
import time
import tempfile
import threading
from collections import deque
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from ai_engine import transcribir_audio

class BackgroundWakeListener:
    """
    Escucha activa continua ultra-sensible a 44100Hz nativos con:
    1. Piso de ruido ambiental adaptativo (EMA) para no saturarse con ruido de sala/PC.
    2. Buffer circular pre-roll de 370ms para no cortar la consonante inicial 'B-'.
    3. Detección VAD rápida (0.65-0.70s de pausa) para respuesta inmediata.
    4. Perro guardián (Watchdog) auto-recuperable para no congelarse tras horas de uso.
    """
    def __init__(self, callback_comando, samplerate=44100):
        self.callback_comando = callback_comando
        self.samplerate = samplerate
        self.activo = False
        self.en_proceso = False
        self.tiempo_inicio_proceso = 0.0
        self.stream = None
        self.acumulador_voz = []
        self.hablando = False
        self.silencio_frames = 0
        self.pre_roll = deque(maxlen=4)  # ~370ms de pre-grabación
        self.ambient_floor = 8.0         # Nivel de ruido base adaptativo
        self._lock = threading.Lock()
        self._hilo_watchdog = None

    def iniciar(self):
        with self._lock:
            if not self.activo:
                self.activo = True
                self._iniciar_stream()
                if not self._hilo_watchdog or not self._hilo_watchdog.is_alive():
                    self._hilo_watchdog = threading.Thread(target=self._watchdog_loop, daemon=True)
                    self._hilo_watchdog.start()

    def _iniciar_stream(self):
        try:
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
            self.stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                dtype='int16',
                blocksize=4096,
                callback=self._audio_callback
            )
            self.stream.start()
            print("[VOICE LISTENER] Escucha activa continua iniciada a 44100Hz nativos (Di 'Bimo').")
        except Exception as e:
            print(f"[VOICE LISTENER] Error al inicializar InputStream de audio: {e}")

    def detener(self):
        with self._lock:
            self.activo = False
            self.pausado = True
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.en_proceso = False
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

    def pausar(self):
        """Pausa temporalmente el procesamiento de audio y vacía buffers de inmediato."""
        with self._lock:
            self.pausado = True
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self.en_proceso = False

    def reanudar(self):
        """Reanuda la escucha activa con buffers limpios."""
        with self._lock:
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self.en_proceso = False
            self.pausado = False

    def _audio_callback(self, indata, frames, time_info, status):
        if not self.activo or getattr(self, "pausado", False):
            return
        
        # FILTRO ANTI-RETROALIMENTACIÓN ACÚSTICA: Si Bimo está hablando por el altavoz, descartar audio entrante
        from voice_assistant import bimo_esta_hablando
        if bimo_esta_hablando():
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            return

        datos = indata.flatten()
        vol = float(np.abs(datos).mean())
        self.pre_roll.append(datos)

        if self.en_proceso:
            return

        if not self.hablando:
            # Calibración adaptativa en reposo
            self.ambient_floor = 0.95 * self.ambient_floor + 0.05 * vol
            umbral_inicio = max(18.0, self.ambient_floor * 2.0)

            if vol > umbral_inicio:
                self.hablando = True
                self.silencio_frames = 0
                self.acumulador_voz = list(self.pre_roll)
                self.acumulador_voz.append(datos)
        else:
            self.acumulador_voz.append(datos)
            umbral_silencio = max(13.0, self.ambient_floor * 1.35)

            if vol < umbral_silencio:
                self.silencio_frames += 1
                total_samples = sum(len(b) for b in self.acumulador_voz)

                # Pausa natural (~0.65 - 0.70 seg tras hablar)
                if self.silencio_frames >= 7:
                    if total_samples >= int(self.samplerate * 0.35):
                        audio_np = np.concatenate(self.acumulador_voz)
                        self._despachar_analisis(audio_np)
                    self.acumulador_voz = []
                    self.hablando = False
                    self.silencio_frames = 0
            else:
                self.silencio_frames = 0
                total_samples = sum(len(b) for b in self.acumulador_voz)
                # Límite de frase continua: 12 segundos
                if total_samples > int(self.samplerate * 12):
                    audio_np = np.concatenate(self.acumulador_voz)
                    self._despachar_analisis(audio_np)
                    self.acumulador_voz = []
                    self.hablando = False
                    self.silencio_frames = 0

    def _despachar_analisis(self, audio_np):
        if self.en_proceso:
            return
        self.en_proceso = True
        self.tiempo_inicio_proceso = time.time()
        threading.Thread(target=self._analizar_audio, args=(audio_np,), daemon=True).start()

    def _analizar_audio(self, audio_np):
        temp_file = os.path.join(tempfile.gettempdir(), f"bimo_wake_{time.time_ns()}.wav")
        try:
            write(temp_file, self.samplerate, audio_np)
            prompt_sesgo = "Bimo. Asistente Bimo."
            texto = transcribir_audio(temp_file, initial_prompt=prompt_sesgo).strip()

            if not texto or len(texto) < 3:
                return

            texto_lower = texto.lower()
            import re
            # REGLA ESTRICTA: La escucha activa SOLO se activa si el usuario dice explícitamente "BIMO" como palabra clave independiente
            if not re.search(r'\b(bimo|vimo|bymo)\b', texto_lower):
                return

            print(f"[VOICE LISTENER] Activación confirmada por Bimo: \"{texto}\"")
            try:
                from audio_feedback import sonar_inicio_dictado
                sonar_inicio_dictado()
            except Exception:
                pass
            if self.callback_comando:
                self.callback_comando(texto)

        except Exception as e:
            print(f"[VOICE LISTENER] Error al procesar comando de voz: {e}")
        finally:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass
            self.en_proceso = False

    def _watchdog_loop(self):
        """Monitorea la salud del audio para evitar que el sistema se vuelva sordo tras horas de uso."""
        while self.activo:
            time.sleep(3.5)
            if not self.activo:
                break
            
            # 1. Recuperar en caso de bloqueo en procesamiento
            if self.en_proceso and (time.time() - self.tiempo_inicio_proceso) > 15.0:
                print("[VOICE LISTENER WATCHDOG] Reiniciando bandera de proceso bloqueada...")
                self.en_proceso = False

            # 2. Recuperar stream si se detuvo o fue desconectado por Windows
            if self.stream is None or not self.stream.active:
                print("[VOICE LISTENER WATCHDOG] Stream inactivo detectado. Auto-recuperando audio...")
                self._iniciar_stream()
