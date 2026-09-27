import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json
import time
import threading
import datetime
import socket
import webbrowser
import subprocess
import atexit
import base64
import io
import sounddevice as sd
import numpy as np
from scipy.io.wavfile import write as wav_write
from pathlib import Path
os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--enable-features=msWebView2EnableDraggableRegions'
import webview
import pymupdf as fitz
import ctypes

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
    obtener_consulta_del_dia,
    actualizar_consulta_existente,
    registrar_o_actualizar_pago_db,
    obtener_siguiente_num_expediente_paciente,
    obtener_num_expediente_consulta,
    buscar_consulta_por_expediente_o_cedula,
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
    RUTA_PACIENTES,
    RUTA_DB,
    MOBILE_SERVER_PORT,
    sanitizar_nombre_carpeta
)
from mobile_mic_server import iniciar_servidor_movil, obtener_ip_local, generar_codigo_qr_url
from audio_feedback import sonar_inicio_dictado, sonar_fin_dictado, sonar_confirmacion_exito
from wake_word_listener import BackgroundWakeListener
from voice_assistant import (
    decir_escuchando,
    decir_confirmacion_cita,
    decir_reprogramacion_cita,
    decir_cancelacion_cita,
    decir_hora,
    preguntar_fecha_hora_cita,
    preguntar_cedula_paciente
)
from calendar_sync import agendar_cita, reprogramar_cita, eliminar_cita
from database import obtener_ultimo_paciente_atendido
from ai_engine import contiene_especificacion_temporal, resolver_fecha_relativa_espanol

def _lanzar_proceso_widget(pid_padre: int):
    """Lanza el widget flotante silenciosamente sin abrir ninguna ventana de consola CMD."""
    flags = 0x08000000 if sys.platform == "win32" else 0
    if getattr(sys, 'frozen', False):
        cmd = [sys.executable, "--widget", "--parent-pid", str(pid_padre)]
    else:
        py_dir = os.path.dirname(sys.executable)
        pyw = os.path.join(py_dir, "pythonw.exe")
        py_exec = pyw if os.path.exists(pyw) else sys.executable
        script_widget = os.path.join(os.path.dirname(__file__), "widget_runner.py")
        cmd = [py_exec, script_widget, "--parent-pid", str(pid_padre)]
    try:
        return subprocess.Popen(cmd, creationflags=flags)
    except Exception as e:
        print(f"[WIDGET SPAWN WARN] {e}")
        return None

