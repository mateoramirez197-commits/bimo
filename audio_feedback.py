import os
import sys
import threading

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "sounds")

def _reproducir_wav(nombre_archivo):
    ruta = os.path.join(SOUNDS_DIR, nombre_archivo)
    if not os.path.exists(ruta):
        return

    try:
        if sys.platform == "win32":
            import winsound
            winsound.PlaySound(ruta, winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            import soundfile as sf
            import sounddevice as sd
            data, fs = sf.read(ruta, dtype='float32')
            sd.play(data, fs)
            sd.wait()
    except Exception:
        pass

def sonar_inicio_dictado():
    """Chime cristalino de activación estilo Siri / Google Assistant ('Bimo te está escuchando')."""
    threading.Thread(target=_reproducir_wav, args=("bimo_listen.wav",), daemon=True).start()

def sonar_fin_dictado():
    """Tono suave descendente tipo campana cálida ('Bimo en pausa / apagado')."""
    threading.Thread(target=_reproducir_wav, args=("bimo_sleep.wav",), daemon=True).start()

def sonar_confirmacion_exito():
    """Chime armónico de 3 tonos para acciones clínicas completadas con éxito."""
    threading.Thread(target=_reproducir_wav, args=("bimo_success.wav",), daemon=True).start()
