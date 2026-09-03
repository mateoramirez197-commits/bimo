import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
import os

# 1. Cargamos el cerebro (Solo descarga la primera vez)
print("⏳ Cargando el cerebro de Bimo (Whisper Small)...")
modelo = WhisperModel("small", device="cpu", compute_type="int8")

# 2. Configuración del micrófono
frecuencia = 44100  # Calidad de CD
segundos = 7        # Tiempo de grabación para esta prueba

print("\n========================================")
print(f"🔴 ¡HABLA AHORA! (Te escucharé por {segundos} segundos...)")
print("========================================\n")

# 3. Empieza a grabar
audio = sd.rec(int(segundos * frecuencia), samplerate=frecuencia, channels=1, dtype='int16')
sd.wait() # Espera a que pasen los 7 segundos
print("✅ Grabación terminada. Procesando...")

# 4. Guardamos el audio
write("temp.wav", frecuencia, audio)

# 5. Inteligencia Artificial analiza el texto
segmentos, info = modelo.transcribe("temp.wav", language="es")

texto_final = ""
for segmento in segmentos:
    texto_final += segmento.text + " "

# 6. Resultado
print("\n========================================")
print(f"🏥 BIMO ESCUCHÓ: {texto_final.strip()}")
print("========================================\n")

# Limpiamos el rastro por privacidad médica
if os.path.exists("temp.wav"):
    os.remove("temp.wav")