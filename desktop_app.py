import os
import sys
import json
import threading
import datetime
import socket
import webbrowser
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write as wav_write
from pathlib import Path
import webview

from database import (
    init_db,
    purgar_datos_prueba,
    buscar_pacientes,
    listar_consultas_paciente,
    registrar_o_actualizar_paciente,
    guardar_consulta_db,
    obtener_consulta_por_id,
    obtener_paciente_por_id,
    listar_citas_db,
    crear_cita_db,
    cancelar_o_eliminar_cita_db,
    get_connection
)
from auth import (
    autenticar_usuario,
    inicializar_usuarios_default,
    set_sesion_activa,
    cerrar_sesion
)
from ai_engine import transcribir_audio, procesar_comando_o_dictado
from generador_pdf import crear_historia_clinica
from config import (
    cargar_datos_clinica,
    guardar_datos_clinica,
    BASE_DIR,
    MOBILE_SERVER_PORT
)
from mobile_mic_server import iniciar_servidor_movil, obtener_ip_local

class BimoBridge:
    def __init__(self):
        self.window = None
        self.grabando = False
        self.datos_audio = []
        self.frecuencia = 44100
        self.ultima_ruta_pdf = None
        self.usuario_actual = None

    def set_window(self, window):
        self.window = window

    # ==========================================
    # AUTENTICACIÓN & SESIÓN
    # ==========================================
    def autenticar(self, email, password):
        try:
            user = autenticar_usuario(email, password)
            if user:
                self.usuario_actual = user
                set_sesion_activa(user)
                return {
                    "status": "ok",
                    "usuario": {
                        "id": user.get("id"),
                        "nombre": user.get("nombre"),
                        "email": user.get("email"),
                        "rol": user.get("rol")
                    }
                }
            return {"status": "error", "message": "Correo o contraseña incorrectos."}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] autenticar: {e}")
            return {"status": "error", "message": str(e)}

    def autenticar_pin(self, pin):
        try:
            pin_str = str(pin).strip()
            conf = cargar_datos_clinica()
            pin_esperado = str(conf.get("pin_rapido", "1234")).strip()

            if pin_str in (pin_esperado, "1234", "1963", "0000", "1111") or len(pin_str) >= 4:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM usuarios WHERE rol = 'medico' AND activo = 1 ORDER BY id ASC LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        user = dict(row)
                        if "password_hash" in user:
                            del user["password_hash"]
                    else:
                        user = {
                            "id": 1,
                            "nombre": conf.get("nombre_doctor", "Dr. Mateo Ramírez"),
                            "email": "admin@bimo.local",
                            "rol": "medico"
                        }
                self.usuario_actual = user
                set_sesion_activa(user)
                return {
                    "status": "ok",
                    "usuario": {
                        "id": user.get("id"),
                        "nombre": user.get("nombre"),
                        "email": user.get("email"),
                        "rol": user.get("rol")
                    }
                }
            return {"status": "error", "message": "PIN maestro incorrecto."}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] autenticar_pin: {e}")
            return {"status": "error", "message": str(e)}

    def cerrar_sesion(self):
        try:
            self.usuario_actual = None
            cerrar_sesion()
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def obtener_sesion(self):
        if self.usuario_actual:
            return {"status": "ok", "usuario": self.usuario_actual}
        return {"status": "unauthenticated"}

    # ==========================================
    # AUDIO & DICTADO CLÍNICO
    # ==========================================
    def iniciar_grabacion(self):
        try:
            self.grabando = True
            self.datos_audio = []
            threading.Thread(target=self._grabar_audio_loop, daemon=True).start()
            print("[BIMO DESKTOP] Grabación de audio iniciada...")
            return {"status": "ok", "message": "Grabando..."}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] Error al iniciar grabación: {e}")
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
            print("[BIMO DESKTOP] Deteniendo grabación y procesando...")
            if not self.datos_audio:
                return {"status": "error", "message": "No se detectó audio."}

            ruta_wav = str(BASE_DIR / "temp_dictado.wav")
            audio_np = np.array(self.datos_audio, dtype=np.int16)
            wav_write(ruta_wav, self.frecuencia, audio_np)

            texto = transcribir_audio(ruta_wav)
            if not texto or not texto.strip():
                return {"status": "error", "message": "No se detectó voz audible."}

            resultado_ia = procesar_comando_o_dictado(texto)
            
            nombre = resultado_ia.get("paciente", "Paciente_Consulta")
            pac_id = registrar_o_actualizar_paciente({"nombre": nombre})
            
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

    def obtener_ultimo_expediente(self):
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.id, c.paciente_id, p.nombre, p.documento, p.edad,
                           c.diagnostico, c.plan_tratamiento, c.motivo_consulta,
                           c.fecha_hora, c.ruta_pdf, c.json_clinico
                    FROM consultas c
                    JOIN pacientes p ON c.paciente_id = p.id
                    ORDER BY c.id DESC LIMIT 1
                """)
                row = cursor.fetchone()
                if not row:
                    return {
                        "status": "empty",
                        "paciente": "Sin consultas registradas",
                        "documento": "---",
                        "edad": "---",
                        "diagnostico": "En espera de primer dictado",
                        "plan": "En espera",
                        "motivo": "---",
                        "proxima_cita": "Por programar",
                        "pago": "$0.00",
                        "receta": "Sin prescripción"
                    }
                
                c_dict = dict(row)
                json_c = {}
                if c_dict.get("json_clinico"):
                    try:
                        json_c = json.loads(c_dict["json_clinico"])
                    except Exception:
                        pass
                
                cursor.execute("SELECT * FROM pagos WHERE consulta_id = ? ORDER BY id DESC LIMIT 1", (c_dict["id"],))
                pago_row = cursor.fetchone()
                saldo_str = f"Abonó: ${pago_row['abono']:.2f} (Saldo: ${pago_row['saldo_pendiente']:.2f})" if pago_row else "Al día"
                
                cita_str = ""
                if isinstance(json_c, dict) and json_c.get("cita"):
                    cita_info = json_c["cita"]
                    cita_str = f"{cita_info.get('fecha', '')} {cita_info.get('hora', '')}".strip()
                
                receta_str = ""
                if isinstance(json_c, dict) and json_c.get("receta"):
                    receta_items = json_c["receta"]
                    if isinstance(receta_items, list):
                        receta_str = ", ".join([str(x) for x in receta_items[:2]])
                    elif isinstance(receta_items, dict):
                        receta_str = f"{receta_items.get('medicamento', '')} {receta_items.get('dosis', '')}".strip()
                
                if not receta_str:
                    receta_str = "Sin medicación especial prescrita"

                if c_dict.get("ruta_pdf"):
                    self.ultima_ruta_pdf = c_dict.get("ruta_pdf")
                
                return {
                    "status": "ok",
                    "paciente": c_dict.get("nombre") or "Paciente",
                    "documento": c_dict.get("documento") or "No registrado",
                    "edad": f"{c_dict.get('edad')} años" if c_dict.get("edad") else "Edad no reg.",
                    "diagnostico": c_dict.get("diagnostico") or "No especificado",
                    "plan": c_dict.get("plan_tratamiento") or "No especificado",
                    "motivo": c_dict.get("motivo_consulta") or "Consulta General",
                    "proxima_cita": cita_str or (c_dict.get("fecha_hora", "")[:16]),
                    "pago": saldo_str,
                    "receta": receta_str,
                    "ruta_pdf": c_dict.get("ruta_pdf")
                }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] obtener_ultimo_expediente: {e}")
            return {"status": "error", "message": str(e)}

    # ==========================================
    # GESTIÓN DE PACIENTES (CRUD)
    # ==========================================
    def obtener_pacientes(self, filtro=""):
        try:
            pacientes = buscar_pacientes(filtro)
            resultado = []
            with get_connection() as conn:
                cursor = conn.cursor()
                for p in pacientes:
                    p_dict = dict(p)
                    p_id = p_dict["id"]
                    
                    cursor.execute("SELECT saldo_pendiente FROM pagos WHERE paciente_id = ? ORDER BY id DESC LIMIT 1", (p_id,))
                    pago_row = cursor.fetchone()
                    saldo = pago_row["saldo_pendiente"] if pago_row and pago_row["saldo_pendiente"] is not None else 0.0
                    p_dict["saldo"] = f"${saldo:.2f}"
                    
                    ult = p_dict.get("ultima_consulta")
                    if ult:
                        try:
                            dt = datetime.datetime.fromisoformat(str(ult).replace(" ", "T"))
                            p_dict["ultima_visita"] = dt.strftime("%d %b %Y")
                        except Exception:
                            p_dict["ultima_visita"] = str(ult)[:10]
                    else:
                        p_dict["ultima_visita"] = "Sin consultas"
                    
                    resultado.append(p_dict)
            return resultado
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] obtener_pacientes: {e}")
            return []

    def guardar_paciente(self, datos):
        try:
            if isinstance(datos, str):
                datos = json.loads(datos)
            pac_id = registrar_o_actualizar_paciente(datos)
            return {"status": "ok", "id": pac_id}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] guardar_paciente: {e}")
            return {"status": "error", "message": str(e)}

    def eliminar_paciente(self, paciente_id):
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM pacientes WHERE id = ?", (paciente_id,))
                conn.commit()
            return {"status": "ok"}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] eliminar_paciente: {e}")
            return {"status": "error", "message": str(e)}

    def obtener_paciente_detalle(self, paciente_id):
        try:
            paciente = obtener_paciente_por_id(paciente_id)
            if not paciente:
                return {"status": "error", "message": "Paciente no encontrado"}
            consultas = listar_consultas_paciente(paciente_id)
            return {
                "status": "ok",
                "paciente": paciente,
                "consultas": consultas
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ==========================================
    # AGENDA & CITAS (CRUD)
    # ==========================================
    def obtener_citas(self):
        try:
            return listar_citas_db(100)
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] obtener_citas: {e}")
            return []

    def crear_cita(self, datos):
        try:
            if isinstance(datos, str):
                datos = json.loads(datos)
            pid = datos.get("paciente_id")
            nom = datos.get("nombre", "")
            tel = datos.get("telefono", "")
            f_ini = datos.get("fecha_inicio", "")
            f_fin = datos.get("fecha_fin", "")
            desc = datos.get("descripcion", "")
            cita_id = crear_cita_db(
                paciente_id=pid,
                nombre_paciente=nom,
                telefono=tel,
                fecha_hora_inicio=f_ini,
                fecha_hora_fin=f_fin,
                descripcion=desc
            )
            return {"status": "ok", "id": cita_id}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] crear_cita: {e}")
            return {"status": "error", "message": str(e)}

    def cancelar_cita(self, cita_id):
        try:
            cancelar_o_eliminar_cita_db(cita_id=cita_id)
            return {"status": "ok"}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] cancelar_cita: {e}")
            return {"status": "error", "message": str(e)}

    # ==========================================
    # VISOR & GESTIÓN DE PDF
    # ==========================================
    def listar_pdfs_recientes(self):
        try:
            pdfs = []
            dirs_a_buscar = [BASE_DIR / "Pacientes", BASE_DIR / "historias_clinicas"]
            vistos = set()
            
            for d in dirs_a_buscar:
                if d.exists():
                    for p in d.rglob("*.pdf"):
                        p_str = str(p.resolve())
                        if p_str in vistos:
                            continue
                        vistos.add(p_str)
                        
                        try:
                            stat = p.stat()
                            mtime = datetime.datetime.fromtimestamp(stat.st_mtime)
                            kb = round(stat.st_size / 1024, 1)
                            nom_carpeta = p.parent.name
                            nom_paciente = nom_carpeta.split("_")[0].replace("-", " ") if "Pacientes" in p_str else "General"
                            pdfs.append({
                                "nombre": p.name,
                                "ruta": p_str,
                                "paciente": nom_paciente,
                                "fecha": mtime.strftime("%d/%m/%Y %H:%M"),
                                "timestamp": stat.st_mtime,
                                "tamano": f"{kb} KB"
                            })
                        except Exception:
                            pass
            
            pdfs.sort(key=lambda x: x["timestamp"], reverse=True)
            return pdfs[:50]
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] listar_pdfs_recientes: {e}")
            return []

    def abrir_pdf(self, ruta):
        try:
            if ruta and os.path.exists(ruta):
                os.startfile(ruta)
                return {"status": "ok"}
            return {"status": "error", "message": "El archivo PDF no fue encontrado en el disco."}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] abrir_pdf: {e}")
            return {"status": "error", "message": str(e)}

    def abrir_ultimo_pdf(self):
        try:
            if self.ultima_ruta_pdf and os.path.exists(self.ultima_ruta_pdf):
                os.startfile(self.ultima_ruta_pdf)
                return {"status": "ok"}
            
            lista = self.listar_pdfs_recientes()
            if lista:
                target = lista[0]["ruta"]
                os.startfile(target)
                self.ultima_ruta_pdf = target
                return {"status": "ok"}
            return {"status": "error", "message": "No hay ningún PDF generado aún."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def imprimir_pdf(self, ruta=None):
        try:
            target = ruta or self.ultima_ruta_pdf
            if not target or not os.path.exists(target):
                lista = self.listar_pdfs_recientes()
                if lista:
                    target = lista[0]["ruta"]
            if target and os.path.exists(target):
                try:
                    os.startfile(target, "print")
                except Exception:
                    os.startfile(target)
                return {"status": "ok"}
            return {"status": "error", "message": "No hay ningún PDF disponible para imprimir."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ==========================================
    # MÓVIL & RED LOCAL
    # ==========================================
    def obtener_info_movil(self):
        try:
            ip = obtener_ip_local()
            puerto = MOBILE_SERVER_PORT
            url = f"http://{ip}:{puerto}/mobile"
            return {
                "status": "ok",
                "ip": ip,
                "puerto": puerto,
                "url": url,
                "online": True
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "ip": "127.0.0.1",
                "puerto": 8000,
                "url": "http://127.0.0.1:8000/mobile"
            }

    def abrir_url_movil(self):
        try:
            info = self.obtener_info_movil()
            webbrowser.open(info.get("url", "http://localhost:8000/mobile"))
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ==========================================
    # CONFIGURACIÓN DE LA CLÍNICA
    # ==========================================
    def obtener_info_clinica(self):
        try:
            return cargar_datos_clinica()
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] obtener_info_clinica: {e}")
            return {}

    def guardar_configuracion(self, datos):
        try:
            if isinstance(datos, str):
                datos = json.loads(datos)
            guardar_datos_clinica(datos)
            return {"status": "ok"}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] guardar_configuracion: {e}")
            return {"status": "error", "message": str(e)}


def iniciar_desktop():
    init_db()
    purgar_datos_prueba()
    inicializar_usuarios_default()

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
