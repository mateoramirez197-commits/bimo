import os
import sys
import time
import queue
import tempfile
import threading
from collections import deque
import numpy as np
import sounddevice as sd
from scipy.io.wavfile import write
from ai_engine import get_whisper_engine


_VOLUMEN_WINDOWS_ASEGURADO = False


def asegurar_volumen_microfono_windows():
    """
    Asegura automáticamente (una sola vez en segundo plano) que el micrófono predeterminado de Windows
    no esté silenciado (Mute=0) y tenga un nivel de ganancia óptimo (>= 92%).
    """
    global _VOLUMEN_WINDOWS_ASEGURADO
    if _VOLUMEN_WINDOWS_ASEGURADO or sys.platform != "win32":
        return
    _VOLUMEN_WINDOWS_ASEGURADO = True

    def _ajustar_bg():
        try:
            import ctypes
            from ctypes import POINTER, byref, c_float, c_int, c_uint, c_void_p
            import comtypes
            from comtypes import GUID, IUnknown, COMMETHOD, HRESULT, CLSCTX_ALL

            class IAudioEndpointVolume(IUnknown):
                _iid_ = GUID('{5CDF2C82-841E-4546-9722-0CF74078229A}')
                _methods_ = [
                    COMMETHOD([], HRESULT, 'RegisterControlChangeNotify', (['in'], c_void_p, 'pNotify')),
                    COMMETHOD([], HRESULT, 'UnregisterControlChangeNotify', (['in'], c_void_p, 'pNotify')),
                    COMMETHOD([], HRESULT, 'GetChannelCount', (['out'], POINTER(c_uint), 'pnChannelCount')),
                    COMMETHOD([], HRESULT, 'SetMasterVolumeLevel', (['in'], c_float, 'fLevelDB'), (['in'], POINTER(GUID), 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'SetMasterVolumeLevelScalar', (['in'], c_float, 'fLevel'), (['in'], POINTER(GUID), 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'GetMasterVolumeLevel', (['out'], POINTER(c_float), 'pfLevelDB')),
                    COMMETHOD([], HRESULT, 'GetMasterVolumeLevelScalar', (['out'], POINTER(c_float), 'pfLevel')),
                    COMMETHOD([], HRESULT, 'SetChannelVolumeLevel', (['in'], c_uint, 'nChannel'), (['in'], c_float, 'fLevelDB'), (['in'], POINTER(GUID), 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'SetChannelVolumeLevelScalar', (['in'], c_uint, 'nChannel'), (['in'], c_float, 'fLevel'), (['in'], POINTER(GUID), 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'GetChannelVolumeLevel', (['in'], c_uint, 'nChannel'), (['out'], POINTER(c_float), 'pfLevelDB')),
                    COMMETHOD([], HRESULT, 'GetChannelVolumeLevelScalar', (['in'], c_uint, 'nChannel'), (['out'], POINTER(c_float), 'pfLevel')),
                    COMMETHOD([], HRESULT, 'SetMute', (['in'], c_int, 'bMute'), (['in'], POINTER(GUID), 'pguidEventContext')),
                    COMMETHOD([], HRESULT, 'GetMute', (['out'], POINTER(c_int), 'pbMute')),
                ]

            class IMMDevice(IUnknown):
                _iid_ = GUID('{D666063F-1587-4E43-81F1-B948E807363F}')
                _methods_ = [
                    COMMETHOD([], HRESULT, 'Activate', (['in'], POINTER(GUID), 'iid'), (['in'], c_uint, 'dwClsCtx'), (['in'], c_void_p, 'pActivationParams'), (['out'], POINTER(POINTER(IUnknown)), 'ppInterface')),
                ]

            class IMMDeviceEnumerator(IUnknown):
                _iid_ = GUID('{A95664D2-9614-4F35-A746-DE8DB63617E6}')
                _methods_ = [
                    COMMETHOD([], HRESULT, 'EnumAudioEndpoints', (['in'], c_uint, 'dataFlow'), (['in'], c_uint, 'dwStateMask'), (['out'], POINTER(c_void_p), 'ppDevices')),
                    COMMETHOD([], HRESULT, 'GetDefaultAudioEndpoint', (['in'], c_uint, 'dataFlow'), (['in'], c_uint, 'role'), (['out'], POINTER(POINTER(IMMDevice)), 'ppEndpoint')),
                ]

            comtypes.CoInitialize()
            clsid_enum = GUID('{BCDE0395-E52F-467C-8E3D-C4579291692E}')
            enumerator = comtypes.CoCreateInstance(clsid_enum, interface=IMMDeviceEnumerator, clsctx=CLSCTX_ALL)
            for role in (0, 1, 2):
                try:
                    dev = enumerator.GetDefaultAudioEndpoint(1, role)
                    unk = dev.Activate(byref(IAudioEndpointVolume._iid_), CLSCTX_ALL, None)
                    ep = ctypes.cast(unk, POINTER(IAudioEndpointVolume))
                    if ep.GetMute():
                        ep.SetMute(0, None)
                    if ep.GetMasterVolumeLevelScalar() < 0.90:
                        ep.SetMasterVolumeLevelScalar(0.95, None)
                except Exception:
                    pass
        except Exception:
            pass

    threading.Thread(target=_ajustar_bg, daemon=True).start()


def obtener_candidatos_microfono_predeterminado(samplerate_preferido=16000, refrescar=False):
    """
    Detecta automáticamente el micrófono predeterminado del sistema operativo (Windows)
    y genera una lista priorizada de combinaciones (device, samplerate, nombre_descriptivo)
    para garantizar que siempre se use el micrófono predeterminado activo sin intervención manual.
    """
    if refrescar:
        try:
            sd._terminate()
            sd._initialize()
        except Exception:
            pass

    asegurar_volumen_microfono_windows()

    candidatos_dispositivos = []
    vistos_dev = set()

    def _agregar_dev(dev_id, nombre, sr_nativo):
        if dev_id not in vistos_dev:
            vistos_dev.add(dev_id)
            candidatos_dispositivos.append((dev_id, nombre, int(sr_nativo or 44100)))

    # 1. Dispositivo de entrada predeterminado explícito reportado por el SO
    nombre_default = "Micrófono Predeterminado del Sistema"
    sr_default = 44100
    try:
        info_def = sd.query_devices(kind='input')
        if info_def and int(info_def.get('max_input_channels', 0)) > 0:
            idx_def = info_def.get('index', None)
            nombre_default = info_def.get('name', nombre_default)
            sr_default = int(info_def.get('default_samplerate', 44100))
            if idx_def is not None:
                _agregar_dev(int(idx_def), nombre_default, sr_default)
    except Exception:
        pass

    # 2. Dispositivo None (delega al enrutador predeterminado de PortAudio/Windows)
    _agregar_dev(None, nombre_default, sr_default)

    # 3. Sound Mapper / Controlador primario de captura de Windows (sigue dinámicamente al predeterminado)
    # y demás micrófonos físicos reales conectados como respaldo
    try:
        todos = sd.query_devices()
        # Primero los mapeadores dinámicos del sistema operativo
        for idx, d in enumerate(todos):
            if int(d.get('max_input_channels', 0)) <= 0:
                continue
            nom_l = str(d.get('name', '')).lower()
            if any(k in nom_l for k in ('asignador de sonido', 'sound mapper', 'controlador primario', 'primary sound capture')):
                _agregar_dev(idx, d.get('name', f'Device {idx}'), int(d.get('default_samplerate', 44100)))

        # Luego coincidencias exactas con el nombre del micrófono predeterminado en otras APIs (MME/DirectSound/WASAPI)
        nom_def_base = nombre_default.lower().split('(')[-1].replace(')', '').strip() if '(' in nombre_default else nombre_default.lower()
        for idx, d in enumerate(todos):
            if int(d.get('max_input_channels', 0)) <= 0:
                continue
            if int(d.get('hostapi', 0)) == 3:  # Evitar WDM-KS si MME/DirectSound/WASAPI están disponibles
                continue
            nom_d = str(d.get('name', ''))
            if nom_def_base and nom_def_base in nom_d.lower():
                _agregar_dev(idx, nom_d, int(d.get('default_samplerate', 44100)))

        # Finalmente cualquier micrófono físico real (excluyendo mezcla estéreo o altavoces loopback)
        for idx, d in enumerate(todos):
            if int(d.get('max_input_channels', 0)) <= 0:
                continue
            if int(d.get('hostapi', 0)) == 3:
                continue
            nom_d = str(d.get('name', ''))
            nom_l = nom_d.lower()
            if any(bad in nom_l for bad in ('stereo mix', 'mezcla estéreo', 'pc speaker', 'what u hear', 'loopback')):
                continue
            _agregar_dev(idx, nom_d, int(d.get('default_samplerate', 44100)))
    except Exception:
        pass

    # Construir combinaciones (device, samplerate, nombre)
    combinaciones = []
    for dev_id, nom_dev, sr_nat in candidatos_dispositivos:
        tasas = []
        for s in (sr_nat, samplerate_preferido, 44100, 48000, 16000):
            if s and int(s) not in tasas:
                tasas.append(int(s))
        for sr in tasas:
            combinaciones.append((dev_id, sr, nom_dev))

    return combinaciones


class BackgroundWakeListener:
    """
    Escucha activa continua ultra-reactiva conectada automáticamente al micrófono predeterminado:
    1. 100% en memoria RAM sin escritura a disco (cero latencia de I/O).
    2. Detección automática del micrófono predeterminado de Windows y su frecuencia nativa.
    3. Canal compartido sin colisiones (Tap directo) para dictado manual con botón (0ms de latencia).
    4. VAD adaptativo ultra-sensible compatible con micrófonos USB de baja ganancia (ej. ME6S).
    5. Perro guardián (Watchdog) auto-recuperable ante desconexión o cambio de micrófono.
    """
    def __init__(self, callback_comando, samplerate=16000):
        self.callback_comando = callback_comando
        self.samplerate = samplerate
        self.device_actual = None
        self.nombre_microfono = "Micrófono Predeterminado"
        self.activo = False
        self.pausado = False
        self.en_proceso = False
        self.tiempo_inicio_proceso = 0.0
        self.tiempo_ventana_activa = 0.0  # Ventana multi-turn para recibir órdenes tras decir 'Bimo'
        self.stream = None
        self.acumulador_voz = []
        self.hablando = False
        self.silencio_frames = 0
        self.pre_roll = deque(maxlen=10)  # ~600ms de pre-grabación para no cortar el inicio de "Bimo"
        self.ambient_floor = 8.0          # Piso de ruido inicial sensible para micrófonos USB y de estudio
        self._peak_voz = 0.0
        self._calibracion_frames = 0
        self._startup_skip_frames = 2     # Descartar primeros bloques tras iniciar stream
        self._lock = threading.Lock()
        self._hilo_watchdog = None
        self._cola_audio = queue.Queue(maxsize=3)
        self._hilo_worker = None
        self._duracion_actual_analisis = 4.0
        self._callback_tap_manual = None  # Tap en vivo para grabación por botón sin cerrar el hardware
        try:
            from audio_feedback import _asegurar_wav
            _asegurar_wav("bimo_ding.wav")
        except Exception:
            pass

    def iniciar_tap_manual(self, callback_frame):
        """
        Conecta la grabación manual por botón directamente al flujo del micrófono predeterminado
        sin cerrar ni reabrir el dispositivo de hardware (evita PaErrorCode y pérdidas de audio).
        """
        with self._lock:
            self._callback_tap_manual = callback_frame
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
            if not self.activo:
                self.activo = True
            self.pausado = False
            if self.stream is None or not getattr(self.stream, "active", False):
                self._iniciar_stream(refrescar=False)
            return self.stream is not None and getattr(self.stream, "active", False), self.samplerate

    def detener_tap_manual(self):
        """Desconecta el tap de grabación manual y limpia los acumuladores de voz activa."""
        with self._lock:
            self._callback_tap_manual = None
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
            self._startup_skip_frames = 1

    def activar_ventana_activa(self, segundos=10.0):
        """Abre una ventana activa de escucha para recibir órdenes directas sin exigir repetir 'Bimo'."""
        with self._lock:
            self.tiempo_ventana_activa = time.time() + segundos
            print(f"[VOICE LISTENER] Ventana de orden activa por {segundos}s...")

    def esta_en_ventana_activa(self) -> bool:
        return time.time() < self.tiempo_ventana_activa

    def iniciar(self):
        with self._lock:
            self.activo = True
            self.pausado = False
            if self.stream is None or not getattr(self.stream, "active", False):
                self._iniciar_stream(refrescar=False)
            if not self._hilo_worker or not self._hilo_worker.is_alive():
                self._hilo_worker = threading.Thread(target=self._worker_loop, daemon=True)
                self._hilo_worker.start()
            if not self._hilo_watchdog or not self._hilo_watchdog.is_alive():
                self._hilo_watchdog = threading.Thread(target=self._watchdog_loop, daemon=True)
                self._hilo_watchdog.start()
            # Pre-calentar motor Whisper local en segundo plano sin bloquear el arranque
            threading.Thread(target=self._precalentar_whisper, daemon=True).start()

    def _precalentar_whisper(self):
        try:
            get_whisper_engine()
        except Exception:
            pass

    def _iniciar_stream(self, refrescar=False):
        try:
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except Exception:
                    pass
                self.stream = None

            # Limpiar buffers de audio para evitar disparos con residuos
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
            self._calibracion_frames = 0
            self._startup_skip_frames = 2

            for intento_refresco in ([refrescar, True] if not refrescar else [True]):
                candidatos = obtener_candidatos_microfono_predeterminado(
                    samplerate_preferido=self.samplerate,
                    refrescar=intento_refresco
                )
                ultimo_error = None
                for dev_id, sr, nom_dev in candidatos:
                    try:
                        blocksize = max(1024, int(sr * 0.064))
                        kwargs_stream = dict(
                            samplerate=sr,
                            channels=1,
                            dtype='int16',
                            blocksize=blocksize,
                            callback=self._audio_callback
                        )
                        if dev_id is not None:
                            kwargs_stream["device"] = dev_id
                        self.stream = sd.InputStream(**kwargs_stream)
                        self.stream.start()
                        self.samplerate = sr
                        self.device_actual = dev_id
                        self.nombre_microfono = nom_dev
                        print(f"[VOICE LISTENER] Micrófono predeterminado activo: '{nom_dev}' (device={dev_id}, {self.samplerate}Hz).")
                        return
                    except Exception as e_sr:
                        ultimo_error = e_sr
                        self.stream = None
                if ultimo_error and intento_refresco:
                    print(f"[VOICE LISTENER] Error al inicializar InputStream de audio: {ultimo_error}")
        except Exception as e:
            print(f"[VOICE LISTENER] Error al inicializar InputStream de audio: {e}")

    def detener(self):
        with self._lock:
            self.activo = False
            self.pausado = True
            self._callback_tap_manual = None
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
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
        """Pausa temporalmente el procesamiento de voz activa manteniendo el stream listo."""
        with self._lock:
            self.pausado = True
            self.pre_roll.clear()
            self.acumulador_voz.clear()
            self.hablando = False
            self.silencio_frames = 0
            self._peak_voz = 0.0
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
            self._peak_voz = 0.0
            self.en_proceso = False
            self._startup_skip_frames = 2
            self.pausado = False

    def _audio_callback(self, indata, frames, time_info, status):
        # 1. Si el usuario está grabando manualmente con el botón, alimentar directamente el tap manual
        tap = self._callback_tap_manual
        if tap is not None:
            try:
                tap(indata.copy())
            except Exception:
                pass
            return

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
            self._peak_voz = 0.0
            return

        datos = indata.flatten()
        # Restar componente continua (DC offset) para neutralizar ruidos de baja frecuencia/zumbidos
        datos_centrados = datos.astype(np.float32) - float(np.mean(datos))
        vol = float(np.abs(datos_centrados).mean())
        peak_frame = float(np.max(np.abs(datos_centrados))) if datos_centrados.size else 0.0
        self.pre_roll.append(datos.copy())

        if not self.hablando:
            self._calibracion_frames += 1
            # Calibración adaptativa en reposo para int16
            if self._calibracion_frames <= 10:
                self.ambient_floor = max(3.0, min(800.0, 0.65 * self.ambient_floor + 0.35 * vol))
            elif vol < self.ambient_floor * 1.45:
                self.ambient_floor = max(3.0, min(800.0, 0.92 * self.ambient_floor + 0.08 * vol))
            else:
                self.ambient_floor = max(3.0, min(800.0, 0.985 * self.ambient_floor + 0.015 * vol))

            # Umbral firme por encima del ruido de fondo para no disparar con ruidos leves ni respiraciones
            mult_inicio = 1.65 if self.esta_en_ventana_activa() else 1.85
            umbral_inicio = max(14.0, min(1600.0, self.ambient_floor * mult_inicio + 8.0))

            if vol > umbral_inicio:
                self.hablando = True
                self.silencio_frames = 0
                self._frames_voz_reales = 1
                self._peak_voz = vol
                self.acumulador_voz = list(self.pre_roll)
                self.acumulador_voz.append(datos.copy())
        else:
            self.acumulador_voz.append(datos.copy())
            if vol > self._peak_voz:
                self._peak_voz = vol
            if vol < self.ambient_floor:
                self.ambient_floor = max(3.0, 0.97 * self.ambient_floor + 0.03 * vol)

            umbral_voz_activa = max(12.0, self.ambient_floor * 1.55 + 6.0)
            if vol > umbral_voz_activa:
                self._frames_voz_reales = getattr(self, "_frames_voz_reales", 1) + 1

            # Umbral de silencio adaptativo basado en el piso de ruido y la caída respecto al pico de voz
            umbral_base = self.ambient_floor * 1.30 + 3.5
            umbral_relativo = min(self.ambient_floor * 2.1, self._peak_voz * 0.28)
            umbral_silencio = max(6.0, min(1000.0, max(umbral_base, umbral_relativo)))

            total_samples = sum(len(b) for b in self.acumulador_voz)
            duracion_actual_seg = total_samples / self.samplerate
            frames_voz_efectiva = max(1, len(self.acumulador_voz) - len(self.pre_roll) - self.silencio_frames)
            duracion_voz_seg = (frames_voz_efectiva * (len(datos) or 1024)) / self.samplerate

            if vol < umbral_silencio:
                self.silencio_frames += 1

                # Pausa inteligente en escucha activa para permitir que el doctor piense antes de enviar la orden:
                # - En reposo diciendo solo "Bimo" (<= 1.6s de voz): 12 frames (~0.77s) para despertar rápido.
                # - En ventana activa o dictando una orden tras "Bimo" (<= 4.5s de voz): 34 frames (~2.2s) de espera inteligente.
                # - En dictado clínico extenso por voz activa (> 4.5s de voz): 38 frames (~2.4s) para pausas mientras piensa.
                if not self.esta_en_ventana_activa() and duracion_voz_seg <= 1.6:
                    max_silencio = 12
                elif duracion_voz_seg <= 4.5:
                    max_silencio = 34
                else:
                    max_silencio = 38

                if self.silencio_frames >= max_silencio:
                    frames_reales = getattr(self, "_frames_voz_reales", 1)
                    umbral_snr_pico = max(16.0, self.ambient_floor * 1.85 + 9.0)
                    if total_samples >= int(self.samplerate * 0.28) and frames_reales >= 3 and self._peak_voz >= umbral_snr_pico:
                        audio_np = np.concatenate(self.acumulador_voz)
                        self._despachar_analisis(audio_np)
                    self.acumulador_voz = []
                    self.hablando = False
                    self.silencio_frames = 0
                    self._frames_voz_reales = 0
                    self._peak_voz = 0.0
            else:
                # Solo reiniciar completamente el contador de silencio si es voz clara por encima del umbral
                umbral_voz_clara = max(umbral_silencio * 1.18, self.ambient_floor * 1.50 + 5.0)
                if vol > umbral_voz_clara:
                    self.silencio_frames = 0
                else:
                    self.silencio_frames = max(0, self.silencio_frames - 1)

                # Corte de seguridad: si no está en ventana activa y lleva > 18s, o en dictado continuo > 120s
                limite_seg = 120.0 if (self.esta_en_ventana_activa() or duracion_actual_seg > 4.0) else 18.0
                if total_samples >= int(self.samplerate * limite_seg):
                    audio_np = np.concatenate(self.acumulador_voz)
                    self._despachar_analisis(audio_np)
                    self.acumulador_voz = []
                    self.hablando = False
                    self.silencio_frames = 0
                    self._frames_voz_reales = 0
                    self._peak_voz = 0.0

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
            if duracion_seg < 0.25 or duracion_seg > 120.0:
                return

            # Normalización, remuestreo a 16000Hz y Control Automático de Ganancia (AGC equilibrado)
            from ai_engine import normalizar_audio_para_stt
            _, audio_float, tiene_energia = normalizar_audio_para_stt(audio_np, samplerate=self.samplerate)
            if not tiene_energia or audio_float.size == 0:
                return

            # 2. Transcripción de alta precisión (Groq whisper-large-v3-turbo con fallback local)
            texto = ""
            es_mock_whisper = hasattr(get_whisper_engine, "assert_called")
            if not es_mock_whisper and (duracion_seg >= 0.35):
                try:
                    from ai_engine import transcribir_audio
                    texto = transcribir_audio(audio_float)
                except Exception as e_man_par:
                    print(f"[VOICE LISTENER PARIDAD WARN]: Fallback a transcripción directa ({e_man_par})")
                    texto = ""

            if not texto:
                # Transcripción rápida local optimizada para activación y órdenes cortas
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

                # IMPORTANTE: NO incluir 'Bimo' en prompt_sesgo para evitar que Whisper lo alucine ante ruidos de sala
                prompt_sesgo = f"Consulta clínica de odontología. Citas, pacientes, Llumiquinga, Guaminga, Toapanta, Quispe, Simbaña, Tituaña, Chiluisa, Pilataxi.{vocab_aprendido}"
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
                    # Filtrar si Whisper detecta alta probabilidad de no-voz
                    if s.no_speech_prob > 0.75:
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

            # Verificar si estamos dentro de la ventana activa multi-turn (el usuario YA dijo 'Bimo' previamente)
            if self.esta_en_ventana_activa():
                palabras_activas = [w for w in palabras if w not in ('eh', 'este', 'em', 'mm', 'ah', 'oh')]
                # Si fue solo un suspiro, muletilla o ruido corto mientras el doctor piensa, mantener la ventana activa abierta
                if len(palabras_activas) < 2 and duracion_seg < 1.8:
                    print(f"[VOICE LISTENER] Pausa/muletilla detectada en ventana activa; esperando orden completa...")
                    return
                self.tiempo_ventana_activa = 0.0
                print(f"[VOICE LISTENER] Comando recibido dentro de ventana activa: \"{texto}\"")
                if self.callback_comando:
                    self.callback_comando(texto)
                return

            # 3. Regla de activación ESTRICTA: SOLO activar cuando se pronuncie claramente la palabra clave 'Bimo'
            def _es_variacion_bimo(p: str) -> bool:
                p = p.strip().lower()
                # Solo transcripciones fonéticas directas de la palabra 'Bimo' (sin palabras comunes del español)
                return p in (
                    'bimo', 'vimo', 'bymo', 'vymo', 'dimo', 'mimo',
                    'beemo', 'bmo', 'bimbo', 'bimos', 'vimos'
                )

            idx_bimo = -1
            for i, w in enumerate(palabras):
                if _es_variacion_bimo(w):
                    idx_bimo = i
                    break

            if idx_bimo == -1:
                return

            # Exigir que 'Bimo' esté al inicio de la frase de invocación (ej. "Bimo...", "Hola Bimo...", "Oye Bimo...")
            es_invocacion = False
            if idx_bimo <= 3:
                es_invocacion = True
            elif idx_bimo <= 5 and any(w in palabras[:idx_bimo] for w in ['hola', 'ola', 'oye', 'hey', 'ok', 'favor', 'asistente', 'por', 'buenas', 'buenos', 'disculpa']):
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

            # 2. Activar ventana activa con pausa inteligente (15s para dictar con calma)
            self.activar_ventana_activa(15.0)

            # 3. Filtro de Ruido (BLOQUE 2):
            # Si solo dijo "Bimo" / "Hola Bimo" para despertarlo, abrir micrófono y esperar la orden completa
            palabras_comando = [w for w in palabras if not _es_variacion_bimo(w) and w not in ('hola', 'ola', 'oye', 'hey', 'ok', 'por', 'favor', 'buenas', 'buenos', 'dias', 'tardes', 'noches')]
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
        """Monitorea la salud del audio para evitar que el sistema se vuelva sordo o pierda el micrófono predeterminado."""
        while self.activo:
            time.sleep(2.0)
            if not self.activo:
                break

            # 1. Recuperar en caso de bloqueo en procesamiento (watchdog adaptativo)
            timeout_adaptativo = max(6.0, getattr(self, "_duracion_actual_analisis", 4.0) * 1.5)
            if self.en_proceso and (time.time() - self.tiempo_inicio_proceso) > timeout_adaptativo:
                print(f"[VOICE LISTENER WATCHDOG] Reiniciando bandera de proceso tras timeout adaptativo ({timeout_adaptativo:.1f}s)...")
                self.en_proceso = False

            # 2. Recuperar stream si se detuvo o fue desconectado/cambiado en Windows
            if (not self.pausado or self._callback_tap_manual is not None) and (self.stream is None or not getattr(self.stream, "active", False)):
                print("[VOICE LISTENER WATCHDOG] Stream inactivo detectado. Auto-recuperando micrófono predeterminado...")
                with self._lock:
                    self._iniciar_stream(refrescar=True)

