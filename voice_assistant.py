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

async def _generar_audio_edge(texto: str, ruta_mp3: str):
    communicate = edge_tts.Communicate(texto, VOZ_FEMENINA, rate="+22%")
    await communicate.save(ruta_mp3)

def _reproducir_audio(texto: str):
    global _BIMO_HABLANDO
    with _tts_lock:
        _BIMO_HABLANDO = True
        ruta_mp3 = "temp_bimo_voice.mp3"
        exito = False
        try:
            asyncio.run(_generar_audio_edge(texto, ruta_mp3))
            if os.path.exists(ruta_mp3):
                data, fs = sf.read(ruta_mp3)
                sd.play(data, fs)
                sd.wait()
                exito = True
                try:
                    os.remove(ruta_mp3)
                except Exception:
                    pass
        except Exception:
            exito = False

        if not exito:
            try:
                engine = pyttsx3.init()
                engine.setProperty("rate", 190)
                engine.setProperty("volume", 1.0)
                voces = engine.getProperty("voices")
                for v in voces:
                    if "zira" in v.name.lower() or "sabina" in v.name.lower() or "female" in v.name.lower():
                        engine.setProperty("voice", v.id)
                        break
                engine.say(texto)
                engine.runAndWait()
                engine.stop()
            except Exception as err:
                print(f"[VOICE] Error en fallback TTS: {err}")
        
        # Pausa acústica de seguridad para que los ecos en la sala no reactiven el micrófono
        time.sleep(0.7)
        _BIMO_HABLANDO = False

def hablar_asincrono(texto: str):
    threading.Thread(target=_reproducir_audio, args=(texto,), daemon=True).start()

def decir_escuchando(nombre_doctor: str = "Mateo"):
    nombre_limpio = nombre_doctor.replace("Dr.", "").replace("Dra.", "").strip() or "Doctor"
    mensaje = f"Sí, Doctor {nombre_limpio}, lo escucho."
    hablar_asincrono(mensaje)

def decir_confirmacion_cita(nombre_doctor: str = "Mateo", nombre_paciente: str = ""):
    nombre_limpio = nombre_doctor.replace("Dr.", "").replace("Dra.", "").strip() or "Doctor"
    if nombre_paciente and nombre_paciente.lower() != "no especificado":
        mensaje = f"Doctor {nombre_limpio}, cita agendada y sincronizada para {nombre_paciente}."
    else:
        mensaje = f"Doctor {nombre_limpio}, su cita ha sido agendada y sincronizada correctamente."
    hablar_asincrono(mensaje)

def decir_cancelacion_cita(nombre_doctor: str = "Mateo", nombre_paciente: str = ""):
    nombre_limpio = nombre_doctor.replace("Dr.", "").replace("Dra.", "").strip() or "Doctor"
    if nombre_paciente and nombre_paciente.lower() != "no especificado":
        mensaje = f"Doctor {nombre_limpio}, la cita de {nombre_paciente} ha sido cancelada y eliminada del calendario."
    else:
        mensaje = f"Doctor {nombre_limpio}, la cita ha sido cancelada y eliminada de su agenda."
    hablar_asincrono(mensaje)

def decir_reprogramacion_cita(nombre_doctor: str = "Mateo", nombre_paciente: str = "", nueva_fecha: str = ""):
    nombre_limpio = nombre_doctor.replace("Dr.", "").replace("Dra.", "").strip() or "Doctor"
    if nombre_paciente and nombre_paciente.lower() != "no especificado":
        mensaje = f"Doctor {nombre_limpio}, la cita de {nombre_paciente} ha sido cambiada para la nueva fecha y la cita anterior fue eliminada."
    else:
        mensaje = f"Doctor {nombre_limpio}, la cita ha sido reprogramada y actualizada en su agenda."
    hablar_asincrono(mensaje)

def preguntar_desambiguacion_homonimos_detallada(nombre_paciente: str, lista_pacientes: list):
    """
    Formato solicitado por el doctor:
    '¿Es para Mateo Ramírez con esta edad y esta cédula o para Mateo Ramírez con esta edad y esta cédula?'
    """
    partes = []
    for p in lista_pacientes[:2]:
        edad_str = f" de {p.get('edad')} años" if p.get('edad') else ""
        doc = p.get('documento') or f"ID{p['id']}"
        partes.append(f"para {p['nombre']}{edad_str} con cédula {doc}")

    opciones = " o ".join(partes)
    mensaje = f"Encontré más de un paciente llamado {nombre_paciente}. ¿Es {opciones}?"
    hablar_asincrono(mensaje)

def preguntar_paciente_cita():
    mensaje = "¿Para qué paciente desea agendar la cita?"
    hablar_asincrono(mensaje)

def preguntar_cedula_paciente(nombre_paciente: str = "", nombre_doctor: str = "Mateo"):
    nombre_doc = nombre_doctor.replace("Dr.", "").replace("Dra.", "").strip() or "Doctor"
    if nombre_paciente and nombre_paciente.lower() != "no especificado":
        mensaje = f"Doctor {nombre_doc}, por favor ingrese o dicte el número de cédula de {nombre_paciente} para archivar su historia clínica."
    else:
        mensaje = f"Doctor {nombre_doc}, por favor ingrese el número de cédula del paciente para archivar su historia clínica."
    hablar_asincrono(mensaje)
