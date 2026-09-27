import os
import asyncio
import threading
import soundfile as sf
import sounddevice as sd
import pyttsx3
import edge_tts

import time

# Voz Femenina Neural de Alta Definición (Cálida, Natural, Rápida y Amigable)
VOZ_FEMENINA = "es-CO-SalomeNeural" # Alternativa: "es-MX-DaliaNeural"
_tts_lock = threading.Lock()
_BIMO_HABLANDO = False

def bimo_esta_hablando() -> bool:
    """Devuelve True si Bimo está emitiendo voz por los altavoces o en el tiempo de disipación de eco."""
    return _BIMO_HABLANDO

import tempfile
import uuid

async def _generar_audio_edge(texto: str, ruta_mp3: str):
    communicate = edge_tts.Communicate(texto, VOZ_FEMENINA, rate="+22%")
    await asyncio.wait_for(communicate.save(ruta_mp3), timeout=2.2)

def _reproducir_audio(texto: str):
    global _BIMO_HABLANDO
    with _tts_lock:
        ruta_mp3 = os.path.join(tempfile.gettempdir(), f"bimo_voice_{uuid.uuid4().hex[:8]}.mp3")
        exito = False
        try:
            asyncio.run(_generar_audio_edge(texto, ruta_mp3))
            if os.path.exists(ruta_mp3) and os.path.getsize(ruta_mp3) > 0:
                data, fs = sf.read(ruta_mp3)
                try:
                    _BIMO_HABLANDO = True
                    sd.play(data, fs)
                    sd.wait()
                    exito = True
                finally:
                    time.sleep(0.4)
                    _BIMO_HABLANDO = False
        except Exception:
            exito = False
        finally:
            if os.path.exists(ruta_mp3):
                try:
                    os.remove(ruta_mp3)
                except Exception:
                    pass

        if not exito:
            try:
                _BIMO_HABLANDO = True
                engine = pyttsx3.init()
                engine.setProperty("rate", 190)
                engine.setProperty("volume", 1.0)
                voces = engine.getProperty("voices")
                for v in voces:
                    if any(k in v.name.lower() for k in ("zira", "sabina", "female", "helena", "monica", "laura")):
                        engine.setProperty("voice", v.id)
                        break
                engine.say(texto)
                engine.runAndWait()
                engine.stop()
            except Exception as err:
                print(f"[VOICE] Error en fallback TTS: {err}")
            finally:
                time.sleep(0.4)
                _BIMO_HABLANDO = False

def hablar_asincrono(texto: str):
    threading.Thread(target=_reproducir_audio, args=(texto,), daemon=True).start()

def decir_escuchando(nombre_doctor: str = "Mateo"):
    nombre_limpio = nombre_doctor.replace("Dr.", "").replace("Dra.", "").strip() or "Mateo"
    mensaje = f"Sí, {nombre_limpio}, te escucho."
    hablar_asincrono(mensaje)

def decir_confirmacion_cita(nombre_doctor: str = "Mateo", nombre_paciente: str = ""):
    nombre_limpio = nombre_doctor.replace("Dr.", "").replace("Dra.", "").strip() or "Mateo"
    if nombre_paciente and nombre_paciente.lower() != "no especificado":
        mensaje = f"{nombre_limpio}, cita agendada y sincronizada para {nombre_paciente}."
    else:
        mensaje = f"{nombre_limpio}, la cita ha sido agendada y sincronizada correctamente."
    hablar_asincrono(mensaje)

def decir_cancelacion_cita(nombre_doctor: str = "Mateo", nombre_paciente: str = ""):
    nombre_limpio = nombre_doctor.replace("Dr.", "").replace("Dra.", "").strip() or "Mateo"
    if nombre_paciente and nombre_paciente.lower() != "no especificado":
        mensaje = f"{nombre_limpio}, la cita de {nombre_paciente} ha sido cancelada y eliminada del calendario."
    else:
        mensaje = f"{nombre_limpio}, la cita ha sido cancelada y eliminada de tu agenda."
    hablar_asincrono(mensaje)

def decir_reprogramacion_cita(nombre_doctor: str = "Mateo", nombre_paciente: str = "", nueva_fecha: str = ""):
    nombre_limpio = nombre_doctor.replace("Dr.", "").replace("Dra.", "").strip() or "Mateo"
    if nombre_paciente and nombre_paciente.lower() != "no especificado":
        mensaje = f"{nombre_limpio}, la cita de {nombre_paciente} ha sido cambiada para la nueva fecha y la anterior fue eliminada."
    else:
        mensaje = f"{nombre_limpio}, la cita ha sido reprogramada y actualizada en tu agenda."
    hablar_asincrono(mensaje)

def decir_hora(frase_hora: str):
    """Pronuncia de inmediato la hora actual solicitada por voz."""
    hablar_asincrono(frase_hora)

def preguntar_desambiguacion_homonimos_detallada(nombre_paciente: str, lista_pacientes: list):
    partes = []
    for p in lista_pacientes[:2]:
        edad_str = f" de {p.get('edad')} años" if p.get('edad') else ""
        doc = p.get('documento') or f"ID{p['id']}"
        partes.append(f"para {p['nombre']}{edad_str} con cédula {doc}")

    opciones = " o ".join(partes)
    mensaje = f"Encontré más de un paciente llamado {nombre_paciente}. ¿Es {opciones}?"
    hablar_asincrono(mensaje)

def preguntar_paciente_cita():
    mensaje = "¿Para qué paciente deseas agendar la cita?"
    hablar_asincrono(mensaje)

def preguntar_fecha_hora_cita(nombre_paciente: str = ""):
    if nombre_paciente and nombre_paciente.lower() not in ("no especificado", "el último paciente", "paciente"):
        mensaje = f"Mateo, ¿para qué fecha y hora deseas la cita para {nombre_paciente}?"
    else:
        mensaje = "Mateo, ¿para qué fecha y hora deseas agendar la cita?"
    hablar_asincrono(mensaje)

def preguntar_cedula_paciente(nombre_paciente: str = "", nombre_doctor: str = "Mateo"):
    nombre_doc = nombre_doctor.replace("Dr.", "").replace("Dra.", "").strip() or "Mateo"
    if nombre_paciente and nombre_paciente.lower() != "no especificado":
        mensaje = f"{nombre_doc}, por favor ingresa o dicta el número de cédula de {nombre_paciente} para archivar su historia clínica."
    else:
        mensaje = f"{nombre_doc}, por favor ingresa el número de cédula del paciente para archivar su historia clínica."
    hablar_asincrono(mensaje)