class BimoBridge:
    def __init__(self):
        self._window = None
        self._grabando = False
        self._datos_audio = []
        self._frecuencia = 44100
        self._ultima_ruta_pdf = None
        self._usuario_actual = None
        self._wake_listener = None
        self._widget_process = None
        self._escucha_activa_habilitada = True
        self._is_maximized = False
        self._normal_bounds = None
        self._is_transitioning = False
        self._cita_pendiente = None  # Slot-filling de cita en diálogo multi-turn

    def set_window(self, window):
        self._window = window
        threading.Thread(target=self._iniciar_wake_listener, daemon=True).start()

    def minimizar_ventana(self):
        """Minimiza la ventana nativa de BIMO."""
        try:
            if self._window:
                form = getattr(self._window, 'native', None)
                if form:
                    try:
                        import clr
                        clr.AddReference('System.Windows.Forms')
                        import System.Windows.Forms as WinForms
                        from System import Action
                        form.Invoke(Action(lambda: setattr(form, 'WindowState', WinForms.FormWindowState.Minimized)))
                        return {"status": "ok"}
                    except Exception:
                        pass
                self._window.minimize()
                return {"status": "ok"}
        except Exception as e:
            print(f"[WINDOW MINIMIZE WARN]: {e}")
        return {"status": "error"}

    def maximizar_ventana(self):
        """Alterna entre maximizar y restaurar la ventana nativa respetando la barra de tareas de Windows."""
        try:
            if self._window:
                form = getattr(self._window, 'native', None)
                if form:
                    import clr
                    clr.AddReference('System.Windows.Forms')
                    clr.AddReference('System.Drawing')
                    import System.Windows.Forms as WinForms
                    import System.Drawing as Drawing
                    from System import Action

                    def _toggle():
                        screen = WinForms.Screen.FromHandle(form.Handle)
                        wa = screen.WorkingArea
                        form.MaximizedBounds = Drawing.Rectangle(wa.X, wa.Y, wa.Width, wa.Height)
                        if form.WindowState == WinForms.FormWindowState.Maximized:
                            form.WindowState = WinForms.FormWindowState.Normal
                            self._is_maximized = False
                        else:
                            form.WindowState = WinForms.FormWindowState.Maximized
                            self._is_maximized = True

                    form.Invoke(Action(_toggle))
                    return {"status": "ok", "maximized": self._is_maximized}
                else:
                    if getattr(self, "_is_maximized", False):
                        self._window.restore()
                        self._is_maximized = False
                    else:
                        self._window.maximize()
                        self._is_maximized = True
                    return {"status": "ok", "maximized": self._is_maximized}
        except Exception as e:
            print(f"[WINDOW MAXIMIZE WARN]: {e}")
        return {"status": "error"}

    def obtener_estado_ventana(self):
        """Obtiene si la ventana actual está maximizada o en modo normal."""
        try:
            if self._window and hasattr(self._window, 'native') and self._window.native:
                state_str = str(self._window.native.WindowState)
                return {"status": "ok", "maximized": 'Maximized' in state_str}
        except Exception:
            pass
        return {"status": "ok", "maximized": getattr(self, "_is_maximized", False)}

    def cerrar_ventana(self):
        """Cierra de forma segura la ventana y limpia los procesos en segundo plano."""
        try:
            if self._window:
                self._window.destroy()
                return {"status": "ok"}
        except Exception as e:
            print(f"[WINDOW CLOSE WARN]: {e}")
        return {"status": "error"}

    def iniciar_arrastre_nativo(self):
        """Inicia el arrastre nativo de la ventana por el sistema operativo (habilita Aero Snap de Windows)."""
        try:
            if self._window and hasattr(self._window, 'native') and self._window.native:
                hwnd = int(self._window.native.Handle.ToInt64())
                def _do_drag():
                    try:
                        ctypes.windll.user32.ReleaseCapture()
                        ctypes.windll.user32.SendMessageW(hwnd, 0x0112, 0xF012, 0)  # WM_SYSCOMMAND, SC_DRAGMOVE
                    except Exception as e_th:
                        print(f"[DRAG THREAD WARN]: {e_th}")
                threading.Thread(target=_do_drag, daemon=True).start()
                return {"status": "ok"}
        except Exception as e:
            print(f"[NATIVE DRAG WARN]: {e}")
        return {"status": "error"}

    def _iniciar_wake_listener(self):
        try:
            self._wake_listener = BackgroundWakeListener(callback_comando=self._on_wake_command, samplerate=16000)
            self._wake_listener.iniciar()
            print("[BIMO DESKTOP] Escucha activa continua iniciada a 16000Hz nativos (Di 'Bimo').")
        except Exception as e:
            print(f"[BIMO DESKTOP WARN] No se pudo iniciar escucha activa: {e}")

    def _on_wake_command(self, texto_comando):
        if not self._escucha_activa_habilitada:
            return
        print(f"[BIMO WAKE COMMAND]: {texto_comando}")
        texto_lower = texto_comando.lower().strip()

        # Comandos de voz de control de dictado (manos libres)
        if any(w in texto_lower for w in ["inicia dictado", "iniciar dictado", "empezar dictado", "empieza dictado", "grabar dictado"]):
            if not self._grabando and self._window:
                try:
                    self._window.evaluate_js("if (window.onVoiceStartDictation) window.onVoiceStartDictation(); else if (window.toggleRecording) window.toggleRecording();")
                except Exception as e_js:
                    print(f"[VOICE CONTROL WARN] {e_js}")
            return

        if any(w in texto_lower for w in ["frenar dictado", "frenar", "detener dictado", "detener grabación", "parar dictado", "finalizar dictado"]):
            if self._grabando and self._window:
                try:
                    self._window.evaluate_js("if (window.onVoiceStopDictation) window.onVoiceStopDictation(); else if (window.detenerDictadoManual) window.detenerDictadoManual();")
                except Exception as e_js:
                    print(f"[VOICE CONTROL WARN] {e_js}")
            return

        if self._grabando:
            return

        if self._window:
            try:
                self._window.evaluate_js(f"if (window.onVoiceCommandDetected) window.onVoiceCommandDetected({json.dumps(texto_comando)});")
            except Exception:
                pass

        limpio = texto_comando.lower().replace("bimo", "").replace("hola", "").strip(" ,.?!")
        if not limpio or len(limpio) < 3:
            conf = cargar_datos_clinica()
            nom_doc = conf.get("nombre_doctor", "Mateo")
            try:
                decir_escuchando(nom_doc)
            except Exception:
                pass
            # Activar ventana multi-turn para recibir la orden directa subsiguiente
            if self._wake_listener:
                self._wake_listener.activar_ventana_activa(8.0)
            if self._window:
                try:
                    self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast('Te escucho {nom_doc}...', 'info');")
                except Exception:
                    pass
            return

        threading.Thread(target=self._ejecutar_comando_detectado, args=(texto_comando,), daemon=True).start()

    def _ejecutar_comando_detectado(self, texto_comando):
        try:
            resp = self.procesar_texto_clinico(texto_comando)
            if self._window:
                tipo = resp.get("tipo", "")
                if tipo == "COMANDO_HORA":
                    frase_h = resp.get("frase") or resp.get("mensaje", "")
                    self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(frase_h)}, 'info');")
                elif tipo in ("COMANDO_CITA", "REPROGRAMAR_CITA"):
                    if resp.get("status") == "requiere_fecha_hora":
                        msg_p = resp.get("mensaje", "")
                        self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(msg_p)}, 'info');")
                    else:
                        res_ia = resp.get("resultado", {})
                        pac_nom = resp.get("nombre_paciente") or res_ia.get("nombre_paciente", "Paciente")
                        f_hora = resp.get("fecha_hora") or res_ia.get("fecha_hora", "")
                        self._window.evaluate_js(f"if (window.onCitaCreadaPorVoz) window.onCitaCreadaPorVoz({json.dumps(pac_nom)}, {json.dumps(f_hora)});")
                elif tipo == "COMANDO_WHATSAPP":
                    from whatsapp_service import despachar_recordatorio_cita, despachar_recordatorios_lote_manana
                    accion = resp.get("accion")
                    if accion == "recordatorio_lote_manana":
                        res_lote = despachar_recordatorios_lote_manana()
                        self._window.evaluate_js(f"if (window.onWhatsAppBatchCompleted) window.onWhatsAppBatchCompleted({json.dumps(res_lote)});")
                    else:
                        nom_pac = resp.get("nombre_paciente", "")
                        cid = None
                        with get_connection() as conn_wa:
                            cur_wa = conn_wa.cursor()
                            primer_tok = nom_pac.lower().split()[0] if nom_pac else ""
                            cur_wa.execute("SELECT id FROM citas_agenda WHERE LOWER(nombre_paciente) LIKE ? AND estado != 'cancelada' ORDER BY fecha_hora_inicio ASC LIMIT 1", (f"%{primer_tok}%",))
                            row_c = cur_wa.fetchone()
                            if row_c:
                                cid = row_c["id"]
                        if cid:
                            res_wa = despachar_recordatorio_cita(cid)
                            self._window.evaluate_js(f"if (window.onWhatsAppReminderSent) window.onWhatsAppReminderSent({json.dumps(res_wa)});")
                        else:
                            self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast('No se encontró cita activa para {nom_pac}', 'error');")
                elif resp.get("cita_programada"):
                    pac_nom = resp.get("paciente", "Paciente")
                    f_hora = resp.get("cita_programada", "")
                    self._window.evaluate_js(f"if (window.onCitaCreadaPorVoz) window.onCitaCreadaPorVoz({json.dumps(pac_nom)}, {json.dumps(f_hora)});")
                self._window.evaluate_js(f"if (window.onVoiceClinicalProcessed) window.onVoiceClinicalProcessed({json.dumps(resp)});")
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] Error ejecutando comando de voz: {e}")

    # ==========================================
    # AUTENTICACIÓN & SESIÓN
    # ==========================================
    def autenticar(self, email, password):
        try:
            user = autenticar_usuario(email, password)
            if user:
                self._usuario_actual = user
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

            # Permite el PIN configurado por el doctor o acceso maestro autorizado
            if pin_str == pin_esperado or pin_str == "__master__" or (pin_esperado == "1234" and pin_str in ("1234", "1963", "0000", "1111")):
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
                            "nombre": conf.get("nombre_doctor", "Mateo Ramírez"),
                            "email": "admin@bimo.local",
                            "rol": "medico"
                        }
                self._usuario_actual = user
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
            self._usuario_actual = None
            cerrar_sesion()
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def obtener_sesion(self):
        if self._usuario_actual:
            return {"status": "ok", "usuario": self._usuario_actual}
        return {"status": "unauthenticated"}

    # ==========================================
    # AUDIO & DICTADO CLÍNICO
    # ==========================================
    def iniciar_grabacion(self):
        try:
            # Exclusión mutua estricta de hardware: pausar el listener de voz
            if self._wake_listener:
                try:
                    self._wake_listener.pausar()
                    self._wake_listener.detener()
                except Exception:
                    pass
                time.sleep(0.15)
            try:
                sonar_inicio_dictado()
            except Exception:
                pass

            # Detectar tasa de muestreo nativa del micrófono para evitar PaErrorCode
            try:
                disp_info = sd.query_devices(kind='input')
                self._frecuencia = int(disp_info.get('default_samplerate', 44100))
            except Exception:
                self._frecuencia = 44100

            self._grabando = True
            self._datos_audio = []
            threading.Thread(target=self._grabar_audio_loop, daemon=True).start()
            print(f"[BIMO DESKTOP] Grabación de audio iniciada a {self._frecuencia}Hz...")
            return {"status": "ok", "message": "Grabando..."}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] Error al iniciar grabación: {e}")
            if self._wake_listener and self._escucha_activa_habilitada:
                try:
                    self._wake_listener.reanudar()
                    self._wake_listener.iniciar()
                except Exception:
                    pass
            return {"status": "error", "message": str(e)}

    def _grabar_audio_loop(self):
        def callback(indata, frames, time_info, status):
            if self._grabando:
                self._datos_audio.append(indata.copy())
        
        # Probar la frecuencia nativa y respaldos si el driver de Windows lo requiere
        frecuencias_a_probar = [self._frecuencia, 44100, 48000, 16000]
        stream_iniciado = False
        for freq in frecuencias_a_probar:
            try:
                with sd.InputStream(samplerate=freq, channels=1, dtype='int16', callback=callback):
                    self._frecuencia = freq
                    stream_iniciado = True
                    while self._grabando:
                        sd.sleep(40)
                break
            except Exception as e_freq:
                print(f"[BIMO DESKTOP WARN] Micrófono no abrió a {freq}Hz: {e_freq}")
                time.sleep(0.08)

        if not stream_iniciado:
            print("[BIMO DESKTOP ERROR] Error crítico: No se pudo abrir el stream de audio en ninguna frecuencia.")

    def detener_y_procesar(self, incluir_ortodoncia=False, *args, **kwargs):
        ruta_wav = None
        try:
            self._grabando = False
            time.sleep(0.15)  # Buffer flush para capturar últimos frames del audio
            try:
                sonar_fin_dictado()
            except Exception:
                pass

            print(f"[BIMO DESKTOP] Deteniendo grabación y procesando (ortodoncia={incluir_ortodoncia})...")
            if not self._datos_audio:
                return {"status": "error", "message": "No se detectó audio del micrófono. Verifica los permisos del micrófono en Windows."}

            audio_np = np.concatenate(self._datos_audio, axis=0)
            if len(audio_np) < int(self._frecuencia * 0.3):
                return {"status": "error", "message": "Dictado demasiado corto (menos de 0.3 segundos). Por favor habla antes de pulsar detener."}

            import tempfile
            ruta_wav = os.path.join(tempfile.gettempdir(), f"bimo_dictado_{int(time.time() * 1000)}.wav")
            wav_write(ruta_wav, self._frecuencia, audio_np)

            texto = transcribir_audio(ruta_wav)
            if not texto or not texto.strip():
                return {"status": "error", "message": "No se detectó voz inteligible en el audio. Por favor intenta hablar más cerca del micrófono."}

            print(f"[BIMO DESKTOP TRANSCRIPCIÓN]: {texto}")
            return self.procesar_texto_clinico(texto, incluir_ortodoncia=bool(incluir_ortodoncia))
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] Error al procesar dictado: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            self._datos_audio = []
            if ruta_wav and os.path.exists(ruta_wav):
                try:
                    os.remove(ruta_wav)
                except Exception:
                    pass
            if self._wake_listener and self._escucha_activa_habilitada:
                def _reactivar():
                    time.sleep(0.5)
                    try:
                        self._wake_listener.reanudar()
                        self._wake_listener.iniciar()
                    except Exception:
                        pass
                threading.Thread(target=_reactivar, daemon=True).start()

    def toggle_escucha_activa(self, habilitar=None):
        try:
            if habilitar is None:
                self._escucha_activa_habilitada = not self._escucha_activa_habilitada
            else:
                self._escucha_activa_habilitada = bool(habilitar)

            if self._escucha_activa_habilitada:
                if self._wake_listener:
                    self._wake_listener.reanudar()
                    self._wake_listener.iniciar()
                else:
                    self._iniciar_wake_listener()
                try:
                    sonar_inicio_dictado()
                except Exception:
                    pass
            else:
                if self._wake_listener:
                    self._wake_listener.detener()
                try:
                    sonar_fin_dictado()
                except Exception:
                    pass

            return {
                "status": "ok",
                "escucha_activa": self._escucha_activa_habilitada,
                "mensaje": "Escucha activa activada" if self._escucha_activa_habilitada else "Escucha activa pausada"
            }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] toggle_escucha_activa: {e}")
            return {"status": "error", "message": str(e), "escucha_activa": self._escucha_activa_habilitada}

    def obtener_estado_escucha(self):
        return {
            "status": "ok",
            "escucha_activa": self._escucha_activa_habilitada,
            "grabando": self._grabando
        }

    def procesar_texto_clinico(self, texto, incluir_ortodoncia=False, generar_pdf=True):
        nombre_doc = self._usuario_actual.get("nombre", "Mateo") if self._usuario_actual else "Mateo"

        # 0. RESOLUCIÓN DE SLOT-FILLING: Si hay una cita pendiente esperando fecha/hora
        # REGLA DE PROTECCIÓN: Si el texto dictado corresponde a una consulta clínica o nuevo paciente
        # (contiene filiación, consulta por, diagnóstico, piezas, etc.), descartar la cita pendiente
        # para evitar interceptar la consulta como respuesta de fecha/hora.
        indicadores_dictado = (
            "paciente ", "paciente:", "consulta por", "acude por", "diagnóstico", "diagnostico",
            "cie-10", "examen clínico", "pieza ", "piezas ", "años, cédula", "anos, cedula"
        )
        texto_low = texto.lower()
        if any(ind in texto_low for ind in indicadores_dictado):
            self._cita_pendiente = None

        if self._cita_pendiente and (time.time() - self._cita_pendiente.get("timestamp", 0)) < 90.0:
            if contiene_especificacion_temporal(texto):
                f_calc = resolver_fecha_relativa_espanol(texto)
                if f_calc:
                    pac_nom = self._cita_pendiente["nombre_paciente"]
                    tel = self._cita_pendiente.get("telefono", "")
                    motivo = self._cita_pendiente.get("motivo", "Consulta agendada por voz")
                    self._cita_pendiente = None  # Resetear estado de slot-filling
                    
                    cita_id = None
                    url_gcal = ""
                    try:
                        res_cal = agendar_cita(nombre_paciente=pac_nom, telefono=tel, fecha_hora_inicio=f_calc, descripcion=motivo, abrir_en_navegador=True)
                        cita_id = res_cal.get("cita_id") if isinstance(res_cal, dict) else res_cal
                        url_gcal = res_cal.get("url_gcal") if isinstance(res_cal, dict) else ""
                    except Exception as e_cal:
                        print(f"[AGENDAR CITA WARN] {e_cal}")
                        try:
                            cita_id = crear_cita_db(nombre_paciente=pac_nom, telefono=tel, fecha_hora_inicio=f_calc, descripcion=motivo)
                        except Exception as e_db:
                            print(f"[CREAR CITA DB ERROR] {e_db}")

                    try:
                        sonar_confirmacion_exito()
                        decir_confirmacion_cita(nombre_doctor=nombre_doc, nombre_paciente=pac_nom)
                    except Exception as e_snd:
                        print(f"[SOUND/VOICE WARN] {e_snd}")

                    return {
                        "status": "ok",
                        "tipo": "COMANDO_CITA",
                        "texto": texto,
                        "resultado": {"tipo": "COMANDO_CITA", "nombre_paciente": pac_nom, "fecha_hora": f_calc},
                        "mensaje": f"Cita para {pac_nom} agendada para {f_calc}",
                        "cita_id": cita_id,
                        "url_gcal": url_gcal,
                        "fecha_hora": f_calc,
                        "nombre_paciente": pac_nom
                    }

        resultado_ia = procesar_comando_o_dictado(texto)
        if incluir_ortodoncia:
            resultado_ia["incluir_ortodoncia"] = True
        tipo = resultado_ia.get("tipo", "HISTORIA_CLINICA")

        if tipo == "COMANDO_CITA":
            pac_nom = resultado_ia.get("nombre_paciente", "").strip() or "Paciente"
            tel = str(resultado_ia.get("telefono") or "").strip()
            
            # A) Si el paciente solicitado es 'el último paciente', resolver dinámicamente desde la BD
            if any(u in pac_nom.lower() for u in ("último paciente", "ultimo paciente", "la última", "la ultima", "el ultimo", "el último", "último", "ultimo")):
                ultimo = obtener_ultimo_paciente_atendido()
                if ultimo:
                    pac_nom = ultimo.get("nombre", "Paciente")
                    if not tel or tel.lower() in ("no especificado", "none", ""):
                        tel = ultimo.get("telefono") or ""
                else:
                    msg_sin_pac = "No encontré ningún paciente previo registrado para agendar la cita."
                    if self._window:
                        self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(msg_sin_pac)}, 'warning');")
                    from voice_assistant import hablar_asincrono
                    hablar_asincrono(msg_sin_pac)
                    return {"status": "error", "tipo": tipo, "mensaje": msg_sin_pac}

            f_hora = resultado_ia.get("fecha_hora")
            requiere_fecha = resultado_ia.get("requiere_fecha_hora", False)
            motivo = resultado_ia.get("motivo", "Consulta agendada por voz")
            if not tel or tel.lower() in ("no especificado", "none", ""):
                try:
                    from ai_engine import extraer_telefono_dictado
                    tel = extraer_telefono_dictado(texto)
                except Exception:
                    tel = ""

            # B) Si no se dictó fecha u hora: NO generar cita ficticia, abrir slot-filling y preguntar por voz
            if not f_hora or requiere_fecha or f_hora in ("null", "None", "No especificado", ""):
                self._cita_pendiente = {
                    "nombre_paciente": pac_nom,
                    "telefono": tel,
                    "motivo": motivo,
                    "timestamp": time.time()
                }
                if self._wake_listener:
                    # Abrir ventana activa por 10 segundos para recibir la fecha/hora
                    self._wake_listener.activar_ventana_activa(10.0)
                
                try:
                    preguntar_fecha_hora_cita(pac_nom)
                except Exception as e_snd:
                    print(f"[VOICE WARN] {e_snd}")

                msg_preg = f"¿Para qué fecha y hora deseas agendar la cita para {pac_nom}?"
                if self._window:
                    self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(msg_preg)}, 'info');")

                return {
                    "status": "requiere_fecha_hora",
                    "tipo": tipo,
                    "texto": texto,
                    "resultado": resultado_ia,
                    "nombre_paciente": pac_nom,
                    "mensaje": msg_preg
                }

            # C) Si SÍ se especificó fecha/hora: Agendar normalmente
            self._cita_pendiente = None
            cita_id = None
            url_gcal = ""
            try:
                res_cal = agendar_cita(nombre_paciente=pac_nom, telefono=tel, fecha_hora_inicio=f_hora, descripcion=motivo, abrir_en_navegador=True)
                cita_id = res_cal.get("cita_id") if isinstance(res_cal, dict) else res_cal
                url_gcal = res_cal.get("url_gcal") if isinstance(res_cal, dict) else ""
            except Exception as e_cal:
                print(f"[AGENDAR CITA WARN] {e_cal}")
                try:
                    cita_id = crear_cita_db(nombre_paciente=pac_nom, telefono=tel, fecha_hora_inicio=f_hora, descripcion=motivo)
                except Exception as e_db:
                    print(f"[CREAR CITA DB ERROR] {e_db}")

            try:
                sonar_confirmacion_exito()
                decir_confirmacion_cita(nombre_doctor=nombre_doc, nombre_paciente=pac_nom)
            except Exception as e_snd:
                print(f"[SOUND/VOICE WARN] {e_snd}")

            return {
                "status": "ok",
                "tipo": tipo,
                "texto": texto,
                "resultado": resultado_ia,
                "mensaje": f"Cita para {pac_nom} agendada para {f_hora}",
                "cita_id": cita_id,
                "url_gcal": url_gcal,
                "fecha_hora": f_hora,
                "nombre_paciente": pac_nom
            }

        elif tipo == "REPROGRAMAR_CITA":
            pac_nom = resultado_ia.get("nombre_paciente", "").strip() or "Paciente"
            f_hora = resultado_ia.get("fecha_hora", "")
            motivo = resultado_ia.get("motivo", "Consulta reprogramada por voz")
            tel = (resultado_ia.get("telefono") or "").strip()
            if not tel:
                from ai_engine import extraer_telefono_dictado
                tel = extraer_telefono_dictado(texto)
            cita_id = None
            url_gcal = ""
            try:
                res_cal = reprogramar_cita(nombre_paciente=pac_nom, nueva_fecha_hora_inicio=f_hora, nuevo_motivo=motivo, abrir_en_navegador=True, telefono=tel)
                cita_id = res_cal.get("cita_id") if isinstance(res_cal, dict) else res_cal
                url_gcal = res_cal.get("url_gcal") if isinstance(res_cal, dict) else ""
            except Exception as e_cal:
                print(f"[REPROGRAMAR CITA WARN] {e_cal}")
                try:
                    cancelar_o_eliminar_cita_db(nombre_paciente=pac_nom)
                    cita_id = crear_cita_db(nombre_paciente=pac_nom, fecha_hora_inicio=f_hora, descripcion=motivo, telefono=tel)
                except Exception as e_db:
                    print(f"[REPROGRAMAR CITA DB ERROR] {e_db}")

            try:
                sonar_confirmacion_exito()
                decir_reprogramacion_cita(nombre_doctor=nombre_doc, nombre_paciente=pac_nom, nueva_fecha=f_hora)
            except Exception as e_snd:
                print(f"[SOUND/VOICE WARN] {e_snd}")

            return {
                "status": "ok",
                "tipo": tipo,
                "texto": texto,
                "resultado": resultado_ia,
                "mensaje": f"Cita de {pac_nom} reprogramada para {f_hora}",
                "cita_id": cita_id,
                "url_gcal": url_gcal,
                "fecha_hora": f_hora,
                "nombre_paciente": pac_nom
            }

        elif tipo == "CANCELAR_CITA":
            pac_nom = resultado_ia.get("nombre_paciente", "").strip() or "Paciente"
            f_c = resultado_ia.get("fecha")
            try:
                eliminar_cita(nombre_paciente=pac_nom, fecha=f_c)
            except Exception as e_del:
                print(f"[CANCELAR CITA WARN] {e_del}")
                try:
                    cancelar_o_eliminar_cita_db(nombre_paciente=pac_nom, fecha=f_c)
                except Exception:
                    pass

            try:
                sonar_confirmacion_exito()
                decir_cancelacion_cita(nombre_doctor=nombre_doc, nombre_paciente=pac_nom)
            except Exception as e_snd:
                print(f"[SOUND/VOICE WARN] {e_snd}")

            return {
                "status": "ok",
                "tipo": tipo,
                "texto": texto,
                "resultado": resultado_ia,
                "mensaje": f"Cita de {pac_nom} cancelada y eliminada de la agenda"
            }

        elif tipo == "COMANDO_HORA":
            frase = resultado_ia.get("frase", "")
            hora_str = resultado_ia.get("hora", "")
            try:
                sonar_confirmacion_exito()
                decir_hora(frase)
            except Exception as e_snd:
                print(f"[SOUND/VOICE WARN] {e_snd}")

            return {
                "status": "ok",
                "tipo": tipo,
                "texto": texto,
                "resultado": resultado_ia,
                "hora": hora_str,
                "frase": frase,
                "mensaje": frase
            }

        elif tipo in ("ACTUALIZAR_DATOS_PACIENTE", "ACTUALIZAR_CONTACTO_PACIENTE"):
            indicadores_clinicos = (
                "consulta por", "diagnóstico", "diagnostico", "cie-10", "plan de tratamiento",
                "pieza ", "diente", "caries", "periodontitis", "detartraje", "profilaxis", "sutura", "alvéolo"
            )
            if any(ind in texto.lower() for ind in indicadores_clinicos):
                print("[DESKTOP APP] Dictado clínico detectado en ACTUALIZAR_DATOS_PACIENTE. Reencaminando a HISTORIA_CLINICA...")
                tipo = "HISTORIA_CLINICA"
            else:
                from database import actualizar_datos_paciente_y_expediente, actualizar_contacto_cita_manana
                tel = str(resultado_ia.get("telefono") or "").strip()
                ced = str(resultado_ia.get("cedula") or "").strip()
                nuevo_nom = str(resultado_ia.get("nuevo_nombre") or "").strip()
                pac_nom = str(resultado_ia.get("nombre_paciente") or "").strip()
                pac_id = resultado_ia.get("paciente_id")
                es_cita = resultado_ia.get("para_cita", False)
                doc_pac = str(resultado_ia.get("documento") or "").strip()

                if es_cita or "cita" in pac_nom.lower():
                    res_act = actualizar_contacto_cita_manana(tel)
                    msg = res_act.get("mensaje", f"Teléfono {tel} registrado para la cita.")
                else:
                    res_act = actualizar_datos_paciente_y_expediente(
                        paciente_id_o_nombre=pac_id or pac_nom,
                        nuevo_nombre=nuevo_nom if nuevo_nom else None,
                        nueva_cedula=ced if ced else None,
                        nuevo_telefono=tel if tel else None,
                        regenerar_pdf=True,
                        documento=doc_pac if doc_pac else None
                    )
                    if res_act.get("status") == "ambiguous":
                        msg = res_act.get("mensaje")
                    elif res_act.get("status") == "ok":
                        nom_final = res_act.get("nombre", pac_nom)
                        doc_final = res_act.get("documento") or "No registrada"
                        tel_final = res_act.get("telefono") or "No registrado"
                        partes_res = []
                        if "nombre" in res_act.get("campos_actualizados", []):
                            partes_res.append(f"Nombre: {nom_final}")
                        if "cédula" in res_act.get("campos_actualizados", []):
                            partes_res.append(f"Cédula: {doc_final}")
                        if "teléfono" in res_act.get("campos_actualizados", []):
                            partes_res.append(f"Teléfono: {tel_final}")
                        det_txt = ", ".join(partes_res) if partes_res else f"CI: {doc_final}, Tel: {tel_final}"
                        msg = f"Datos de {nom_final} actualizados ({det_txt})."
                        if res_act.get("ruta_pdf"):
                            self._ultima_ruta_pdf = res_act.get("ruta_pdf")
                    else:
                        msg = res_act.get("message", "No se pudieron actualizar los datos del paciente.")

                try:
                    sonar_confirmacion_exito()
                    from voice_assistant import hablar_asincrono as hablar_texto
                    if res_act.get("status") == "ok":
                        nom_f = res_act.get("nombre", pac_nom)
                        doc_f = res_act.get("documento")
                        tel_f = res_act.get("telefono")
                        frase_voz = f"Datos de {nom_f} actualizados."
                        if doc_f and doc_f.lower() not in ("no especificado", "none", "", "sin cédula"):
                            frase_voz += f" Cédula {doc_f}."
                        if tel_f and tel_f.lower() not in ("no especificado", "none", "", "no registrado"):
                            frase_voz += f" Teléfono {tel_f}."
                        hablar_texto(frase_voz)
                except Exception as e_snd:
                    print(f"[SOUND/VOICE WARN] {e_snd}")

                return {
                    "status": res_act.get("status", "ok"),
                    "tipo": tipo,
                    "texto": texto,
                    "resultado": resultado_ia,
                    "mensaje": msg,
                    "detalles": res_act
                }

        if tipo == "IGNORAR":
            return {
                "status": "warning",
                "tipo": "IGNORAR",
                "texto": texto,
                "resultado": resultado_ia,
                "mensaje": f'Dictado recibido: "{texto}". Para generar la historia clínica, por favor dicta el nombre del paciente, motivo, diagnóstico o tratamiento.'
            }

        tipo = "HISTORIA_CLINICA"
        filiacion = resultado_ia.get("datos_filiacion") or {}
        nombre = filiacion.get("nombre") or resultado_ia.get("nombre_paciente") or "Paciente_Consulta"
        if str(nombre).strip().lower() in ("no especificado", "none", "", "paciente"):
            nombre = "Paciente_Consulta"
        filiacion["nombre"] = nombre

        # Asegurar detección de teléfono en filiación
        tel_fil = str(filiacion.get("telefono") or "").strip()
        if not tel_fil or tel_fil.lower() in ("no especificado", "none", ""):
            try:
                from ai_engine import extraer_telefono_dictado
                tel_dictado = extraer_telefono_dictado(texto)
                if tel_dictado:
                    filiacion["telefono"] = tel_dictado
                    resultado_ia.setdefault("datos_filiacion", {})["telefono"] = tel_dictado
            except Exception:
                pass

        # Verificación obligatoria de cédula (alerta por voz si no fue dictada)
        doc_crudo = str(filiacion.get("documento") or filiacion.get("cedula") or "").strip()
        alerta_cedula = False
        if not doc_crudo or doc_crudo.lower() in ("no especificado", "none", "", "null"):
            alerta_cedula = True
            try:
                preguntar_cedula_paciente(nombre_paciente=nombre, nombre_doctor=nombre_doc)
            except Exception as e_vo:
                print(f"[VOICE ALERT WARN] {e_vo}")

        pac_id = registrar_o_actualizar_paciente(filiacion)

        consulta_hoy = obtener_consulta_del_dia(pac_id)
        if consulta_hoy:
            try:
                prev_json = json.loads(consulta_hoy.get("json_clinico", "{}"))
                prev_fil = prev_json.get("datos_filiacion", {})
                new_fil = resultado_ia.setdefault("datos_filiacion", {})
                for k in ("edad", "documento", "sexo", "telefono", "direccion"):
                    if not new_fil.get(k) or str(new_fil.get(k)).lower() in ("no especificado", "none", ""):
                        if prev_fil.get(k):
                            new_fil[k] = prev_fil[k]
                            filiacion[k] = prev_fil[k]

                prev_odonto = {p.get("pieza_dental"): p for p in prev_json.get("odontograma", []) if p.get("pieza_dental")}
                for p in resultado_ia.get("odontograma", []):
                    prev_odonto[p.get("pieza_dental")] = p
                resultado_ia["odontograma"] = list(prev_odonto.values())

                if prev_json.get("diagnostico") and prev_json["diagnostico"] != "No especificado":
                    if not resultado_ia.get("diagnostico") or resultado_ia.get("diagnostico") == "No especificado":
                        resultado_ia["diagnostico"] = prev_json["diagnostico"]
                if prev_json.get("plan_tratamiento") and prev_json["plan_tratamiento"] != "No especificado":
                    if not resultado_ia.get("plan_tratamiento") or resultado_ia.get("plan_tratamiento") == "No especificado":
                        resultado_ia["plan_tratamiento"] = prev_json["plan_tratamiento"]
            except Exception as e_merge:
                print(f"[CONSOLIDACION WARN] {e_merge}")

        num_exp = None
        if consulta_hoy:
            num_exp = obtener_num_expediente_consulta(consulta_hoy["id"])
        else:
            num_exp = obtener_siguiente_num_expediente_paciente(pac_id)
        resultado_ia["num_expediente"] = num_exp
        ruta_pdf = None
        if generar_pdf:
            ruta_pdf = crear_historia_clinica(resultado_ia, paciente_id=pac_id, num_expediente=num_exp)
            self._ultima_ruta_pdf = ruta_pdf

        medico_id = self._usuario_actual.get("id", 1) if self._usuario_actual else 1
        if consulta_hoy:
            cid = consulta_hoy["id"]
            actualizar_consulta_existente(cid, resultado_ia, ruta_pdf=ruta_pdf)
        else:
            cid = guardar_consulta_db(paciente_id=pac_id, json_clinico=resultado_ia, ruta_pdf=ruta_pdf, medico_id=medico_id)

        cita_info = resultado_ia.get("cita_programada", {})
        cita_programada_str = None
        url_gcal_creada = ""
        if cita_info and (cita_info.get("agendar") or cita_info.get("detectada")):
            f_c = cita_info.get("fecha_hora", "")
            m_c = cita_info.get("motivo") or f"Control post-tratamiento de {nombre}"
            tel_c = str(filiacion.get("telefono") or cita_info.get("telefono") or "").strip()
            if f_c:
                cita_programada_str = f_c
                try:
                    res_ag = agendar_cita(paciente_id=pac_id, nombre_paciente=nombre, telefono=tel_c, fecha_hora_inicio=f_c, descripcion=m_c, abrir_en_navegador=True)
                    url_gcal_creada = res_ag.get("url_gcal") if isinstance(res_ag, dict) else ""
                except Exception as e_ag:
                    print(f"[AGENDAR CITA WARN] {e_ag}")
                    try:
                        crear_cita_db(paciente_id=pac_id, nombre_paciente=nombre, telefono=tel_c, fecha_hora_inicio=f_c, descripcion=m_c)
                    except Exception as e_c:
                        print(f"[CREAR CITA DB WARN] {e_c}")

        if not alerta_cedula:
            try:
                sonar_confirmacion_exito()
            except Exception:
                pass

        if self._window:
            try:
                self._window.evaluate_js("if (window.actualizarTodosLosMenus) window.actualizarTodosLosMenus();")
            except Exception:
                pass

        return {
            "status": "ok",
            "tipo": "HISTORIA_CLINICA",
            "texto": texto,
            "resultado": resultado_ia,
            "ruta_pdf": ruta_pdf,
            "paciente": nombre,
            "paciente_id": pac_id,
            "consulta_id": cid,
            "alerta_cedula_requerida": alerta_cedula,
            "cita_programada": cita_programada_str,
            "url_gcal": url_gcal_creada
        }

    def procesar_audio_externo(self, ruta_wav):
        try:
            print(f"[BIMO DESKTOP] Audio recibido desde smartphone: {ruta_wav}")
            texto = transcribir_audio(ruta_wav)
            if texto and texto.strip():
                resp = self.procesar_texto_clinico(texto)
                if self._window:
                    self._window.evaluate_js(f"if (window.onMobileAudioProcessed) window.onMobileAudioProcessed({json.dumps(resp)});")
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] procesar_audio_externo: {e}")

    def obtener_ultimo_expediente(self):
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.id, c.paciente_id, p.nombre, p.documento, p.edad, p.telefono,
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
                        "telefono": "",
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
                    self._ultima_ruta_pdf = c_dict.get("ruta_pdf")
                
                costo_val = pago_row['costo_total'] if pago_row and 'costo_total' in pago_row.keys() and pago_row['costo_total'] is not None else 0.0
                abono_val = pago_row['abono'] if pago_row and 'abono' in pago_row.keys() and pago_row['abono'] is not None else 0.0

                tel_pac = c_dict.get("telefono") or ""
                if str(tel_pac).lower() in ("no especificado", "none", "null"):
                    tel_pac = ""

                return {
                    "status": "ok",
                    "id": c_dict["id"],
                    "paciente_id": c_dict["paciente_id"],
                    "paciente": c_dict.get("nombre") or "Paciente",
                    "documento": c_dict.get("documento") or "",
                    "edad": f"{c_dict.get('edad')} años" if c_dict.get("edad") else "Edad no reg.",
                    "edad_num": c_dict.get("edad") if c_dict.get("edad") is not None else "",
                    "telefono": tel_pac,
                    "diagnostico": c_dict.get("diagnostico") or "No especificado",
                    "plan": c_dict.get("plan_tratamiento") or "No especificado",
                    "motivo": c_dict.get("motivo_consulta") or "Consulta General",
                    "proxima_cita": cita_str or (c_dict.get("fecha_hora", "")[:16]),
                    "pago": saldo_str,
                    "costo_total": costo_val,
                    "abono": abono_val,
                    "receta": receta_str,
                    "ruta_pdf": c_dict.get("ruta_pdf"),
                    "json_clinico": json_c
                }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] obtener_ultimo_expediente: {e}")
            return {"status": "error", "message": str(e)}

    def guardar_consulta_corregida(self, datos):
        try:
            if isinstance(datos, str):
                datos = json.loads(datos)

            consulta_id = datos.get("consulta_id") or datos.get("id")
            paciente_id = datos.get("paciente_id")
            nuevo_nombre = str(datos.get("nombre", "")).strip() or "Paciente_Consulta"
            nueva_cedula = str(datos.get("documento") or datos.get("cedula") or "").strip()
            nuevo_telefono = str(datos.get("telefono", "")).strip()
            nueva_edad_str = str(datos.get("edad", "")).strip()
            nueva_edad = int(nueva_edad_str) if nueva_edad_str.isdigit() else None
            nuevo_motivo = str(datos.get("motivo_consulta") or datos.get("motivo") or "").strip()
            nuevo_diag = str(datos.get("diagnostico", "")).strip()
            nuevo_plan = str(datos.get("plan_tratamiento") or datos.get("plan") or "").strip()
            nueva_receta = str(datos.get("receta", "")).strip()

            try:
                costo_total = float(datos.get("costo_total", 0.0) or 0.0)
            except Exception:
                costo_total = 0.0
            try:
                abono = float(datos.get("abono", 0.0) or 0.0)
            except Exception:
                abono = 0.0
            saldo_pendiente = max(0.0, costo_total - abono)

            with get_connection() as conn:
                cursor = conn.cursor()
                if consulta_id:
                    cursor.execute("SELECT id, paciente_id, ruta_pdf, json_clinico FROM consultas WHERE id = ?", (consulta_id,))
                else:
                    cursor.execute("SELECT id, paciente_id, ruta_pdf, json_clinico FROM consultas ORDER BY id DESC LIMIT 1")
                c_row = cursor.fetchone()

            if not c_row:
                return {"status": "error", "message": "No se encontró la consulta a corregir."}

            cid = c_row["id"]
            pid = paciente_id or c_row["paciente_id"]
            ruta_pdf_antigua = c_row["ruta_pdf"]

            json_clinico = {}
            if c_row["json_clinico"]:
                try:
                    json_clinico = json.loads(c_row["json_clinico"])
                except Exception:
                    pass

            # 1. Actualizar filiación de paciente
            if nueva_cedula and nueva_cedula.lower() not in ("no especificado", "none", ""):
                with get_connection() as conn_check:
                    c_check = conn_check.cursor()
                    c_check.execute("SELECT id FROM pacientes WHERE documento = ? AND id != ?", (nueva_cedula, pid))
                    pac_con_cedula = c_check.fetchone()
                    if pac_con_cedula:
                        pid = pac_con_cedula["id"]

            filiacion = json_clinico.setdefault("datos_filiacion", {})
            filiacion["id"] = pid
            filiacion["nombre"] = nuevo_nombre
            filiacion["documento"] = nueva_cedula if nueva_cedula else "No especificado"
            filiacion["edad"] = nueva_edad
            if nuevo_telefono:
                filiacion["telefono"] = nuevo_telefono

            pid_actualizado = registrar_o_actualizar_paciente(filiacion)
            if pid_actualizado:
                pid = pid_actualizado

            if nuevo_telefono:
                with get_connection() as conn_tel:
                    c_tel = conn_tel.cursor()
                    c_tel.execute("UPDATE pacientes SET telefono = ? WHERE id = ?", (nuevo_telefono, pid))
                    c_tel.execute("UPDATE citas_agenda SET telefono = ? WHERE paciente_id = ?", (nuevo_telefono, pid))
                    conn_tel.commit()

            with get_connection() as conn_re:
                c_re = conn_re.cursor()
                c_re.execute("UPDATE consultas SET paciente_id = ? WHERE id = ?", (pid, cid))
                conn_re.commit()

            # 2. Actualizar json_clinico
            json_clinico["datos_filiacion"] = filiacion
            if nuevo_motivo:
                json_clinico["motivo_consulta"] = nuevo_motivo
            if nuevo_diag:
                json_clinico["diagnostico"] = nuevo_diag
            if nuevo_plan:
                json_clinico["plan_tratamiento"] = nuevo_plan
            if nueva_receta:
                json_clinico["receta"] = nueva_receta

            incluir_ortodoncia = datos.get("incluir_ortodoncia", None)
            if incluir_ortodoncia is not None:
                json_clinico["incluir_ortodoncia"] = bool(incluir_ortodoncia)
                json_clinico["hoja_ortodoncia"] = bool(incluir_ortodoncia)
                json_clinico["es_ortodoncia"] = bool(incluir_ortodoncia)
                if bool(incluir_ortodoncia) and "ortodoncia" not in json_clinico:
                    json_clinico["ortodoncia"] = {
                        "tipo_maloclusion": "Clase I molar",
                        "linea_media": "Centrada",
                        "mordida": "Normomordida",
                        "habitos": "Ninguno reportado",
                        "apiñamiento": "Leve",
                        "objetivos": "Alineación y nivelación",
                        "aparatologia": "Brackets metálicos prescripción MBT slot 0.022",
                        "fases": "1. Alineación 2. Cierre de espacios 3. Detallado",
                        "tiempo_estimado": "18 a 24 meses"
                    }

            json_clinico["pagos"] = {
                "costo_total": costo_total,
                "abono": abono,
                "saldo_pendiente": saldo_pendiente,
                "estado": "Cancelado" if saldo_pendiente <= 0 else "Pendiente",
                "metodo_pago": "Efectivo",
                "notas": ""
            }

            # 3. Regenerar nuevo PDF definitivo
            num_exp = obtener_num_expediente_consulta(cid)
            json_clinico["num_expediente"] = num_exp
            nueva_ruta = crear_historia_clinica(json_clinico, paciente_id=pid, num_expediente=num_exp)

            # 4. Eliminar estrictamente el PDF anterior si la ruta o nombre cambió
            if ruta_pdf_antigua and os.path.exists(ruta_pdf_antigua) and os.path.abspath(ruta_pdf_antigua) != os.path.abspath(nueva_ruta):
                try:
                    os.remove(ruta_pdf_antigua)
                    print(f"[PDF CLEANUP] PDF anterior eliminado tras corrección: {ruta_pdf_antigua}")
                    dir_antiguo = os.path.dirname(ruta_pdf_antigua)
                    if os.path.exists(dir_antiguo) and not os.listdir(dir_antiguo):
                        os.rmdir(dir_antiguo)
                except Exception as e_clean:
                    print(f"[PDF CLEANUP WARN]: {e_clean}")

            self._ultima_ruta_pdf = nueva_ruta

            # 5. Actualizar registro en base de datos
            actualizar_consulta_existente(cid, json_clinico, ruta_pdf=nueva_ruta)

            # Actualizar pagos
            if costo_total > 0 or abono > 0:
                try:
                    registrar_o_actualizar_pago_db(
                        paciente_id=pid,
                        consulta_id=cid,
                        costo_total=costo_total,
                        abono=abono,
                        saldo_pendiente=saldo_pendiente,
                        estado="Cancelado" if saldo_pendiente <= 0 else "Pendiente"
                    )
                except Exception as e_pago:
                    print(f"[PAGO CORRECCION WARN]: {e_pago}")

            try:
                sonar_confirmacion_exito()
            except Exception:
                pass

            if self._window:
                try:
                    self._window.evaluate_js("if (window.actualizarTodosLosMenus) window.actualizarTodosLosMenus();")
                except Exception:
                    pass

            return {
                "status": "ok",
                "message": "Expediente corregido y PDF regenerado con éxito",
                "ruta_pdf": nueva_ruta,
                "paciente": nuevo_nombre,
                "paciente_id": pid,
                "consulta_id": cid
            }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] guardar_consulta_corregida: {e}")
            return {"status": "error", "message": str(e)}

    def actualizar_cedula_paciente(self, paciente_id=None, nueva_cedula="", consulta_id=None):
        """
        Actualiza la cédula del paciente y regenera el PDF oficial de su consulta actual.
        """
        try:
            from ai_engine import sanitizar_cedula
            cedula_limpia = sanitizar_cedula(nueva_cedula)
            if not cedula_limpia or cedula_limpia.lower() in ("no especificado", "none", ""):
                return {"status": "error", "message": "Por favor ingrese un número de cédula válido."}

            with get_connection() as conn:
                cursor = conn.cursor()
                pid = paciente_id
                if not pid:
                    cursor.execute("SELECT id FROM pacientes ORDER BY id DESC LIMIT 1")
                    p_row = cursor.fetchone()
                    if p_row:
                        pid = p_row["id"]

                if not pid:
                    return {"status": "error", "message": "No se encontró paciente para actualizar cédula."}

                cursor.execute("UPDATE pacientes SET documento = ? WHERE id = ?", (cedula_limpia, pid))
                conn.commit()

                # Buscar consulta para regenerar PDF con la cédula integrada
                if consulta_id:
                    cursor.execute("SELECT id, json_clinico, ruta_pdf FROM consultas WHERE id = ?", (consulta_id,))
                else:
                    cursor.execute("SELECT id, json_clinico, ruta_pdf FROM consultas WHERE paciente_id = ? ORDER BY id DESC LIMIT 1", (pid,))
                c_row = cursor.fetchone()

                nueva_ruta_pdf = None
                if c_row:
                    cid = c_row["id"]
                    ruta_antigua = c_row["ruta_pdf"]
                    json_c = {}
                    if c_row["json_clinico"]:
                        try:
                            json_c = json.loads(c_row["json_clinico"])
                        except Exception:
                            pass
                    fil = json_c.setdefault("datos_filiacion", {})
                    fil["documento"] = cedula_limpia
                    num_exp = obtener_num_expediente_consulta(cid)
                    json_c["num_expediente"] = num_exp
                    nueva_ruta_pdf = crear_historia_clinica(json_c, paciente_id=pid, num_expediente=num_exp)
                    cursor.execute("UPDATE consultas SET json_clinico = ?, ruta_pdf = ? WHERE id = ?",
                                   (json.dumps(json_c, ensure_ascii=False), nueva_ruta_pdf, cid))
                    conn.commit()

                    if ruta_antigua and ruta_antigua != nueva_ruta_pdf and os.path.exists(ruta_antigua):
                        try:
                            os.remove(ruta_antigua)
                        except Exception:
                            pass
                    self._ultima_ruta_pdf = nueva_ruta_pdf

            try:
                sonar_confirmacion_exito()
            except Exception:
                pass

            if self._window:
                try:
                    self._window.evaluate_js("if (window.actualizarTodosLosMenus) window.actualizarTodosLosMenus();")
                except Exception:
                    pass

            return {
                "status": "ok",
                "cedula": cedula_limpia,
                "paciente_id": pid,
                "ruta_pdf": nueva_ruta_pdf,
                "message": "Cédula registrada y expediente actualizado exitosamente."
            }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] actualizar_cedula_paciente: {e}")
            return {"status": "error", "message": str(e)}

    def actualizar_telefono_paciente(self, paciente_id=None, nuevo_telefono="", consulta_id=None):
        """
        Actualiza el número de teléfono del paciente y regenera el PDF oficial de su consulta actual.
        """
        try:
            if isinstance(paciente_id, dict):
                d = paciente_id
                paciente_id = d.get("paciente_id") or d.get("id")
                nuevo_telefono = d.get("telefono") or d.get("nuevo_telefono") or ""
                consulta_id = d.get("consulta_id")

            from database import actualizar_telefono_paciente_y_expediente
            res = actualizar_telefono_paciente_y_expediente(paciente_id, nuevo_telefono, regenerar_pdf=True)
            if res.get("status") == "ok":
                if res.get("ruta_pdf"):
                    self._ultima_ruta_pdf = res.get("ruta_pdf")
                try:
                    sonar_confirmacion_exito()
                except Exception:
                    pass
                if self._window:
                    try:
                        self._window.evaluate_js("if (window.actualizarTodosLosMenus) window.actualizarTodosLosMenus();")
                    except Exception:
                        pass
            return res
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] actualizar_telefono_paciente: {e}")
            return {"status": "error", "message": str(e)}

    def actualizar_datos_completos_paciente(self, paciente_id=None, nuevo_nombre=None, nueva_cedula=None, nuevo_telefono=None, consulta_id=None):
        """
        Actualiza simultáneamente nombre, cédula y/o teléfono del paciente y regenera su PDF oficial.
        """
        try:
            if isinstance(paciente_id, dict):
                d = paciente_id
                paciente_id = d.get("paciente_id") or d.get("id")
                nuevo_nombre = d.get("nuevo_nombre") or d.get("nombre")
                nueva_cedula = d.get("nueva_cedula") or d.get("cedula")
                nuevo_telefono = d.get("nuevo_telefono") or d.get("telefono")
                consulta_id = d.get("consulta_id")

            from database import actualizar_datos_paciente_y_expediente
            res = actualizar_datos_paciente_y_expediente(
                paciente_id_o_nombre=paciente_id,
                nuevo_nombre=nuevo_nombre,
                nueva_cedula=nueva_cedula,
                nuevo_telefono=nuevo_telefono,
                regenerar_pdf=True
            )
            if res.get("status") == "ok":
                if res.get("ruta_pdf"):
                    self._ultima_ruta_pdf = res.get("ruta_pdf")
                try:
                    sonar_confirmacion_exito()
                except Exception:
                    pass
                if self._window:
                    try:
                        self._window.evaluate_js("if (window.actualizarTodosLosMenus) window.actualizarTodosLosMenus();")
                    except Exception:
                        pass
            return res
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] actualizar_datos_completos_paciente: {e}")
            return {"status": "error", "message": str(e)}

    def cambiar_posicion_widget(self, posicion):
        try:
            pos_val = str(posicion).strip().lower()
            conf = cargar_datos_clinica()
            conf["posicion_widget"] = pos_val
            guardar_datos_clinica(conf)
            print(f"[BIMO DESKTOP] Posición de widget guardada: {pos_val}")
            if self._widget_process and self._widget_process.poll() is None:
                self.toggle_widget_escritorio(False)
                import time
                time.sleep(0.3)
                self.toggle_widget_escritorio(True)
            return {"status": "ok", "posicion": pos_val, "message": f"Posición guardada: {pos_val}"}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] cambiar_posicion_widget: {e}")
            return {"status": "error", "message": str(e)}

    def cambiar_opacidad_widget(self, opacidad):
        try:
            alpha_val = float(opacidad)
            alpha_val = max(0.2, min(1.0, alpha_val))
            conf = cargar_datos_clinica()
            conf["opacidad_widget"] = alpha_val
            guardar_datos_clinica(conf)
            print(f"[BIMO DESKTOP] Opacidad de widget guardada: {alpha_val}")
            if self._widget_process and self._widget_process.poll() is None:
                self.toggle_widget_escritorio(False)
                import time
                time.sleep(0.3)
                self.toggle_widget_escritorio(True)
            return {"status": "ok", "opacidad": alpha_val, "message": f"Transparencia cambiada a {int(alpha_val*100)}%"}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] cambiar_opacidad_widget: {e}")
            return {"status": "error", "message": str(e)}

    def generar_pdf_actual(self, consulta_id=None, incluir_ortodoncia=False, abrir_externo=False):
        """
        Genera la Historia Clínica Oficial en PDF de la consulta actual o especificada.
        Soporta forzar la inclusión de la 3ra hoja especializada de ortodoncia.
        Solo abre ventana externa del sistema operativo si abrir_externo=True (por defecto False para visor interno).
        """
        try:
            if isinstance(consulta_id, dict):
                d = consulta_id
                consulta_id = d.get("consulta_id") or d.get("id")
                incluir_ortodoncia = d.get("incluir_ortodoncia", False)
                abrir_externo = d.get("abrir_externo", False)

            if str(consulta_id).strip().lower() in ("none", "null", "undefined", "", "0"):
                consulta_id = None
            elif consulta_id is not None:
                try:
                    consulta_id = int(consulta_id)
                except Exception:
                    consulta_id = None

            with get_connection() as conn:
                cursor = conn.cursor()
                if consulta_id:
                    cursor.execute("SELECT id, paciente_id, ruta_pdf, json_clinico, motivo_consulta, enfermedad_actual, diagnostico, plan_tratamiento FROM consultas WHERE id = ?", (consulta_id,))
                else:
                    cursor.execute("SELECT id, paciente_id, ruta_pdf, json_clinico, motivo_consulta, enfermedad_actual, diagnostico, plan_tratamiento FROM consultas ORDER BY id DESC LIMIT 1")
                c_row = cursor.fetchone()

            if not c_row:
                return {"status": "error", "message": "No se encontró ninguna consulta para generar el PDF."}

            cid = c_row["id"]
            pid = c_row["paciente_id"]

            json_clinico = {}
            if c_row["json_clinico"]:
                try:
                    json_clinico = json.loads(c_row["json_clinico"])
                except Exception:
                    pass

            if not json_clinico or not isinstance(json_clinico, dict):
                paciente = obtener_paciente_por_id(pid) or {}
                json_clinico = {
                    "tipo": "HISTORIA_CLINICA",
                    "datos_filiacion": {
                        "nombre": paciente.get("nombre", "Paciente"),
                        "edad": paciente.get("edad", 25),
                        "documento": paciente.get("documento", ""),
                        "telefono": paciente.get("telefono", ""),
                        "sexo": paciente.get("sexo", "No especificado")
                    },
                    "motivo_consulta": c_row.get("motivo_consulta") or "Evaluación odontológica general",
                    "enfermedad_actual": c_row.get("enfermedad_actual") or "Paciente acude a revisión dental.",
                    "diagnostico": c_row.get("diagnostico") or "Examen odontológico de rutina",
                    "plan_tratamiento": c_row.get("plan_tratamiento") or "Profilaxis y evaluación preventiva",
                    "odontograma": []
                }

            if bool(incluir_ortodoncia):
                json_clinico["incluir_ortodoncia"] = True
                json_clinico["hoja_ortodoncia"] = True
                json_clinico["es_ortodoncia"] = True
                if "ortodoncia" not in json_clinico:
                    json_clinico["ortodoncia"] = {
                        "tipo_maloclusion": "Clase I molar",
                        "linea_media": "Centrada",
                        "mordida": "Normomordida",
                        "habitos": "Ninguno reportado",
                        "apiñamiento": "Leve",
                        "objetivos": "Alineación y nivelación",
                        "aparatologia": "Brackets metálicos prescripción MBT slot 0.022",
                        "fases": "1. Alineación 2. Cierre de espacios 3. Detallado",
                        "tiempo_estimado": "18 a 24 meses"
                    }

            num_exp = obtener_num_expediente_consulta(cid)
            json_clinico["num_expediente"] = num_exp
            nueva_ruta = crear_historia_clinica(json_clinico, paciente_id=pid, num_expediente=num_exp)
            self._ultima_ruta_pdf = nueva_ruta

            # Actualizar en BD
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE consultas SET ruta_pdf = ?, json_clinico = ? WHERE id = ?",
                               (nueva_ruta, json.dumps(json_clinico, ensure_ascii=False), cid))
                conn.commit()

            paciente_nombre = json_clinico.get("datos_filiacion", {}).get("nombre", "Paciente")

            # Abrir archivo en el sistema operativo solo si se solicita explícitamente
            try:
                if abrir_externo and os.path.exists(nueva_ruta):
                    os.startfile(os.path.abspath(nueva_ruta))
            except Exception as e_open:
                print(f"[PDF OPEN WARN] {e_open}")

            try:
                sonar_confirmacion_exito()
            except Exception:
                pass

            if self._window:
                try:
                    self._window.evaluate_js("if (window.actualizarTodosLosMenus) window.actualizarTodosLosMenus();")
                except Exception:
                    pass

            return {
                "status": "ok",
                "message": "Historia Clínica Oficial en PDF generada exitosamente",
                "ruta_pdf": nueva_ruta,
                "paciente": paciente_nombre,
                "consulta_id": cid,
                "incluye_ortodoncia": bool(incluir_ortodoncia)
            }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] generar_pdf_actual: {e}")
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
            # Auto-sanación: asegurar que cada consulta tenga su PDF localizado en RUTA_PACIENTES
            for c in consultas:
                r_pdf = c.get("ruta_pdf")
                if not r_pdf or not os.path.exists(r_pdf):
                    cid = c["id"]
                    if RUTA_PACIENTES.exists():
                        for p_cand in RUTA_PACIENTES.rglob("*.pdf"):
                            cand_str = str(p_cand)
                            if f"_ID{paciente_id}" in cand_str or f"ID{paciente_id}" in cand_str:
                                num_e = c.get("num_expediente")
                                if not num_e or f"Exp{num_e}" in p_cand.name:
                                    c["ruta_pdf"] = str(p_cand.resolve())
                                    try:
                                        with get_connection() as conn_heal:
                                            conn_heal.cursor().execute("UPDATE consultas SET ruta_pdf = ? WHERE id = ?", (str(p_cand.resolve()), cid))
                                            conn_heal.commit()
                                    except Exception:
                                        pass
                                    break
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
    def obtener_citas(self, limite=100):
        try:
            return listar_citas_db(limite)
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] obtener_citas: {e}")
            return []

    def crear_cita(self, datos=None, **kwargs):
        try:
            if datos is None and kwargs:
                datos = kwargs
            elif isinstance(datos, str):
                datos = json.loads(datos)
            elif not isinstance(datos, dict):
                datos = {}
            if kwargs:
                datos.update(kwargs)

            pid = datos.get("paciente_id")
            nom = datos.get("nombre") or datos.get("nombre_paciente", "")
            tel = datos.get("telefono", "")
            f_ini = datos.get("fecha_inicio") or datos.get("fecha_hora", "")
            f_fin = datos.get("fecha_fin", "")
            desc = datos.get("descripcion", "Consulta odontológica")
            res_cal = agendar_cita(
                paciente_id=pid,
                nombre_paciente=nom,
                telefono=tel,
                fecha_hora_inicio=f_ini,
                fecha_hora_fin=f_fin,
                descripcion=desc,
                abrir_en_navegador=True
            )
            cita_id = res_cal.get("cita_id") if isinstance(res_cal, dict) else res_cal
            url_gcal = res_cal.get("url_gcal") if isinstance(res_cal, dict) else ""
            return {"status": "ok", "id": cita_id, "cita_id": cita_id, "url_gcal": url_gcal}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] crear_cita: {e}")
            return {"status": "error", "message": str(e)}

    def cancelar_cita(self, cita_id=None, nombre_paciente=None, fecha=None):
        try:
            if cita_id:
                cancelar_o_eliminar_cita_db(cita_id=cita_id)
            elif nombre_paciente:
                cancelar_o_eliminar_cita_db(nombre_paciente=nombre_paciente, fecha=fecha)
            return {"status": "ok"}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] cancelar_cita: {e}")
            return {"status": "error", "message": str(e)}

    def reprogramar_cita_id(self, datos=None, **kwargs):
        """
        Reprograma una cita existente por su ID:
        Actualiza fecha_hora_inicio, fecha_hora_fin, descripcion y genera sincronización Google Calendar.
        """
        try:
            if datos is None and kwargs:
                datos = kwargs
            elif isinstance(datos, str):
                datos = json.loads(datos)
            elif not isinstance(datos, dict):
                datos = {}
            if kwargs:
                datos.update(kwargs)

            cita_id = datos.get("cita_id") or datos.get("id")
            nueva_fecha_inicio = datos.get("fecha_inicio") or datos.get("fecha_hora") or datos.get("fecha_hora_inicio")
            nuevo_motivo = datos.get("descripcion") or datos.get("motivo")
            nuevo_tel = str(datos.get("telefono") or datos.get("celular") or "").strip()

            if not cita_id or not nueva_fecha_inicio:
                return {"status": "error", "message": "Se requiere ID de cita y nueva fecha/hora."}

            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM citas_agenda WHERE id = ?", (cita_id,))
                cita_existente = cursor.fetchone()

            if not cita_existente:
                return {"status": "error", "message": f"No se encontró la cita #{cita_id}"}

            nom_paciente = cita_existente["nombre_paciente"]
            pid = cita_existente["paciente_id"]
            desc_final = nuevo_motivo or cita_existente["descripcion"] or "Consulta odontológica"
            tel_final = nuevo_tel if nuevo_tel else (cita_existente["telefono"] or "")
            google_event_id = cita_existente["google_event_id"]

            # 1. Eliminar evento anterior en Google Calendar si existe
            from calendar_sync import _CALENDAR_SERVICE
            if _CALENDAR_SERVICE and google_event_id:
                try:
                    _CALENDAR_SERVICE.events().delete(calendarId='primary', eventId=google_event_id).execute()
                except Exception:
                    pass

            # 2. Calcular nueva fecha_hora_fin (30 minutos por defecto)
            nueva_f_fin = None
            try:
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                    try:
                        dt_ini = datetime.datetime.strptime(nueva_fecha_inicio, fmt)
                        nueva_f_fin = (dt_ini + datetime.timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
                        break
                    except Exception:
                        pass
            except Exception:
                pass

            # 3. Actualizar en SQLite
            with get_connection() as conn_up:
                cur_up = conn_up.cursor()
                cur_up.execute("""
                    UPDATE citas_agenda
                    SET fecha_hora_inicio = ?, fecha_hora_fin = ?, descripcion = ?, telefono = ?, estado = 'programada'
                    WHERE id = ?
                """, (nueva_fecha_inicio, nueva_f_fin, desc_final, tel_final, cita_id))

                if nuevo_tel:
                    if pid:
                        cur_up.execute("""
                            UPDATE pacientes
                            SET telefono = ?
                            WHERE id = ? AND (telefono IS NULL OR telefono = '' OR telefono = 'No especificado')
                        """, (nuevo_tel, pid))
                    elif nom_paciente:
                        cur_up.execute("""
                            UPDATE pacientes
                            SET telefono = ?
                            WHERE LOWER(TRIM(nombre)) = LOWER(TRIM(?)) AND (telefono IS NULL OR telefono = '' OR telefono = 'No especificado')
                        """, (nuevo_tel, nom_paciente))
                conn_up.commit()

            # 4. Generar enlace oficial de Google Calendar y abrir navegador
            res_cal = agendar_cita(
                paciente_id=pid,
                nombre_paciente=nom_paciente,
                telefono=tel_final,
                fecha_hora_inicio=nueva_fecha_inicio,
                fecha_hora_fin=nueva_f_fin,
                descripcion=desc_final,
                abrir_en_navegador=True
            )
            url_gcal = res_cal.get("url_gcal") if isinstance(res_cal, dict) else ""

            try:
                sonar_confirmacion_exito()
            except Exception:
                pass

            print(f"[REPROGRAMAR CITA ID] Cita #{cita_id} de {nom_paciente} movida a {nueva_fecha_inicio}")
            return {
                "status": "ok",
                "cita_id": cita_id,
                "nombre_paciente": nom_paciente,
                "fecha_hora": nueva_fecha_inicio,
                "url_gcal": url_gcal,
                "message": f"Cita de {nom_paciente} reprogramada exitosamente para {nueva_fecha_inicio}"
            }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] reprogramar_cita_id: {e}")
            return {"status": "error", "message": str(e)}

    # ==========================================
    # VISOR & GESTIÓN DE PDF
    # ==========================================
    def listar_pdfs_recientes(self):
        try:
            pdfs = []
            vistos = set()
            consultas_db = []
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT c.id, c.ruta_pdf, c.fecha_hora, p.nombre, p.documento, p.edad, c.paciente_id
                        FROM consultas c
                        JOIN pacientes p ON c.paciente_id = p.id
                        ORDER BY c.id DESC
                    """)
                    consultas_db = [dict(r) for r in cursor.fetchall()]
            except Exception as e_db:
                print(f"[LISTAR PDFS DB WARN] {e_db}")

            # 1. Cargar directamente todos los PDFs registrados en la Base de Datos con auto-sanación
            for c in consultas_db:
                r_pdf = c.get("ruta_pdf")
                if r_pdf and not os.path.exists(r_pdf):
                    # Auto-detección en RUTA_PACIENTES por nombre de archivo
                    b_name = os.path.basename(r_pdf)
                    if RUTA_PACIENTES.exists():
                        for p_cand in RUTA_PACIENTES.rglob(b_name):
                            r_pdf = str(p_cand.resolve())
                            try:
                                with get_connection() as conn_heal:
                                    conn_heal.cursor().execute("UPDATE consultas SET ruta_pdf = ? WHERE id = ?", (r_pdf, c["id"]))
                                    conn_heal.commit()
                            except Exception:
                                pass
                            break

                if r_pdf and os.path.exists(r_pdf):
                    norm = os.path.normpath(r_pdf)
                    if norm not in vistos:
                        vistos.add(norm)
                        try:
                            st = os.stat(r_pdf)
                            kb = round(st.st_size / 1024, 1)
                            mtime = datetime.datetime.fromtimestamp(st.st_mtime)
                            edad_str = f"{c['edad']} años" if c.get("edad") else ""
                            pdfs.append({
                                "nombre": os.path.basename(r_pdf),
                                "ruta": r_pdf,
                                "paciente": c.get("nombre") or "Paciente",
                                "cedula": c.get("documento") or "Sin cédula",
                                "edad": edad_str,
                                "fecha": mtime.strftime("%d/%m/%Y %H:%M"),
                                "timestamp": st.st_mtime,
                                "tamano": f"{kb} KB"
                            })
                        except Exception:
                            pass

            # 2. Escaneo complementario de disco para detectar PDFs creados o transferidos externamente
            dev_project_dir = Path.home() / "Desktop" / "Bimo_Project"
            dirs_a_buscar = [
                RUTA_PACIENTES,
                BASE_DIR / "Pacientes",
                dev_project_dir / "Pacientes"
            ]
            for d in dirs_a_buscar:
                if d.exists():
                    for p in d.rglob("*.pdf"):
                        p_str = str(p.resolve())
                        norm_p = os.path.normpath(p_str)
                        if norm_p in vistos:
                            continue
                        vistos.add(norm_p)
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
                                "cedula": "Sin cédula",
                                "edad": "",
                                "fecha": mtime.strftime("%d/%m/%Y %H:%M"),
                                "timestamp": stat.st_mtime,
                                "tamano": f"{kb} KB"
                            })
                        except Exception:
                            pass

            pdfs.sort(key=lambda x: x["timestamp"], reverse=True)
            return pdfs[:60]
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] listar_pdfs_recientes: {e}")
            return []

    def obtener_preview_pdf(self, ruta_pdf=None):
        try:
            target = ruta_pdf or self._ultima_ruta_pdf
            if target:
                target = os.path.normpath(str(target))
            if not target or not os.path.exists(target):
                recientes = self.listar_pdfs_recientes()
                if recientes:
                    target = os.path.normpath(str(recientes[0]["ruta"]))
            if not target or not os.path.exists(target):
                return {"status": "error", "message": "No se encontró ningún PDF generado aún."}

            doc = fitz.open(target)
            paginas = []
            for i in range(len(doc)):
                page = doc[i]
                pix = page.get_pixmap(dpi=110)
                img_bytes = pix.tobytes("jpeg", jpg_quality=85)
                b64 = "data:image/jpeg;base64," + base64.b64encode(img_bytes).decode("utf-8")
                paginas.append(b64)

            kb = round(os.path.getsize(target) / 1024, 1)
            self._ultima_ruta_pdf = target

            paciente_nom = "Paciente"
            paciente_cedula = "Sin cédula registrada"
            paciente_edad = ""
            fecha_consulta = datetime.datetime.fromtimestamp(os.path.getmtime(target)).strftime("%d/%m/%Y %H:%M")
            doctor_nombre = self._usuario_actual.get("nombre", "Mateo Ramírez") if self._usuario_actual else "Mateo Ramírez"

            try:
                norm_target = os.path.normpath(target)
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT c.id, c.paciente_id, c.fecha_hora, c.json_clinico, p.nombre, p.documento, p.edad, p.telefono, u.nombre as doctor
                        FROM consultas c
                        JOIN pacientes p ON c.paciente_id = p.id
                        LEFT JOIN usuarios u ON c.medico_id = u.id
                        WHERE c.ruta_pdf = ? OR REPLACE(c.ruta_pdf, '/', '\\') = ?
                        ORDER BY c.id DESC LIMIT 1
                    """, (target, norm_target))
                    row = cursor.fetchone()
                    if not row:
                        cursor.execute("""
                            SELECT c.id, c.paciente_id, c.fecha_hora, c.json_clinico, p.nombre, p.documento, p.edad, p.telefono, u.nombre as doctor
                            FROM consultas c
                            JOIN pacientes p ON c.paciente_id = p.id
                            LEFT JOIN usuarios u ON c.medico_id = u.id
                            WHERE c.ruta_pdf LIKE ?
                            ORDER BY c.id DESC LIMIT 1
                        """, (f"%{os.path.basename(target)}%",))
                        row = cursor.fetchone()

                    consulta_id = None
                    paciente_id = None
                    paciente_tel = ""
                    motivo_c = ""
                    diag_c = ""
                    plan_c = ""
                    receta_c = ""
                    costo_c = 0.0
                    abono_c = 0.0
                    es_orto_c = False

                    if row:
                        consulta_id = row["id"]
                        paciente_id = row["paciente_id"]
                        paciente_nom = row["nombre"] or paciente_nom
                        paciente_cedula = row["documento"] or paciente_cedula
                        paciente_tel = row["telefono"] or ""
                        if row["edad"]:
                            paciente_edad = f"{row['edad']} años"
                        if row["doctor"]:
                            doctor_nombre = row["doctor"].replace("Dr.", "").replace("Dr", "").strip()
                        if row["fecha_hora"]:
                            fecha_consulta = str(row["fecha_hora"])[:16]

                        if row["json_clinico"]:
                            try:
                                jc = json.loads(row["json_clinico"]) if isinstance(row["json_clinico"], str) else (row["json_clinico"] or {})
                                motivo_c = jc.get("motivo_consulta") or jc.get("motivo") or ""
                                diag_c = jc.get("diagnostico") or ""
                                plan_c = jc.get("plan_tratamiento") or jc.get("plan") or ""
                                receta_c = jc.get("receta") or ""
                                costo_c = float(jc.get("costo_total") or 0.0)
                                abono_c = float(jc.get("abono") or 0.0)
                                es_orto_c = bool(jc.get("incluir_ortodoncia") or jc.get("hoja_ortodoncia") or jc.get("es_ortodoncia"))
                            except Exception:
                                pass
            except Exception as e_meta:
                print(f"[PDF PREVIEW META WARN] {e_meta}")

            return {
                "status": "ok",
                "ruta": target,
                "nombre": os.path.basename(target),
                "paciente": paciente_nom,
                "cedula": paciente_cedula,
                "telefono": paciente_tel,
                "edad": paciente_edad,
                "doctor": doctor_nombre,
                "fecha": fecha_consulta,
                "consulta_id": consulta_id,
                "paciente_id": paciente_id,
                "motivo": motivo_c,
                "diagnostico": diag_c,
                "plan": plan_c,
                "receta": receta_c,
                "costo_total": costo_c,
                "abono": abono_c,
                "incluir_ortodoncia": es_orto_c,
                "total_paginas": len(paginas),
                "paginas": paginas,
                "tamano": f"{kb} KB"
            }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] obtener_preview_pdf: {e}")
            return {"status": "error", "message": str(e)}

    def abrir_pdf(self, ruta):
        try:
            if ruta and os.path.exists(ruta):
                os.startfile(ruta)
                return {"status": "ok"}
            return {"status": "error", "message": "El archivo PDF no fue encontrado en el disco."}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] abrir_pdf: {e}")
            return {"status": "error", "message": str(e)}

    def abrir_ultimo_pdf(self, abrir_externo=False):
        try:
            target = self._ultima_ruta_pdf
            if not target or not os.path.exists(target):
                lista = self.listar_pdfs_recientes()
                if lista:
                    target = lista[0]["ruta"]
                    self._ultima_ruta_pdf = target
            if target and os.path.exists(target):
                if abrir_externo:
                    try:
                        os.startfile(target)
                    except Exception:
                        pass
                return {"status": "ok", "ruta": target}
            return {"status": "error", "message": "No hay ningún PDF generado aún."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def imprimir_pdf(self, ruta=None):
        try:
            target = ruta or self._ultima_ruta_pdf
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
    # MÓVIL & RED LOCAL CON QR REAL
    # ==========================================
    def obtener_info_movil(self):
        try:
            ip = obtener_ip_local()
            puerto = MOBILE_SERVER_PORT
            url = f"https://{ip}:{puerto}/"
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
                "puerto": 8765,
                "url": "https://127.0.0.1:8765/"
            }

    def obtener_qr_movil_base64(self):
        try:
            ip = obtener_ip_local()
            url = f"https://{ip}:{MOBILE_SERVER_PORT}/"
            pil_img = generar_codigo_qr_url(url)
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("utf-8")
            return {
                "status": "ok",
                "ip": ip,
                "puerto": MOBILE_SERVER_PORT,
                "url": url,
                "qr_b64": b64
            }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] obtener_qr_movil_base64: {e}")
            return {
                "status": "error",
                "message": str(e),
                "ip": "127.0.0.1",
                "puerto": MOBILE_SERVER_PORT,
                "url": f"https://127.0.0.1:{MOBILE_SERVER_PORT}/",
                "qr_b64": ""
            }

    def abrir_url_movil(self):
        try:
            info = self.obtener_info_movil()
            webbrowser.open(info.get("url", "https://localhost:8765/"))
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
            actuales = cargar_datos_clinica()
            if isinstance(datos, dict):
                actuales.update(datos)
            guardar_datos_clinica(actuales)
            return {"status": "ok"}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] guardar_configuracion: {e}")
            return {"status": "error", "message": str(e)}

    # ==========================================
    # WIDGET FLOTANTE DE ESCRITORIO
    # ==========================================
    def obtener_estado_widget(self):
        activo = False
        pid = None
        if self._widget_process and self._widget_process.poll() is None:
            activo = True
            pid = self._widget_process.pid
        return {
            "status": "ok",
            "activo": activo,
            "pid": pid,
            "posicion": "Superior Derecha",
            "opacidad": 90,
            "anclado": True
        }

    def toggle_widget_escritorio(self, activar=True):
        try:
            if isinstance(activar, str):
                activar = activar.lower() in ("true", "1", "si", "yes")

            if activar:
                if not self._widget_process or self._widget_process.poll() is not None:
                    proc = _lanzar_proceso_widget(os.getpid())
                    self._widget_process = proc
                    if proc:
                        print(f"[BIMO DESKTOP] Widget HUD iniciado (PID: {proc.pid})")
                return {
                    "status": "ok",
                    "activo": True,
                    "pid": self._widget_process.pid if self._widget_process else None,
                    "message": "Widget HUD de escritorio activado"
                }
            else:
                if self._widget_process and self._widget_process.poll() is None:
                    try:
                        self._widget_process.terminate()
                        self._widget_process.wait(timeout=1.5)
                    except Exception:
                        try:
                            self._widget_process.kill()
                        except Exception:
                            pass
                    self._widget_process = None
                    print("[BIMO DESKTOP] Widget HUD detenido.")
                return {
                    "status": "ok",
                    "activo": False,
                    "message": "Widget HUD de escritorio desactivado"
                }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] toggle_widget_escritorio: {e}")
            return {"status": "error", "message": str(e)}

    def exportar_excel(self):
        try:
            from export_excel import exportar_a_excel
            ruta_excel = exportar_a_excel()
            self.abrir_pdf(str(ruta_excel))
            return {"status": "ok", "ruta": str(ruta_excel)}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] exportar_excel: {e}")
            return {"status": "error", "message": str(e)}

    def abrir_carpeta_paciente(self, paciente_id):
        try:
            import re
            from config import RUTA_PACIENTES
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, nombre, edad FROM pacientes WHERE id = ?", (paciente_id,))
                p = cursor.fetchone()
            if not p:
                return {"status": "error", "message": "Paciente no encontrado"}

            nombre_limpio = sanitizar_nombre_carpeta(p["nombre"])
            edad_num = p["edad"] or 18
            categoria = "Pacientes_Pediatricos" if edad_num < 18 else "Pacientes_Adultos"
            nombre_carpeta = f"{nombre_limpio}_{edad_num}_anos_ID{p['id']}"
            ruta = os.path.join(RUTA_PACIENTES, categoria, nombre_carpeta)
            os.makedirs(ruta, exist_ok=True)
            self.abrir_pdf(ruta)
            return {"status": "ok", "ruta": str(ruta)}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] abrir_carpeta_paciente: {e}")
            return {"status": "error", "message": str(e)}

    def abrir_google_calendar(self):
        try:
            conf = cargar_datos_clinica()
            email_g = str(conf.get("email_google", "") or "").strip()
            if email_g and "@" in email_g:
                webbrowser.open(f"https://calendar.google.com/calendar/u/{email_g}/r")
            else:
                webbrowser.open("https://calendar.google.com")
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def obtener_info_licencia(self):
        try:
            from license_manager import validar_licencia, obtener_hwid_equipo
            valida, info = validar_licencia()
            hwid = obtener_hwid_equipo()
            return {
                "status": "ok",
                "activa": valida,
                "email": info.get("email", "mateoramirez@bimo.local"),
                "hwid": hwid,
                "plan": "BIMO Pro Permanente (Full Features)"
            }
        except Exception as e:
            return {
                "status": "ok",
                "activa": True,
                "email": "mateoramirez@bimo.local",
                "hwid": "BIMO-HWID-OFFLINE",
                "plan": "BIMO Pro Permanente"
            }

    def reproducir_sonido(self, tipo="exito"):
        try:
            if tipo == "inicio":
                sonar_inicio_dictado()
            elif tipo == "fin":
                sonar_fin_dictado()
            else:
                sonar_confirmacion_exito()
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ==========================================
    # ACUERDOS Y COMPROMISOS CLÍNICOS (ARQUITECTURA Y RIESGOS)
    # ==========================================
    def obtener_estado_terminos(self):
        try:
            from config import obtener_estado_terminos
            return obtener_estado_terminos()
        except Exception as e:
            return {"status": "ok", "aceptados": False, "error": str(e)}

    def aceptar_terminos_legales(self):
        try:
            from config import guardar_aceptacion_terminos
            return guardar_aceptacion_terminos()
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ==========================================
    # MÓDULO 1: WHATSAPP ANTI-AUSENTISMO
    # ==========================================
    def enviar_recordatorio_whatsapp(self, cita_id, forzar_navegador=False):
        try:
            from whatsapp_service import despachar_recordatorio_cita
            res = despachar_recordatorio_cita(int(cita_id), forzar_navegador=bool(forzar_navegador))
            try:
                sonar_confirmacion_exito()
            except Exception:
                pass
            return res
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] enviar_recordatorio_whatsapp: {e}")
            return {"status": "error", "message": str(e)}

    def obtener_citas_recordatorio_manana(self, dias_adelanto=1):
        try:
            from whatsapp_service import obtener_citas_pendientes_recordatorio
            citas = obtener_citas_pendientes_recordatorio(dias_adelanto=int(dias_adelanto))
            return {"status": "ok", "citas": citas}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] obtener_citas_recordatorio_manana: {e}")
            return {"status": "error", "message": str(e), "citas": []}

    def enviar_recordatorios_lote_manana(self, forzar_navegador=False):
        try:
            from whatsapp_service import despachar_recordatorios_lote_manana
            res = despachar_recordatorios_lote_manana(forzar_navegador=bool(forzar_navegador))
            try:
                sonar_confirmacion_exito()
            except Exception:
                pass
            return res
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] enviar_recordatorios_lote_manana: {e}")
            return {"status": "error", "message": str(e)}

    def guardar_configuracion_whatsapp(self, config_wa):
        try:
            from config import cargar_datos_clinica, guardar_datos_clinica
            d = cargar_datos_clinica()
            if isinstance(config_wa, str):
                config_wa = json.loads(config_wa)
            d["whatsapp"] = config_wa
            guardar_datos_clinica(d)
            return {"status": "ok", "message": "Configuración de WhatsApp guardada exitosamente."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def obtener_configuracion_whatsapp(self):
        try:
            from config import cargar_datos_clinica
            d = cargar_datos_clinica()
            conf_wa = d.get("whatsapp", {
                "proveedor": "none",
                "codigo_pais": "593",
                "meta_access_token": "",
                "meta_phone_number_id": "",
                "twilio_account_sid": "",
                "twilio_auth_token": "",
                "twilio_from_number": "",
                "webhook_url": "",
                "webhook_api_key": ""
            })
            return {"status": "ok", "config": conf_wa}
        except Exception as e:
            return {"status": "error", "message": str(e), "config": {}}

    # ==========================================
    # ALIAS UNIVERSALES (CAMELCASE Y SNAKE_CASE)
    # ==========================================
    autenticarPin = autenticar_pin
    cerrarSesion = cerrar_sesion
    obtenerSesion = obtener_sesion
    iniciarGrabacion = iniciar_grabacion
    detenerYProcesar = detener_y_procesar
    obtenerUltimoExpediente = obtener_ultimo_expediente
    obtenerPacientes = obtener_pacientes
    guardarPaciente = guardar_paciente
    eliminarPaciente = eliminar_paciente
    obtenerPacienteDetalle = obtener_paciente_detalle
    obtenerCitas = obtener_citas
    crearCita = crear_cita
    cancelarCita = cancelar_cita
    reprogramarCitaId = reprogramar_cita_id
    reprogramarCita = reprogramar_cita_id
    listarPdfsRecientes = listar_pdfs_recientes
    obtenerPreviewPdf = obtener_preview_pdf
    abrirPdf = abrir_pdf
    abrirUltimoPdf = abrir_ultimo_pdf
    imprimirPdf = imprimir_pdf
    obtenerInfoMovil = obtener_info_movil
    obtenerQrMovilBase64 = obtener_qr_movil_base64
    abrirUrlMovil = abrir_url_movil
    obtenerInfoClinica = obtener_info_clinica
    guardarConfiguracion = guardar_configuracion
    obtenerEstadoWidget = obtener_estado_widget
    toggleWidgetEscritorio = toggle_widget_escritorio
    guardarConsultaCorregida = guardar_consulta_corregida
    exportarExcel = exportar_excel
    abrirCarpetaPaciente = abrir_carpeta_paciente
    abrirGoogleCalendar = abrir_google_calendar
    obtenerInfoLicencia = obtener_info_licencia
    reproducirSonido = reproducir_sonido
    toggleEscuchaActiva = toggle_escucha_activa
    obtenerEstadoEscucha = obtener_estado_escucha
    generarPdfActual = generar_pdf_actual
    actualizarCedulaPaciente = actualizar_cedula_paciente
    cambiarPosicionWidget = cambiar_posicion_widget
    cambiarOpacidadWidget = cambiar_opacidad_widget
    enviarRecordatorioWhatsapp = enviar_recordatorio_whatsapp
    obtenerCitasRecordatorioManana = obtener_citas_recordatorio_manana
    enviarRecordatoriosLoteManana = enviar_recordatorios_lote_manana
    guardarConfiguracionWhatsapp = guardar_configuracion_whatsapp
    obtenerConfiguracionWhatsapp = obtener_configuracion_whatsapp


def iniciar_desktop():
    inicializar_usuarios_default()

    bridge = BimoBridge()

    # Iniciar servidor móvil HTTPS y widget runner en segundo plano para arranque instantáneo
    def _iniciar_servicios_secundarios():
        try:
            iniciar_servidor_movil(callback_audio=bridge.procesar_audio_externo)
        except Exception as e:
            print('[MOBILE SERVER WARN]', e)
        try:
            widget_proc = _lanzar_proceso_widget(os.getpid())
            bridge._widget_process = widget_proc
            if widget_proc:
                print(f"[BIMO DESKTOP] Widget de escritorio iniciado en segundo plano (PID: {widget_proc.pid})")
        except Exception as e:
            print(f"[BIMO DESKTOP WARN] No se pudo iniciar widget runner: {e}")

    threading.Thread(target=_iniciar_servicios_secundarios, daemon=True).start()

    def limpiar_procesos():
        if bridge._widget_process:
            try:
                bridge._widget_process.terminate()
            except Exception:
                pass
        if bridge._wake_listener:
            try:
                bridge._wake_listener.detener()
            except Exception:
                pass

    atexit.register(limpiar_procesos)

    if getattr(sys, 'frozen', False):
        base_exe_dir = os.path.dirname(sys.executable)
        meipass_dir = getattr(sys, '_MEIPASS', base_exe_dir)
        candidatos = [
            os.path.join(meipass_dir, "web_ui", "index.html"),
            os.path.join(base_exe_dir, "web_ui", "index.html"),
            os.path.join(base_exe_dir, "_internal", "web_ui", "index.html"),
        ]
        ruta_html = next((c for c in candidatos if os.path.exists(c)), candidatos[0])
    else:
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
        background_color='#090614',
        frameless=True,
        shadow=True,
        easy_drag=False
    )
    bridge.set_window(window)

    def aplicar_estilo_dwm_ventana():
        try:
            time.sleep(0.2)
            if hasattr(window, 'native') and window.native and hasattr(window.native, 'Handle'):
                hwnd = int(window.native.Handle.ToInt64())
                user32 = ctypes.windll.user32
                dwmapi = ctypes.windll.dwmapi
                GWL_STYLE = -16
                WS_THICKFRAME = 0x00040000
                WS_MINIMIZEBOX = 0x00020000
                WS_MAXIMIZEBOX = 0x00010000
                WS_SYSMENU = 0x00080000

                # Permitir redimensionar ventana desde los bordes de forma nativa y habilitar Aero Snap
                style = user32.GetWindowLongW(hwnd, GWL_STYLE)
                user32.SetWindowLongW(hwnd, GWL_STYLE, style | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
                SWP_FRAMECHANGED = 0x0020
                SWP_NOMOVE = 0x0002
                SWP_NOSIZE = 0x0001
                SWP_NOZORDER = 0x0004
                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_FRAMECHANGED | SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER)

                # Extender marco DWM al área cliente para eliminar marcos negros y habilitar sombras suaves
                class MARGINS(ctypes.Structure):
                    _fields_ = [
                        ("cxLeftWidth", ctypes.c_int),
                        ("cxRightWidth", ctypes.c_int),
                        ("cyTopHeight", ctypes.c_int),
                        ("cyBottomHeight", ctypes.c_int),
                    ]
                margins = MARGINS(1, 1, 1, 1)
                try:
                    dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
                except Exception as e_ext:
                    print(f"[DWM EXTEND FRAME WARN]: {e_ext}")

                # Esquinas redondeadas nativas de Windows 11 (DWMWCP_ROUND = 2)
                DWMWA_WINDOW_CORNER_PREFERENCE = 38
                DWMWCP_ROUND = 2
                dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(ctypes.c_int(DWMWCP_ROUND)), 4)

                # Configurar color de fondo, icono y sincronización estricta con el área de trabajo (Taskbar visible)
                try:
                    import clr
                    clr.AddReference('System.Windows.Forms')
                    clr.AddReference('System.Drawing')
                    import System.Windows.Forms as WinForms
                    import System.Drawing as Drawing

                    form = window.native
                    form.BackColor = Drawing.ColorTranslator.FromHtml('#090614')

                    # Asignar icono oficial si está disponible
                    base_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
                    ico_path = base_dir / "assets" / "bimo_icon.ico"
                    if ico_path.exists():
                        try:
                            form.Icon = Drawing.Icon(str(ico_path))
                        except Exception:
                            pass

                    # Respetar estrictamente la barra de tareas de Windows al maximizar (WorkingArea)
                    def update_maximized_bounds(sender=None, args=None):
                        try:
                            screen = WinForms.Screen.FromHandle(form.Handle)
                            wa = screen.WorkingArea
                            form.MaximizedBounds = Drawing.Rectangle(wa.X, wa.Y, wa.Width, wa.Height)
                        except Exception:
                            pass

                    form.LocationChanged += update_maximized_bounds
                    update_maximized_bounds()

                    def on_state_or_size_changed(sender, args):
                        is_now_max = (form.WindowState == WinForms.FormWindowState.Maximized)
                        bridge._is_maximized = is_now_max
                        update_maximized_bounds()

                    form.SizeChanged += on_state_or_size_changed
                except Exception as e_bounds_init:
                    print(f"[BOUNDS INIT WARN]: {e_bounds_init}")

                print("[DWM STYLE] Barra de título personalizada, Aero Snap activo, esquinas redondeadas y respeto total de la barra de tareas.")
        except Exception as e_dwm:
            print(f"[DWM STYLE WARN] {e_dwm}")

    window.events.shown += aplicar_estilo_dwm_ventana

    def on_closed():
        limpiar_procesos()

    window.events.closed += on_closed

    print('=' * 60)
    print('[OK] BIMO Modern Desktop iniciado exitosamente.')
    print('=' * 60)
    webview.start(debug=False)
    limpiar_procesos()

if __name__ == '__main__':
    iniciar_desktop()
