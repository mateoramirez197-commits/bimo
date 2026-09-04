import os
import sys
import json
import threading
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write as wav_write
from pathlib import Path
import webview

from database import (
    init_db,
    buscar_pacientes,
    listar_consultas_paciente,
    registrar_o_actualizar_paciente,
    guardar_consulta_db,
    obtener_consulta_por_id,
    listar_citas_db,
    crear_cita_db,
    purgar_datos_prueba
)
from ai_engine import transcribir_audio, procesar_comando_o_dictado
from generador_pdf import crear_historia_clinica
from config import cargar_datos_clinica, guardar_datos_clinica, obtener_tema_activo_dict, BASE_DIR
from mobile_mic_server import iniciar_servidor_movil

class BimoBridge:
    def __init__(self):
        self.window = None
        self.grabando = False
        self.datos_audio = []
        self.frecuencia = 44100
        self.ultima_ruta_pdf = None
        self.paciente_activo = None

    def set_window(self, window):
        self.window = window

    def iniciar_grabacion(self):
        try:
            self.grabando = True
            self.datos_audio = []
            threading.Thread(target=self._grabar_audio_loop, daemon=True).start()
            print("[BIMO DESKOPP} Grabación de audio iniciada...")
            return {"status": "ok", "message": "Grabando..."}
        except Exception as e:
            print(f"[BIMO DESKOP ERROR] Error al iniciar grabación: {e}")
            return {"status": "error", "message": str(e)}

    def _grabar_audio_loop(self):
        def callback(indata, frames, time, status):
            if self.grabando:
                self.datos_audio.extend(indata.copy())
        
        try:
            with sd.InputStream(samplerate=self.frecuencia, channels=1, dtype='int16', callback=callback):
                while self.grabando:
                    sd.sleep(100)
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] Error en stream de audio: {e}")

    def detener_y_procesar(self):
        try:
            self.grabando = False
            print("[BIMO DESKOPP} Deteniendo grabación y procesando...")
            if not self.datos_audio:
                return {"status": "error", "message": "No se detectó audio."}

            ruta_wav = str(BASE_DIR / "temp_dictado.wav")
            audio_np = np.array(self.datos_audio, dtype=np.int16)
            wav_write(ruta_wav, self.frecuencia, audio_np)

            texto = transcribir_audio(ruta_wav)
            if not texto.strip():
                return {"status": "error", "message": "No se detectó voz audible."}

            resultado_ia = procesar_comando_o_dictado(texto)
            
            nombre = resultado_ia.get("paciente", "Paciente_Consulta")
            pac_id = registrar_o_actualizar_paciente(nombre)
            
            guardar_consulta_db(
                paciente_id=pac_id,
                motivo=resultado_ia.get("motivo", "Consulta"),
                diagnostico=resultado_ia.get("diagnostico", "No especificado"),
                plan_tratamiento=resultado_ia.get("plan", "No especificado"),
                notas_evolucion=texto,
                odontograma=resultado_ia.get("odontograma", []),
                honorarios=resultado_ia.get("honorarios", {}),
                proxima_cita=resultado_ia.get("cita", {})
            )

            datos_clinica = cargar_datos_clinica()
            ruta_pdf = crear_historia_clinica(
                paciente=nombre,
                fecha=resultado_ia.get("fecha", ""),
                diagnostico=resultado_ia.get("diagnostico", ""),
                tratamiento=resultado_ia.get("plan", ""),
                odontograma=resultado_ia.get("odontograma", []),
                receta=resultado_ia.get("receta", []),
                honorarios=resultado_ia.get("honorarios", {}),
                proxima_cita=resultado_ia.get("cita", {}),
                datos_clinica=datos_clinica
            )
            self.ultima_ruta_pdf = ruta_pdf


            return {
                "status": "ok",
                "texto": texto,
                "resultado": resultado_ia,
                "ruta_pdf": ruta_pdf
            }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] Error al procesar dictado: {e}")
            return {"status": "error", "message": str(e)}

    def abrir_ultimo_pdf(self):
        try:
            if self.ultima_ruta_pdf and os.path.exists(self.ultima_ruta_pdf):
                os.startfile(self.ultima_ruta_pdf)
                return {"status": "ok"}
            dir_hist = BASE_DIR / "historias_clinicas"
            if dir_hist.exists():
                pdfs = list(dir_hist.glob("*.pdf"))
                if pdfs:
                    ultimo = max(pdfs, key=os.path.getmtime)
                    os.startfile(str(ultimo))
                    return {"status": "ok"}
            return {"status": "error", "message": "No hay ningun PDF generado aun."}
        except Exception as e:
            return {"status": "error", "message": str(e)}


    def obtener_pacientes(self, filtro=""):
        try:
            return buscar_pacientes(filtro)
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] Error al buscar pacientes: {e}")
            return []

    def obtener_citas(self):
        try:
            return listar_citas_db()
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] Error al listar citas: {e}")
            return []

    def obtener_info_clinica(self):
        return cargar_datos_clinica()

def iniciar_desktop():
    init_db()
    purgar_datos_prueba()

    bridge = BimoBridge()
    try:
        iniciar_servidor_movil(callback_audio=lambda f: print('[MOBILE MIC] Audio recibido:', f))
    except Exception as e:
        print('[MOBILE SERVER WARN]', e)

    ruta_html = os.path.abspath(os.path.join(os.path.dirname(__file__), "web_ui", "index.html"))
    if not os.path.exists(ruta_html):
        print(f"[ERROR] No se encontro el archivo de interfaz en {ruta_html}")
        sys.exit(1)

    url_target = f'file:///{ruta_html.replace(os.sep, "/")}'
    window = webview.create_window(
        title='BIMO - Asistente Clinico Inteligente',
        url=url_target,
        js_api=bridge,
        width=1340,
        height=880,
        min_size=(1080, 700),
        background_color='#090614'
    )
    bridge.set_window(window)


    print('=' * 60)
    print('🏷️ BIMO Modern Desktop iniciado exitosamente.')
    print('=' * 60)
    webview.start(debug=False)

if __name__ == '__main__':
    iniciar_desktop()
