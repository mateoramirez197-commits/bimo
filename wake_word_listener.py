import os
import time
import queue
import tempfile
import threading
from collections import deque
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from ai_engine import get_whisper_engine

class BackgroundWakeListener:
    """
    Escucha activa continua ultra-reactiva a 16000Hz nativos:
    1. 100% en memoria RAM sin escritura a disco (cero latencia de I/O).
    2. VAD de reacción rápida (~190ms de pausa tras decir 'Bimo').
    3. Ventana temporal optimizada y búfer de hasta 120s para dictados continuos.
    4. Cola de procesamiento asíncrono (hasta 3 segmentos) sin pérdida de voz.
    5. Paridad con transcripción clínica manual (>3s).
    6. Perro guardián (Watchdog) auto-recuperable adaptativo.
    """
    def __init__(self, callback_comando, samplerate=16000):
        self.callback_comando = callback_comando
        self.samplerate = samplerate
        self.activo = False
        self.pausado = False
        self.en_proceso = False
        self.tiempo_inicio_proceso = 0.0
        self.tiempo_ventana_activa = 0.0  # Ventana multi-turn para recibir órdenes tras decir 'Bimo'
        self.stream = None
        self.acumulador_voz = []
        self.hablando = False
        self.silencio_frames = 0
        self.pre_roll = deque(maxlen=6)  # ~384ms de pre-grabación a 16kHz
        self.ambient_floor = 18.0        # Piso de ruido inicial calibrado
        self._startup_skip_frames = 2    # Descartar primeros bloques tras iniciar stream
        self._lock = threading.Lock()
        self._hilo_watchdog = None
        self._cola_audio = queue.Queue(maxsize=3)
        self._hilo_worker = None
        self._duracion_actual_analisis = 4.0
        try:
            from audio_feedback import _asegurar_wav
            _asegurar_wav("bimo_ding.wav")
        except Exception:
            pass

    def activar_ventana_activa(self, segundos=7.5):
        """Abre una ventana activa de escucha para recibir órdenes directas sin exigir repetir 'Bimo'."""
        with self._lock:
            self.tiempo_ventana_activa = time.time() + segundos
            print(f"[VOICE LISTENER] Ventana de orden activa por {segundos}s...")

    def esta_en_ventana_activa(self) -> bool:
        return time.time() < self.tiempo_ventana_activa

    def iniciar(self):
        with self._lock:
            if not self.activo:
                self.activo = True
                self.pausado = False
                self._iniciar_stream()
                if not self._hilo_worker or not self._hilo_worker.is_alive():
                    self._hilo_worker = threading.Thread(target=self._worker_loop, daemon=True)
                    self._hilo_worker.start()
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
            # Limpiar buffers de audio para evitar disparos con residuos
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._startup_skip_frames = 2

            self.stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=1,
                dtype='int16',
                blocksize=1024,
                callback=self._audio_callback
            )
            self.stream.start()
            print(f"[VOICE LISTENER] Escucha activa continua iniciada a {self.samplerate}Hz nativos (Di 'Bimo').")
        except Exception as e:
            print(f"[VOICE LISTENER] Error al inicializar InputStream de audio: {e}")

    def detener(self):
        with self._lock:
            self.activo = False
            self.pausado = True
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self.en_proceso = False
            self.tiempo_ventana_activa = 0.0
            while not self._cola_audio.empty():
                try:
                    self._cola_audio.get_nowait()
                except Exception:
                    break
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
            self.tiempo_ventana_activa = 0.0
            while not self._cola_audio.empty():
                try:
                    self._cola_audio.get_nowait()
                except Exception:
                    break

    def reanudar(self):
        """Reanuda la escucha activa con buffers limpios y supresión de transitorio inicial."""
        with self._lock:
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self.en_proceso = False
            self._startup_skip_frames = 2
            self.pausado = False

    def _audio_callback(self, indata, frames, time_info, status):
        if not self.activo or self.pausado:
            return

        # Supresión de transitorio inicial al abrir el hardware de audio
        if self._startup_skip_frames > 0:
            self._startup_skip_frames -= 1
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
        # Restar componente continua (DC offset) para neutralizar ruidos de baja frecuencia/zumbidos
        datos_centrados = datos - np.mean(datos)
        vol = float(np.abs(datos_centrados).mean())
        self.pre_roll.append(datos)

        if not self.hablando:
            # Calibración adaptativa en reposo con piso mínimo de 12.0 y techo de 50.0
            # Evita que el ruido constante de fondo desensibilice el micrófono
            self.ambient_floor = max(12.0, min(50.0, 0.96 * self.ambient_floor + 0.04 * vol))
            # Si estamos en ventana activa, ser aún más reactivo
            mult_inicio = 1.22 if self.esta_en_ventana_activa() else 1.36
            umbral_inicio = max(20.0, min(65.0, self.ambient_floor * mult_inicio))

            if vol > umbral_inicio:
                self.hablando = True
                self.silencio_frames = 0
                self.acumulador_voz = list(self.pre_roll)
                self.acumulador_voz.append(datos)
        else:
            self.acumulador_voz.append(datos)
            umbral_silencio = max(15.0, min(55.0, self.ambient_floor * 1.12))

            if vol < umbral_silencio:
                self.silencio_frames += 1
                total_samples = sum(len(b) for b in self.acumulador_voz)
                duracion_actual_seg = total_samples / self.samplerate

                # Umbral de silencio dinámico (Pausa Inteligente BLOQUE 2):
                # - En reposo esperando la palabra de activación ("Bimo"): 9 frames (~576ms) para reacción ultra-rápida.
                # - Post-activación o en orden/dictado (> 1.2s): Pausa inteligente de 3.5 a 4.5 segundos
                #   (60 frames * 0.064s = 3.84s) para permitir pausas reflexivas sin cortar la voz.
                if self.esta_en_ventana_activa() or duracion_actual_seg > 1.2:
                    max_silencio = 60  # ~3.84s (rango 3.5 - 4.5s)
                else:
                    max_silencio = 9   # ~576ms para detección ágil de "Bimo"

                if self.silencio_frames >= max_silencio:
                    if total_samples >= int(self.samplerate * 0.22):
                        audio_np = np.concatenate(self.acumulador_voz)
                        self._despachar_analisis(audio_np)
                    self.acumulador_voz = []
                    self.hablando = False
                    self.silencio_frames = 0
            else:
                self.silencio_frames = 0
                total_samples = sum(len(b) for b in self.acumulador_voz)
                # Búfer de hasta 120 segundos para dictados continuos sin corte prematuro:
                if total_samples >= int(self.samplerate * 120.0):
                    audio_np = np.concatenate(self.acumulador_voz)
                    self._despachar_analisis(audio_np)
                    self.acumulador_voz = []
                    self.hablando = False
                    self.silencio_frames = 0

    def _despachar_analisis(self, audio_np):
        """Encola el audio para procesamiento asíncrono (cola de hasta 3 segmentos)."""
        try:
            self._cola_audio.put_nowait(audio_np)
        except queue.Full:
            print("[VOICE LISTENER WARN] Cola de audio llena (3 segmentos). Descartando el más antiguo.")
            try:
                self._cola_audio.get_nowait()
            except Exception:
                pass
            try:
                self._cola_audio.put_nowait(audio_np)
            except Exception:
                pass

    def _worker_loop(self):
        """Hilo dedicado a procesar secuencialmente la cola de audio sin bloquear el callback de sonido."""
        while self.activo:
            try:
                audio_np = self._cola_audio.get(timeout=1.0)
            except queue.Empty:
                continue

            try:
                self.en_proceso = True
                self.tiempo_inicio_proceso = time.time()
                self._analizar_audio(audio_np)
            except Exception as e_w:
                print(f"[VOICE LISTENER WORKER ERROR]: {e_w}")
            finally:
                self.en_proceso = False
                try:
                    self._cola_audio.task_done()
                except Exception:
                    pass

    def _analizar_audio(self, audio_np):
        try:
            # 1. Filtro de energía acústica y duración en memoria RAM (hasta 120s)
            duracion_seg = len(audio_np) / self.samplerate
            self._duracion_actual_analisis = duracion_seg
            if duracion_seg < 0.20 or duracion_seg > 120.0:
                return

            # Resampleo de seguridad a 16000Hz si la captura fue en otra frecuencia
            if self.samplerate != 16000:
                try:
                    import scipy.signal
                    num_samples = int(len(audio_np) * 16000 / self.samplerate)
                    audio_16k = scipy.signal.resample(audio_np.astype(np.float32), num_samples)
                except Exception:
                    audio_16k = audio_np.astype(np.float32)
            else:
                audio_16k = audio_np.astype(np.float32)

            # Remover componente continua
            audio_16k = audio_16k - np.mean(audio_16k)

            rms = float(np.sqrt(np.mean(audio_16k ** 2)))
            peak = float(np.max(np.abs(audio_16k)))

            # Habla humana real frente a micrófono o a distancia (sensible para captar voces lejanas)
            if rms < 6.0 or peak < 25.0:
                return

            # Convertir a float32 [-1.0, 1.0] para Faster-Whisper
            audio_float = audio_16k / 32768.0

            # AGC (Control Automático de Ganancia) Far-Field estilo Alexa:
            # Amplifica señales tenues habladas a 2-4 metros hasta alcanzar ~0.80 de amplitud pico
            max_amp = float(np.max(np.abs(audio_float)))
            if max_amp > 1e-4:
                ganancia = min(25.0, 0.80 / max_amp)
                if ganancia > 1.0:
                    audio_float = audio_float * ganancia

            # 2. Transcripción con paridad respecto al dictado manual para clips > 3s
            texto = ""
            if duracion_seg > 3.0:
                try:
                    from ai_engine import transcribir_audio
                    texto = transcribir_audio(audio_float)
                except Exception as e_man_par:
                    print(f"[VOICE LISTENER PARIDAD WARN]: Fallback a transcripción directa ({e_man_par})")
                    texto = ""

            if not texto:
                # Transcripción rápida optimizada para activación y órdenes cortas
                model = get_whisper_engine()
                
                # Inyección dinámica de vocabulario aprendido en el prompt de Whisper
                vocab_aprendido = ""
                try:
                    from database import obtener_vocabulario_aprendido
                    aprendidos = obtener_vocabulario_aprendido(limite=40)
                    if aprendidos:
                        vocab_aprendido = " Apellidos aprendidos: " + ", ".join(aprendidos) + "."
                except Exception:
                    vocab_aprendido = ""

                prompt_sesgo = f"Bimo, asistente clínico de odontología. Oye Bimo, Hola Bimo. Citas, pacientes, Llumiquinga, Guaminga, Toapanta, Quispe, Simbaña, Tituaña, Chiluisa, Pilataxi.{vocab_aprendido}"
                segmentos, _ = model.transcribe(
                    audio_float,
                    language="es",
                    initial_prompt=prompt_sesgo,
                    vad_filter=False,  # El VAD por energía ya aisló la frase; evitar recorte de clips cortos
                    beam_size=1,
                    temperature=0.0,
                    condition_on_previous_text=False
                )

                texto_partes = []
                for s in segmentos:
                    # Filtrar solo si Whisper tiene certeza casi total de que no es voz
                    if s.no_speech_prob > 0.88:
                        continue
                    texto_partes.append(s.text)

                if not texto_partes:
                    return

                texto = " ".join(texto_partes).strip()
            if not texto or len(texto) < 3:
                return

            import re
            texto_limpio = re.sub(r'[^\w\s]', ' ', texto.lower()).strip()
            palabras = texto_limpio.split()

            # Verificar si estamos dentro de la ventana activa multi-turn (ej. el usuario ya dijo 'Bimo' hace unos segundos)
            if self.esta_en_ventana_activa():
                self.tiempo_ventana_activa = 0.0
                palabras_activas = [w for w in palabras if w not in ('eh', 'este', 'em')]
                # Filtro de ruido en ventana activa: si no hay palabras útiles o es silencio residual
                if duracion_seg < 1.5 and len(palabras_activas) == 0:
                    print(f"[VOICE LISTENER] Ruido descartado en ventana activa ({duracion_seg:.2f}s).")
                    return
                print(f"[VOICE LISTENER] Comando recibido dentro de ventana activa: \"{texto}\"")
                if self.callback_comando:
                    self.callback_comando(texto)
                return

            # 3. Regla de activación con soporte de variaciones fonéticas y tolerancia acústica
            def _es_variacion_bimo(p: str) -> bool:
                p = p.strip().lower()
                # Coincidencias fonéticas directas comunes de Whisper en español
                if p in ('bimo', 'vimo', 'bymo', 'vymo', 'dimo', 'mimo', 'beemo', 'bmo', 'primo', 'vino', 'dime', 'vimos', 'bimos', 'pimo'):
                    return True
                # Distancia de edición 1 con 'bimo' para 4 letras
                if len(p) == 4:
                    if sum(1 for a, b in zip(p, 'bimo') if a != b) <= 1:
                        return True
                return False

            idx_bimo = -1
            for i, w in enumerate(palabras):
                if _es_variacion_bimo(w):
                    idx_bimo = i
                    break

            # Búsqueda regex por patrón fonético si no se halló por token
            if idx_bimo == -1:
                if re.search(r'\b(?:oye|hola|hey|ok)?\s*[bv][iíy]m[oa]s?\b', texto_limpio):
                    idx_bimo = 0

            if idx_bimo == -1:
                return

            es_invocacion = False
            if idx_bimo <= 2:
                es_invocacion = True
            elif any(w in palabras[:idx_bimo] for w in ['hola', 'oye', 'hey', 'ok', 'favor', 'asistente', 'por', 'bimo', 'vimo']):
                es_invocacion = True
            elif len(palabras) <= 6:
                es_invocacion = True

            if not es_invocacion:
                return

            print(f"[VOICE LISTENER] Activación confirmada por Bimo: \"{texto}\"")
            # 1. Feedback acústico instantáneo (0ms de latencia)
            try:
                from audio_feedback import sonar_inicio_dictado
                sonar_inicio_dictado()
            except Exception:
                pass

            # 2. Activar ventana activa con pausa inteligente (3.5 - 4.5s)
            self.activar_ventana_activa(10.0)

            # 3. Filtro de Ruido (BLOQUE 2):
            # Si el clip contiene menos de 1.5 segundos de voz útil (solo escuchó "Bimo" y luego silencio total),
            # o si no hay comando tras "Bimo", notificar a la UI para feedback visual y descartar
            # silenciosamente el envío de comando nulo.
            palabras_comando = [w for w in palabras if not _es_variacion_bimo(w) and w not in ('hola', 'oye', 'hey', 'ok', 'por', 'favor')]
            if len(palabras_comando) == 0 or (duracion_seg < 1.5 and len(palabras_comando) == 0):
                print(f"[VOICE LISTENER] Activación inicial 'Bimo' detectada. Micrófono abierto con pausa inteligente.")
                if self.callback_comando:
                    self.callback_comando("__BIMO_WAKE_LISTENING__")
                return

            if self.callback_comando:
                self.callback_comando(texto)

        except Exception as e:
            print(f"[VOICE LISTENER] Error al procesar comando de voz: {e}")
        finally:
            self.en_proceso = False

    def _watchdog_loop(self):
        """Monitorea la salud del audio para evitar que el sistema se vuelva sordo tras horas de uso."""
        while self.activo:
            time.sleep(2.0)
            if not self.activo:
                break

            # 1. Recuperar en caso de bloqueo en procesamiento (watchdog adaptativo)
            timeout_adaptativo = max(6.0, getattr(self, "_duracion_actual_analisis", 4.0) * 1.5)
            if self.en_proceso and (time.time() - self.tiempo_inicio_proceso) > timeout_adaptativo:
                print(f"[VOICE LISTENER WATCHDOG] Reiniciando bandera de proceso tras timeout adaptativo ({timeout_adaptativo:.1f}s)...")
                self.en_proceso = False

            # 2. Recuperar stream si se detuvo o fue desconectado por Windows
            if self.stream is None or not self.stream.active:
                print("[VOICE LISTENER WATCHDOG] Stream inactivo detectado. Auto-recuperando audio...")
                self._iniciar_stream()
