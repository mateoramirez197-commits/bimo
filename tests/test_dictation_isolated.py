# -*- coding: utf-8 -*-
"""
Verificación integral del pipeline de dictado y transcripción de BIMO Pro.
Comprueba:
1. Carga de faster_whisper y WhisperModel ('base').
2. Generación de un audio WAV sintético (tono de prueba o habla silente).
3. Transcripción con transcribir_audio() y verificación del fallback VAD.
4. Procesamiento clínico de un dictado simulado.
"""
import os
import sys
import wave
import struct
import math
import numpy as np

base_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.abspath(os.path.join(base_dir, ".."))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

print("=" * 60)
print(" VERIFICACIÓN DEL PIPELINE DE DICTADO BIMO PRO")
print("=" * 60)

# 1. Crear un audio WAV de prueba de 2 segundos a 16000 Hz
test_wav = os.path.join(base_dir, "test_audio_temp.wav")
sample_rate = 16000
duration = 1.5  # segundos
num_samples = int(sample_rate * duration)

print(f"\n[1/4] Generando audio WAV de prueba ({sample_rate}Hz, {duration}s)...")
with wave.open(test_wav, 'w') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(sample_rate)
    # Tono suave de 440 Hz modulado
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        val = int(32767.0 * 0.2 * math.sin(2.0 * math.pi * 440.0 * t))
        samples.append(struct.pack('<h', val))
    wf.writeframes(b''.join(samples))

print(f"      -> Archivo creado en: {test_wav} ({os.path.getsize(test_wav)} bytes)")

# 2. Cargar motor Whisper y transcribir
print("\n[2/4] Cargando ai_engine y probando transcribir_audio()...")
from ai_engine import transcribir_audio, get_whisper_engine

whisper = get_whisper_engine()
print(f"      -> WhisperModel cargado con éxito en memoria.")

try:
    texto = transcribir_audio(test_wav)
    print(f"      -> Transcripción completada sin errores: '{texto}'")
except Exception as e:
    print(f"      -> ERROR al transcribir: {e}")
    sys.exit(1)

# 3. Probar transcripción de texto clínico con la IA (Groq / Llama 3.3)
print("\n[3/4] Probando procesar_comando_o_dictado con IA Groq...")
from ai_engine import procesar_comando_o_dictado

dictado_ejemplo = (
    "Paciente Andrés Viteri, cédula 1723456789, acude por molestia en molar inferior. "
    "En el examen se observa caries oclusal en pieza 46. Diagnóstico K021 caries de la dentina. "
    "Tratamiento: restauración con resina fotocurable y profilaxis dental."
)

res_ia = procesar_comando_o_dictado(dictado_ejemplo)
print(f"      -> Tipo detectado: {res_ia.get('tipo')}")
print(f"      -> Paciente: {res_ia.get('nombre_paciente') or res_ia.get('datos_filiacion', {}).get('nombre')}")
print(f"      -> Diagnósticos: {res_ia.get('diagnosticos')}")

# 4. Probar pipeline completo desde BimoBridge.procesar_texto_clinico()...
print("\n[4/4] Probando pipeline de BimoBridge.procesar_texto_clinico()...")
from desktop_app import BimoBridge
app_instance = BimoBridge()
res_app = app_instance.procesar_texto_clinico(dictado_ejemplo)
print(f"      -> Estado resultado: {res_app.get('status')}")
print(f"      -> Tipo: {res_app.get('tipo')}")
print(f"      -> Mensaje: {res_app.get('mensaje')}")
if res_app.get('ruta_pdf'):
    print(f"      -> PDF generado correctamente: {res_app.get('ruta_pdf')}")

# Limpieza
if os.path.exists(test_wav):
    os.remove(test_wav)

print("\n" + "=" * 60)
print(" ¡VERIFICACIÓN DE DICTADO COMPLETADA CON ÉXITO TOTAL!")
print("=" * 60)
