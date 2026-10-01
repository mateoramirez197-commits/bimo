import math
import os
import struct
import sys
import tempfile
import threading
import wave

# Los .wav estan en .gitignore (*.wav): en un clon limpio o en el instalador no
# existirian. Por eso los tonos se SINTETIZAN la primera vez que se necesitan.
SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sounds")
_TMP_DIR = os.path.join(tempfile.gettempdir(), "bimo_sounds")
_gen_lock = threading.Lock()
_SR = 44100


def _tono(freq_ini, freq_fin=None, dur=0.25, vol=0.45, decay=6.0):
    """Seno con envolvente de decaimiento exponencial y glissando opcional."""
    freq_fin = freq_ini if freq_fin is None else freq_fin
    n = int(_SR * dur)
    out, fase = [], 0.0
    for i in range(n):
        t = i / n
        f = freq_ini + (freq_fin - freq_ini) * t
        fase += 2 * math.pi * f / _SR
        ataque = min(1.0, i / (_SR * 0.005))          # evita "click" al inicio
        env = ataque * math.exp(-decay * t)
        out.append(math.sin(fase) * env * vol)
    return out


def _silencio(dur):
    return [0.0] * int(_SR * dur)


# nombre -> muestras (floats -1..1)
def _definiciones():
    return {
        # Ding: un solo tono agudo (Sol6)
        "bimo_ding.wav": _tono(1568, dur=0.35, decay=7.0),
        # Ding-dong: dos tonos, agudo y luego mas grave
        "bimo_dingdong.wav": _tono(988, dur=0.22, decay=6.0) + _silencio(0.02) + _tono(740, dur=0.38, decay=5.0),
        # Bloop: tono grave que cae
        "bimo_bloop.wav": _tono(320, 130, dur=0.28, vol=0.55, decay=4.0),
    }


def _escribir_wav(ruta, muestras):
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(_SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1.0, min(1.0, m)) * 32767)) for m in muestras))


def _asegurar_wav(nombre):
    """Devuelve la ruta del wav; lo genera si no existe. Nunca lanza."""
    with _gen_lock:
        for carpeta in (SOUNDS_DIR, _TMP_DIR):
            ruta = os.path.join(carpeta, nombre)
            if os.path.exists(ruta):
                return ruta
        muestras = _definiciones().get(nombre)
        if muestras is None:
            return None
        for carpeta in (SOUNDS_DIR, _TMP_DIR):   # carpeta del proyecto puede ser de solo lectura (.exe)
            try:
                os.makedirs(carpeta, exist_ok=True)
                ruta = os.path.join(carpeta, nombre)
                _escribir_wav(ruta, muestras)
                return ruta
            except Exception:
                continue
    return None


def _reproducir_ruta(ruta):
    if not ruta or not os.path.exists(ruta):
        return
    try:
        if sys.platform == "win32":
            import winsound
            # SND_ASYNC con archivo: no bloquea; SND_NODEFAULT: sin beep de sistema si falla
            winsound.PlaySound(ruta, winsound.SND_FILENAME | winsound.SND_NODEFAULT | winsound.SND_ASYNC)
        else:
            import soundfile as sf
            import sounddevice as sd
            data, fs = sf.read(ruta, dtype="float32")
            sd.play(data, fs)
            sd.wait()
    except Exception:
        pass


def _reproducir_wav(nombre_archivo):
    """Reproduce un wav ya existente en assets/sounds (sonidos originales)."""
    _reproducir_ruta(os.path.join(SOUNDS_DIR, nombre_archivo))


def _lanzar(nombre_generado):
    def _run():
        _reproducir_ruta(_asegurar_wav(nombre_generado))
    threading.Thread(target=_run, daemon=True).start()


# ------------------------------------------------------------------
# API publica (todas NO bloqueantes)
# ------------------------------------------------------------------
def sonar_inicio_dictado():
    """Ding agudo: microfono abierto."""
    _lanzar("bimo_ding.wav")


def sonar_confirmacion_exito():
    """Ding-dong: operacion / cita exitosa."""
    _lanzar("bimo_dingdong.wav")


def sonar_error():
    """Bloop grave: comando no detectado o error."""
    _lanzar("bimo_bloop.wav")


def sonar_fin_dictado():
    """Se conserva tal cual: tono suave de cierre (usa el wav original si existe)."""
    threading.Thread(target=_reproducir_wav, args=("bimo_sleep.wav",), daemon=True).start()


def hablar(texto: str):
    """Emite síntesis de voz natural en español."""
    try:
        from voice_assistant import hablar as _hablar
        _hablar(texto)
    except Exception as e:
        print(f"[AUDIO FEEDBACK WARN] hablar: {e}")


def hablar_asincrono(texto: str):
    """Emite síntesis de voz natural en español de forma asíncrona."""
    try:
        from voice_assistant import hablar_asincrono as _hablar_asincrono
        _hablar_asincrono(texto)
    except Exception as e:
        print(f"[AUDIO FEEDBACK WARN] hablar_asincrono: {e}")

