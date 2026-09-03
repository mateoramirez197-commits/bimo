import customtkinter as ctk
import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
import numpy as np
import threading
import os
from google import genai
from generador_pdf import crear_historia_clinica
from groq import Groq

# Reemplaza con tu clave de Groq o configúrala en la variable de entorno GROQ_API_KEY
cliente_ia = Groq(api_key=os.getenv("GROQ_API_KEY", ""))

# 2. Configuración de la Ventana Moderna
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# 3. Cargamos el Cerebro de transcripción local
print("⏳ Iniciando el sistema Bimo...")
modelo = WhisperModel("small", device="cpu", compute_type="int8")

class BimoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Bimo - Asistente Clínico Inteligente")
        self.geometry("600x450")
        
        # Variables de control
        self.grabando = False
        self.datos_audio = []
        self.frecuencia = 44100
        
        # Elementos Visuales (UI)
        self.titulo = ctk.CTkLabel(self, text="BIMO", font=("Arial", 30, "bold"))
        self.titulo.pack(pady=(20, 5))
        
        self.estado = ctk.CTkLabel(self, text="Sistema Listo", font=("Arial", 16), text_color="gray")
        self.estado.pack(pady=(0, 20))
        
        self.btn_grabar = ctk.CTkButton(self, text="🎤 Iniciar Dictado", font=("Arial", 18), 
                                        width=250, height=60, command=self.boton_presionado)
        self.btn_grabar.pack(pady=10)
        
        self.caja_texto = ctk.CTkTextbox(self, width=500, height=150, font=("Arial", 16))
        self.caja_texto.pack(pady=20)
        
        # Texto de guía actualizado
        guia_dictado = """📋 PROTOCOLO DE DICTADO CLÍNICO:

1. FILIACIÓN: "Paciente [Nombre], Edad [X] años, Sexo [X], Documento [X]"
2. CLÍNICA: "Motivo de consulta..." y "Enfermedad actual..."
3. ODONTOGRAMA: "Pieza [Número]: presenta [Caries / Calza / Endodoncia]..."

🎤 Presiona 'Iniciar Dictado' para comenzar..."""
        self.caja_texto.insert("0.0", guia_dictado)

    def boton_presionado(self):
        if not self.grabando:
            self.grabando = True
            self.btn_grabar.configure(text="🛑 Terminar Dictado", fg_color="#c0392b", hover_color="#e74c3c")
            self.estado.configure(text="🔴 Escuchando...", text_color="#e74c3c")
            self.datos_audio = []
            self.caja_texto.delete("0.0", "end")
            threading.Thread(target=self.grabar_audio).start()
        else:
            self.grabando = False
            self.btn_grabar.configure(text="⏳ Procesando IA...", fg_color="gray", state="disabled")
            self.estado.configure(text="Analizando audio...", text_color="orange")

    def grabar_audio(self):
        with sd.InputStream(samplerate=self.frecuencia, channels=1, dtype='int16',
                            callback=self.capturar_audio):
            while self.grabando:
                sd.sleep(100)
        self.procesar_inteligencia()

    def capturar_audio(self, indata, frames, time, status):
        if self.grabando:
            self.datos_audio.extend(indata.copy())

    def procesar_inteligencia(self):
        audio_np = np.array(self.datos_audio)
        write("temp.wav", self.frecuencia, audio_np)
        
        self.estado.configure(text="Whisper transcribiendo...", text_color="orange")
        segmentos, _ = modelo.transcribe("temp.wav", language="es")
        texto_crudo = "".join([segmento.text + " " for segmento in segmentos])
        
        self.estado.configure(text="IA corrigiendo formato...", text_color="yellow")
        
        prompt = f"""
        Eres el motor clínico de Bimo. Transforma el dictado de voz en un JSON estructurado para una historia clínica odontológica con validez legal.
        REGLA ESTRICTA DE JERGA: Traduce TODO término coloquial a lenguaje odontológico profesional y nomenclatura FDI. 
        Si un dato solicitado no se menciona en el dictado, llénalo obligatoriamente con la frase "No especificado".
        
        Devuelve ÚNICAMENTE un formato JSON válido con esta estructura exacta:
        {{
            "datos_filiacion": {{"nombre": "", "edad": "", "sexo": "", "documento": "", "ocupacion": "", "direccion": "", "contacto_emergencia": "", "medico_cabecera": ""}},
            "motivo_consulta": "",
            "enfermedad_actual": "",
            "antecedentes": {{"enfermedades_sistemicas": "", "alergias": "", "medicamentos": "", "trastornos_coagulacion": "", "cirugias_previas": ""}},
            "examen_extraoral": "",
            "examen_intraoral": "",
            "odontograma": [
                {{
                    "pieza_dental": "Nombre clínico exacto y número FDI (ej. Pieza 16)",
                    "procedimientos_o_hallazgos": ["Hallazgo 1", "Hallazgo 2"]
                }}
            ],
            "indices_higiene": {{"placa_bacteriana": "", "sangrado_gingival": ""}},
            "examenes_complementarios": "",
            "diagnostico": "",
            "plan_tratamiento": "",
            "evolucion": ""
        }}
        Dictado crudo: {texto_crudo}
        """
        
        try:
            # Capturamos el modelo desde el entorno o usamos tu alternativa por defecto
            modelo_groq = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
            
            respuesta = cliente_ia.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=modelo_groq, 
                temperature=0.1 
            )
            
            json_puro = respuesta.choices[0].message.content.replace('```json', '').replace('```', '').strip()
            
            print("\n--- JSON GENERADO (SOLO PARA MATEO) ---")
            print(json_puro)
            print("---------------------------------------\n")
            # Envía los datos al módulo del PDF
            crear_historia_clinica(json_puro)
            
            self.caja_texto.delete("0.0", "end")
            self.caja_texto.insert("0.0", "✅ Dictado procesado y estandarizado correctamente.\n\nLos datos han sido clasificados para la historia clínica.")
            
        except Exception as e:
            self.caja_texto.insert("end", f"\nError IA: {e}")
        
        self.btn_grabar.configure(text="🎤 Iniciar Dictado", fg_color=['#3a7ebf', '#1f538d'], state="normal")
        self.estado.configure(text="Sistema Listo", text_color="gray")
        
        if os.path.exists("temp.wav"):
            os.remove("temp.wav")

if __name__ == "__main__":
    app = BimoApp()
    app.mainloop()