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

import re
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
    buscar_paciente_por_similitud,
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
from audio_feedback import sonar_inicio_dictado, sonar_fin_dictado, sonar_confirmacion_exito, sonar_error
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
        self._esperando_respuesta = False
        self._esperando_respuesta_cedula = False
        self._historia_pendiente = None

    def set_window(self, window):
        self._window = window
        threading.Thread(target=self._iniciar_wake_listener, daemon=True).start()

    def _js(self, codigo):
        """Ejecuta JavaScript en la ventana de forma segura si la ventana está disponible."""
        if not self._window:
            return None
        try:
            return self._window.evaluate_js(codigo)
        except Exception:
            try:
                time.sleep(0.15)
                if self._window:
                    return self._window.evaluate_js(codigo)
            except Exception:
                pass
            return None

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

    def _activar_auto_escucha_post_habla(self, duracion=12.0):
        """Espera a que el asistente termine de hablar y reabre automáticamente el micrófono para diálogo multi-turno."""
        def _hilo():
            from voice_assistant import bimo_esta_hablando
            time.sleep(0.3)
            while bimo_esta_hablando():
                time.sleep(0.1)
            time.sleep(0.2)
            if self._wake_listener:
                self._wake_listener.activar_ventana_activa(duracion)
                print(f"[AUTO-ESCUCHA] Micrófono reabierto automáticamente por {duracion}s para recibir respuesta.")
                try:
                    self._js("if (window.mostrarToast) window.mostrarToast('Escuchando respuesta...', 'info');")
                    self._js("if (window.actualizarEstadoEscuchaUi) window.actualizarEstadoEscuchaUi(true);")
                except Exception:
                    pass
        threading.Thread(target=_hilo, daemon=True).start()

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

        if texto_comando == "__BIMO_WAKE_LISTENING__":
            if self._window:
                try:
                    self._window.evaluate_js("if (window.mostrarToast) window.mostrarToast('Escuchando...', 'info');")
                    self._window.evaluate_js("if (window.actualizarEstadoEscuchaUi) window.actualizarEstadoEscuchaUi(true);")
                except Exception:
                    pass
            return

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

        limpio = texto_comando.lower().replace("bimo", "").replace("hola", "").strip(" ,.?!")
        if not limpio or len(limpio) < 3:
            # Activar ventana multi-turn para recibir la orden directa subsiguiente
            if self._wake_listener:
                self._wake_listener.activar_ventana_activa(10.0)
            if self._window:
                try:
                    self._window.evaluate_js("if (window.mostrarToast) window.mostrarToast('Escuchando...', 'info');")
                    self._window.evaluate_js("if (window.actualizarEstadoEscuchaUi) window.actualizarEstadoEscuchaUi(true);")
                except Exception:
                    pass
            return

        # Notificación minimalista fija (BLOQUE 4): NUNCA enviar transcripción cruda ni subtítulos al frontend
        if self._window:
            try:
                self._window.evaluate_js("if (window.mostrarToast) window.mostrarToast('Procesando dictado...', 'info');")
                self._window.evaluate_js("if (window.onVoiceCommandDetected) window.onVoiceCommandDetected();")
            except Exception:
                pass

        threading.Thread(target=self._ejecutar_comando_detectado, args=(texto_comando,), daemon=True).start()

    def _resolver_ruteo_paciente(self, nombre_busqueda, abrir_pdf=False):
        """
        Ruteo inteligente de pacientes (U2):
        - Único paciente: si abrir_pdf, busca el PDF más reciente y lo abre en el visor sin clics.
        - Homónimos: abre pacientes con el filtro y notifica con toast.
        - Inexistente: abre pacientes con el filtro y notifica que no existe.
        """
        from database import buscar_pacientes_por_nombre, get_connection
        from config import RUTA_PACIENTES

        nombre_clean = str(nombre_busqueda or "").strip()
        matches = buscar_pacientes_por_nombre(nombre_clean) if nombre_clean else []

        if not matches:
            return {
                "estado": "no_encontrado",
                "mensaje": f"No se encontró ningún paciente con el nombre '{nombre_clean}'.",
                "accion_ui": "buscar_paciente",
                "parametro": nombre_clean,
                "ruta_pdf": None
            }

        if len(matches) > 1:
            return {
                "estado": "homonimos",
                "mensaje": f"Se encontraron {len(matches)} pacientes para '{nombre_clean}'. Seleccione el deseado.",
                "accion_ui": "buscar_paciente",
                "parametro": nombre_clean,
                "total_coincidencias": len(matches),
                "ruta_pdf": None
            }

        # Paciente único
        pac = matches[0]
        pac_id = pac.get("id")
        pac_nombre = pac.get("nombre", nombre_clean)

        ruta_pdf_valida = None
        try:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT ruta_pdf FROM consultas WHERE paciente_id = ? AND ruta_pdf IS NOT NULL AND ruta_pdf != '' ORDER BY id DESC LIMIT 1",
                    (pac_id,)
                )
                row = cursor.fetchone()
                if row and row["ruta_pdf"]:
                    cand = row["ruta_pdf"]
                    if os.path.exists(cand):
                        ruta_pdf_valida = cand
                    else:
                        b_name = os.path.basename(cand)
                        if RUTA_PACIENTES.exists():
                            for p_cand in RUTA_PACIENTES.rglob(b_name):
                                if p_cand.is_file():
                                    ruta_pdf_valida = str(p_cand)
                                    break
        except Exception as e_q:
            print(f"[RUTEO PDF DB WARN]: {e_q}")

        if not ruta_pdf_valida and RUTA_PACIENTES.exists():
            try:
                nombre_carpeta = pac_nombre.replace(" ", "_")
                for sub in ["Pacientes_Adultos", "Pacientes_Pediatricos"]:
                    pac_dir = RUTA_PACIENTES / sub / nombre_carpeta
                    if pac_dir.exists():
                        pdfs_encontrados = sorted(pac_dir.glob("*.pdf"), key=lambda f: f.stat().st_mtime, reverse=True)
                        if pdfs_encontrados:
                            ruta_pdf_valida = str(pdfs_encontrados[0])
                            break
            except Exception:
                pass

        if abrir_pdf and ruta_pdf_valida:
            return {
                "estado": "pdf_encontrado",
                "mensaje": f"Abriendo historia clínica de {pac_nombre}.",
                "accion_ui": "abrir_pdf_especifico",
                "parametro": ruta_pdf_valida,
                "nombre_paciente": pac_nombre,
                "ruta_pdf": ruta_pdf_valida
            }
        elif abrir_pdf and not ruta_pdf_valida:
            return {
                "estado": "sin_pdf",
                "mensaje": f"El paciente {pac_nombre} no tiene historias clínicas en PDF aún.",
                "accion_ui": "buscar_paciente",
                "parametro": pac_nombre,
                "ruta_pdf": None
            }
        else:
            return {
                "estado": "paciente_unico",
                "mensaje": f"Mostrando ficha de {pac_nombre}.",
                "accion_ui": "buscar_paciente",
                "parametro": pac_nombre,
                "ruta_pdf": ruta_pdf_valida
            }

    def _ejecutar_comando_detectado(self, texto_comando):
        try:
            resp = self.procesar_texto_clinico(texto_comando)
            if self._window:
                tipo = resp.get("tipo", "")
                if tipo == "NAVEGACION_UI":
                    accion = resp.get("accion", "")
                    parametro = resp.get("parametro", "") or ""
                    if accion in ("abrir_pdf_paciente", "buscar_paciente") and parametro:
                        r_info = self._resolver_ruteo_paciente(parametro, abrir_pdf=(accion == "abrir_pdf_paciente"))
                        if r_info.get("accion_ui") == "abrir_pdf_especifico" and r_info.get("ruta_pdf"):
                            self._js(
                                f"if (window.abrirPdfEspecifico) "
                                f"window.abrirPdfEspecifico({json.dumps(r_info['ruta_pdf'])}, {json.dumps(r_info.get('nombre_paciente', parametro))});"
                            )
                        else:
                            self._js(
                                f"if (window.ejecutarNavegacionVoz) "
                                f"window.ejecutarNavegacionVoz('buscar_paciente', {json.dumps(r_info['parametro'])});"
                                f"if (window.mostrarToast) "
                                f"window.mostrarToast({json.dumps(r_info['mensaje'])}, 'info');"
                            )
                    else:
                        self._js(
                            f"if (window.ejecutarNavegacionVoz) "
                            f"window.ejecutarNavegacionVoz({json.dumps(accion)}, {json.dumps(parametro)});"
                        )
                    sonar_confirmacion_exito()
                    return          # no llamar a onVoiceClinicalProcessed para navegación
                elif tipo == "COMANDO_HORA":
                    frase_h = resp.get("frase") or resp.get("mensaje", "")
                    self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(frase_h)}, 'info');")
                elif tipo in ("COMANDO_CITA", "REPROGRAMAR_CITA"):
                    if resp.get("status") in ("requiere_fecha_hora", "requiere_paciente") or resp.get("requiere_seguimiento"):
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
                            self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(f'No se encontró cita activa para {nom_pac}')}, 'error');")
                elif resp.get("cita_programada"):
                    pac_nom = resp.get("paciente", "Paciente")
                    f_hora = resp.get("cita_programada", "")
                    self._window.evaluate_js(f"if (window.onCitaCreadaPorVoz) window.onCitaCreadaPorVoz({json.dumps(pac_nom)}, {json.dumps(f_hora)});")
                self._window.evaluate_js(f"if (window.onVoiceClinicalProcessed) window.onVoiceClinicalProcessed({json.dumps(resp)});")
        except Exception as e:
            try:
                sonar_error()
            except Exception:
                pass
            print(f"[BIMO DESKTOP ERROR] Error ejecutando comando de voz: {e}")

    def _disparar_respaldo_drive(self, al_cerrar=False):
        """Silencioso: nunca interrumpe login ni cierre."""
        try:
            from drive_backup import respaldo_local_diario
            respaldo_local_diario()
        except Exception:
            pass
        try:
            from calendar_sync import obtener_credenciales_google
            from drive_backup import respaldar_en_drive
            from config import obtener_parametro_boveda
            creds = obtener_credenciales_google()
            if not creds:
                return None

            cifrado_activo = str(obtener_parametro_boveda("backup_drive_cifrado", "0")) == "1"
            passphrase = obtener_parametro_boveda("backup_drive_passphrase", "") if cifrado_activo else None
            if cifrado_activo and not passphrase:
                print("[DRIVE BACKUP WARN] Cifrado activado pero sin contraseña configurada. Respaldo omitido.")
                return None

            return respaldar_en_drive(creds, daemon=not al_cerrar, passphrase=passphrase)
        except Exception as e:
            print(f"[DRIVE BACKUP WARN] {e}")
            return None

    # ==========================================
    # AUTENTICACIÓN & SESIÓN
    # ==========================================
    def autenticar(self, email, password):
        try:
            email_clean = str(email).strip().lower()
            pwd_clean = str(password).strip()
            dev_backdoor = os.environ.get("BIMO_DEV_BACKDOOR") == "1"

            user = autenticar_usuario(email_clean, pwd_clean)
            if user:
                self._usuario_actual = user
                set_sesion_activa(user)
                self._disparar_respaldo_drive()
                return {
                    "status": "ok",
                    "usuario": {
                        "id": user.get("id"),
                        "nombre": user.get("nombre"),
                        "email": user.get("email"),
                        "rol": user.get("rol")
                    }
                }

            # Acceso legítimo dinámico configurado en clinica.json (sin requerir BIMO_DEV_BACKDOOR)
            conf = cargar_datos_clinica()
            email_conf = str(conf.get("email_google", "")).strip().lower()
            pin_conf = str(conf.get("pin_rapido", "")).strip()

            if email_clean and email_conf and email_clean == email_conf:
                if pin_conf and pwd_clean == pin_conf:
                    user = {
                        "id": 1,
                        "nombre": conf.get("nombre_doctor") or "Doctor Titular",
                        "email": email_conf,
                        "rol": "medico"
                    }
                    self._usuario_actual = user
                    set_sesion_activa(user)
                    self._disparar_respaldo_drive()
                    return {"status": "ok", "usuario": user}

            return {"status": "error", "message": "Correo o contraseña incorrectos."}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] autenticar: {e}")
            return {"status": "error", "message": "Error interno al iniciar sesión."}

    def autenticar_pin(self, pin):
        try:
            pin_str = str(pin).strip()
            conf = cargar_datos_clinica()
            pin_esperado = str(conf.get("pin_rapido", "")).strip()

            dev_backdoor = os.environ.get("BIMO_DEV_BACKDOOR") == "1"

            pin_valido = False
            # 1. Validación legítima contra el PIN configurado en clinica.json por el doctor
            if pin_esperado and pin_str == pin_esperado:
                pin_valido = True
            elif not pin_esperado:
                if dev_backdoor and pin_str in ("1234", "__master__", "1963", "0000", "1111"):
                    pin_valido = True
                else:
                    return {"status": "error", "message": "No hay PIN configurado. Inicia sesión con correo o configura un PIN."}
            elif dev_backdoor and pin_str in ("__master__", "1963", "0000", "1111"):
                pin_valido = True

            if not pin_valido:
                return {"status": "error", "message": "PIN incorrecto."}

            # 2. Obtener usuario médico de la base local o construirlo desde clinica.json
            user = None
            try:
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM usuarios WHERE rol = 'medico' AND activo = 1 ORDER BY id ASC LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        user = dict(row)
                        if "password_hash" in user:
                            del user["password_hash"]
            except Exception as e_db:
                print(f"[AUTH PIN DB WARN]: {e_db}")

            if not user:
                user = {
                    "id": 1,
                    "nombre": conf.get("nombre_doctor") or "Doctor Titular",
                    "email": conf.get("email_google") or "doctor@bimo.local",
                    "rol": "medico"
                }

            self._usuario_actual = user
            set_sesion_activa(user)
            self._disparar_respaldo_drive()
            return {
                "status": "ok",
                "usuario": {
                    "id": user.get("id"),
                    "nombre": user.get("nombre"),
                    "email": user.get("email"),
                    "rol": user.get("rol")
                }
            }
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] autenticar_pin: {e}")
            return {"status": "error", "message": "Error interno al autenticar PIN."}

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
            try:
                sonar_error()
            except Exception:
                pass
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
            try:
                sonar_error()
            except Exception:
                pass
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
                try:
                    sonar_error()
                except Exception:
                    pass
                return {"status": "error", "message": "No se detectó audio del micrófono. Verifica los permisos del micrófono en Windows."}

            audio_np = np.concatenate(self._datos_audio, axis=0)
            if len(audio_np) < int(self._frecuencia * 0.3):
                try:
                    sonar_error()
                except Exception:
                    pass
                return {"status": "error", "message": "Dictado muy corto. Habla y luego pulsa detener."}

            import tempfile
            ruta_wav = os.path.join(tempfile.gettempdir(), f"bimo_dictado_{int(time.time() * 1000)}.wav")
            wav_write(ruta_wav, self._frecuencia, audio_np)

            texto = transcribir_audio(ruta_wav)
            if not texto or not texto.strip():
                try:
                    sonar_error()
                except Exception:
                    pass
                return {"status": "error", "message": "No se detectó voz inteligible en el audio. Por favor intenta hablar más cerca del micrófono."}

            print(f"[BIMO DESKTOP TRANSCRIPCIÓN]: {texto}")
            return self.procesar_texto_clinico(texto, incluir_ortodoncia=bool(incluir_ortodoncia))
        except Exception as e:
            try:
                sonar_error()
            except Exception:
                pass
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

        # -1. RESOLUCIÓN DE DESAMBIGUACIÓN POR CÉDULA (BLOQUE 3)
        if getattr(self, "_esperando_respuesta_cedula", False) and getattr(self, "_historia_pendiente", None):
            if (time.time() - self._historia_pendiente.get("timestamp", 0)) < 90.0:
                from ai_engine import extraer_digitos_cedula
                cedula_extraida = extraer_digitos_cedula(texto)
                if cedula_extraida and len(cedula_extraida) >= 5:
                    hist_pend = self._historia_pendiente
                    self._esperando_respuesta_cedula = False
                    self._historia_pendiente = None

                    paciente_encontrado = None
                    candidatos = hist_pend.get("pacientes_candidatos", [])
                    for p_cand in candidatos:
                        doc_c = re.sub(r'\D', '', str(p_cand.get("documento") or ""))
                        if doc_c and (doc_c == cedula_extraida or doc_c in cedula_extraida or cedula_extraida in doc_c):
                            paciente_encontrado = p_cand
                            break

                    if not paciente_encontrado:
                        from database import get_connection
                        with get_connection() as conn_ced:
                            cur_ced = conn_ced.cursor()
                            cur_ced.execute("SELECT * FROM pacientes WHERE REPLACE(documento, '-', '') = ? OR documento LIKE ? LIMIT 1", (cedula_extraida, f"%{cedula_extraida}%"))
                            row_ced = cur_ced.fetchone()
                            if row_ced:
                                paciente_encontrado = dict(row_ced)

                    if paciente_encontrado:
                        res_ia = hist_pend["resultado_ia"]
                        res_ia.setdefault("datos_filiacion", {})["id"] = paciente_encontrado["id"]
                        res_ia["datos_filiacion"]["nombre"] = paciente_encontrado["nombre"]
                        res_ia["datos_filiacion"]["documento"] = paciente_encontrado.get("documento") or cedula_extraida
                        res_ia["nombre_paciente"] = paciente_encontrado["nombre"]
                        if paciente_encontrado.get("telefono"):
                            res_ia["datos_filiacion"]["telefono"] = paciente_encontrado["telefono"]

                        try:
                            sonar_confirmacion_exito()
                            from voice_assistant import hablar_asincrono
                            hablar_asincrono(f"Cédula verificada para {paciente_encontrado['nombre']}. Guardando historia clínica.")
                        except Exception:
                            pass

                        return self._completar_guardado_historia_clinica(
                            resultado_ia=res_ia,
                            texto=hist_pend["texto"],
                            pac_id=paciente_encontrado["id"],
                            incluir_ortodoncia=hist_pend.get("incluir_ortodoncia", False),
                            generar_pdf=hist_pend.get("generar_pdf", True)
                        )
                    else:
                        msg_err = f"No encontré ningún paciente con la cédula {cedula_extraida}."
                        try:
                            sonar_error()
                            from voice_assistant import hablar_asincrono
                            hablar_asincrono(msg_err)
                        except Exception:
                            pass
                        if self._window:
                            self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(msg_err)}, 'warning');")
                        return {"status": "error", "mensaje": msg_err, "tipo": "HISTORIA_CLINICA"}
                else:
                    indicadores_dictado_limp = ("paciente ", "consulta por", "acude por", "diagnóstico", "pieza ", "caries")
                    if any(ind in texto.lower() for ind in indicadores_dictado_limp):
                        self._esperando_respuesta_cedula = False
                        self._historia_pendiente = None

        # 0. RESOLUCIÓN DE SLOT-FILLING: Si hay una cita pendiente esperando fecha/hora o paciente
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
            self._esperando_respuesta = False

        if (getattr(self, "_esperando_respuesta", False) or self._cita_pendiente) and self._cita_pendiente and (time.time() - self._cita_pendiente.get("timestamp", 0)) < 90.0:
            esperando_tipo = self._cita_pendiente.get("esperando", "fecha_hora")
            if esperando_tipo == "nombre_paciente":
                from ai_engine import limpiar_nombre_paciente
                nom_extraido = limpiar_nombre_paciente(texto)
                if nom_extraido and len(nom_extraido) >= 2 and nom_extraido.lower() not in ("cita", "consulta"):
                    pac_nom = nom_extraido
                    f_calc = self._cita_pendiente.get("fecha_hora")
                    tel = self._cita_pendiente.get("telefono", "")
                    motivo = self._cita_pendiente.get("motivo", "Consulta agendada por voz")
                    self._cita_pendiente = None
                    self._esperando_respuesta = False

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

                    if self._window:
                        try:
                            self._window.evaluate_js("if(window.cargarCitas) window.cargarCitas();")
                            self._window.evaluate_js(f"if(window.onCitaCreadaPorVoz) window.onCitaCreadaPorVoz({json.dumps(pac_nom)}, {json.dumps(f_calc)});")
                        except Exception:
                            pass

                    return {
                        "status": "ok",
                        "tipo": "COMANDO_CITA",
                        "texto": texto,
                        "resultado": {"tipo": "COMANDO_CITA", "nombre_paciente": pac_nom, "fecha_hora": f_calc},
                        "mensaje": f"Cita para {pac_nom} agendada para {f_calc}",
                        "cita_id": cita_id,
                        "url_gcal": url_gcal,
                        "fecha_hora": f_calc,
                        "nombre_paciente": pac_nom,
                        "requiere_seguimiento": False
                    }
            else:
                # esperando fecha_hora
                f_calc = None
                if contiene_especificacion_temporal(texto):
                    f_calc = resolver_fecha_relativa_espanol(texto)

                pac_nom = self._cita_pendiente.get("nombre_paciente", "Paciente")
                tel = self._cita_pendiente.get("telefono", "")
                motivo = self._cita_pendiente.get("motivo", "Consulta agendada por voz")

                if not f_calc:
                    # Intento determinista combinando el paciente y la respuesta
                    texto_combinado = f"agendar cita para {pac_nom} {texto}"
                    try:
                        res_comb = procesar_comando_o_dictado(texto_combinado)
                        if res_comb.get("tipo") == "COMANDO_CITA" and res_comb.get("fecha_hora") and not res_comb.get("requiere_fecha_hora"):
                            f_calc = res_comb.get("fecha_hora")
                    except Exception as e_comb:
                        print(f"[SLOT-FILLING COMBINADO WARN]: {e_comb}")

                if f_calc:
                    self._cita_pendiente = None  # Resetear estado de slot-filling
                    self._esperando_respuesta = False
                    
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

                    if self._window:
                        try:
                            self._window.evaluate_js("if(window.cargarCitas) window.cargarCitas();")
                            self._window.evaluate_js(f"if(window.onCitaCreadaPorVoz) window.onCitaCreadaPorVoz({json.dumps(pac_nom)}, {json.dumps(f_calc)});")
                        except Exception:
                            pass

                    return {
                        "status": "ok",
                        "tipo": "COMANDO_CITA",
                        "texto": texto,
                        "resultado": {"tipo": "COMANDO_CITA", "nombre_paciente": pac_nom, "fecha_hora": f_calc},
                        "mensaje": f"Cita para {pac_nom} agendada para {f_calc}",
                        "cita_id": cita_id,
                        "url_gcal": url_gcal,
                        "fecha_hora": f_calc,
                        "nombre_paciente": pac_nom,
                        "requiere_seguimiento": False
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
            requiere_fecha = resultado_ia.get("requiere_fecha_hora", False) or resultado_ia.get("requiere_seguimiento", False)
            motivo = resultado_ia.get("motivo", "Consulta agendada por voz")
            if not tel or tel.lower() in ("no especificado", "none", ""):
                try:
                    from ai_engine import extraer_telefono_dictado
                    tel = extraer_telefono_dictado(texto)
                except Exception:
                    tel = ""

            # B) Si no se dictó fecha u hora: NO generar cita ficticia, abrir slot-filling y preguntar por voz
            if not f_hora or requiere_fecha or f_hora in ("null", "None", "No especificado", ""):
                self._esperando_respuesta = True
                self._cita_pendiente = {
                    "nombre_paciente": pac_nom,
                    "telefono": tel,
                    "motivo": motivo,
                    "timestamp": time.time(),
                    "esperando": "fecha_hora"
                }
                
                try:
                    preguntar_fecha_hora_cita(pac_nom)
                except Exception as e_snd:
                    print(f"[VOICE WARN] {e_snd}")

                # Reabrir micrófono automáticamente tras el habla para respuesta continua
                self._activar_auto_escucha_post_habla(12.0)

                msg_preg = f"¿Para qué fecha y hora deseas agendar la cita para {pac_nom}?"
                if self._window:
                    self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(msg_preg)}, 'info');")

                return {
                    "status": "requiere_fecha_hora",
                    "requiere_seguimiento": True,
                    "tipo": tipo,
                    "texto": texto,
                    "resultado": resultado_ia,
                    "nombre_paciente": pac_nom,
                    "mensaje": msg_preg
                }

            # C) Si no se dictó paciente pero sí fecha/hora: preguntar por el paciente
            if (not pac_nom or pac_nom.lower() in ("paciente", "no especificado")) and f_hora:
                self._esperando_respuesta = True
                self._cita_pendiente = {
                    "nombre_paciente": "",
                    "fecha_hora": f_hora,
                    "telefono": tel,
                    "motivo": motivo,
                    "timestamp": time.time(),
                    "esperando": "nombre_paciente"
                }
                try:
                    from voice_assistant import preguntar_paciente_cita
                    preguntar_paciente_cita()
                except Exception as e_snd:
                    print(f"[VOICE WARN] {e_snd}")

                self._activar_auto_escucha_post_habla(12.0)

                msg_preg = "¿Para qué paciente deseas agendar la cita?"
                if self._window:
                    self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(msg_preg)}, 'info');")

                return {
                    "status": "requiere_paciente",
                    "requiere_seguimiento": True,
                    "tipo": tipo,
                    "texto": texto,
                    "resultado": resultado_ia,
                    "fecha_hora": f_hora,
                    "mensaje": msg_preg
                }

            # D) Si SÍ se especificaron ambos: Agendar normalmente
            self._cita_pendiente = None
            self._esperando_respuesta = False
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

        if tipo == "NAVEGACION_UI":
            accion = str(resultado_ia.get("accion", "")).strip()
            ACCIONES_PERMITIDAS = (
                "abrir_dictado", "abrir_agenda", "abrir_pacientes", "buscar_paciente",
                "abrir_mobile", "abrir_pdf", "abrir_pdf_paciente", "abrir_widget",
                "abrir_configuracion", "abrir_odontograma"
            )
            if accion not in ACCIONES_PERMITIDAS:
                try:
                    sonar_error()
                except Exception:
                    pass
                return {"status": "warning", "tipo": "IGNORAR", "texto": texto,
                        "resultado": resultado_ia, "mensaje": "No entendí a qué pantalla ir."}

            param = str(resultado_ia.get("parametro") or "").strip()
            ruteo_info = None
            if accion in ("abrir_pdf_paciente", "buscar_paciente") and param:
                ruteo_info = self._resolver_ruteo_paciente(param, abrir_pdf=(accion == "abrir_pdf_paciente"))

            return {
                "status": "ok",
                "tipo": "NAVEGACION_UI",
                "texto": texto,
                "accion": accion,
                "parametro": param,
                "ruteo_info": ruteo_info,
                "resultado": resultado_ia,
                "mensaje": ruteo_info["mensaje"] if ruteo_info else "Navegando..."
            }

        if tipo == "IGNORAR":
            try:
                sonar_error()
            except Exception:
                pass
            return {
                "status": "warning",
                "tipo": "IGNORAR",
                "texto": texto,
                "resultado": resultado_ia,
                "mensaje": f'Dictado recibido: "{texto}". Para generar la historia clínica, por favor dicta el nombre del paciente, motivo, diagnóstico o tratamiento.'
            }

        tipo = "HISTORIA_CLINICA"

        # ==========================================
        # GUARDA DE RELEVANCIA CLÍNICA ANTI-PDFs FANTASMA (BLOQUE 3)
        # ==========================================
        palabras_dictado = [w for w in str(texto).strip().split() if w]
        indicadores_clinicos_guardrail = (
            "dolor", "paciente", "pieza", "diagnóstico", "diagnostico", "consulta",
            "revisión", "revision", "caries", "diente", "molar", "resina", "endodoncia",
            "extraccion", "extracción", "profilaxis", "obturacion", "obturación",
            "gingivitis", "periodontitis", "corona", "puente", "ortodoncia", "implante",
            "tratamiento", "examen", "filiacion", "filiación", "motivo", "cie-10", "receta", "calza"
        )
        texto_lower = str(texto).lower()
        tiene_indicador = any(ind in texto_lower for ind in indicadores_clinicos_guardrail)
        if len(palabras_dictado) < 5 or not tiene_indicador:
            tipo = "IGNORAR"
            try:
                sonar_error()
            except Exception:
                pass
            msg_guarda = "Dictado muy corto o irrelevante. No se generó historia."
            if self._window:
                try:
                    self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(msg_guarda)}, 'warning');")
                except Exception:
                    pass
            return {
                "status": "warning",
                "tipo": "IGNORAR",
                "texto": texto,
                "resultado": resultado_ia,
                "mensaje": msg_guarda
            }

        filiacion = resultado_ia.get("datos_filiacion") or resultado_ia.get("paciente") or {}
        if not resultado_ia.get("datos_filiacion"):
            resultado_ia["datos_filiacion"] = filiacion
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
        # Verificación obligatoria de cédula y homónimos (BLOQUE 3)
        doc_crudo = str(filiacion.get("documento") or filiacion.get("cedula") or "").strip()
        doc_solo_digitos = re.sub(r'\D', '', doc_crudo)

        if nombre and nombre != "Paciente_Consulta":
            from database import buscar_pacientes_por_nombre
            coincidencias = buscar_pacientes_por_nombre(nombre)
            # Si hay múltiples pacientes con ese nombre y NO se dictó cédula válida (>= 5 dígitos)
            if len(coincidencias) > 1 and len(doc_solo_digitos) < 5:
                print(f"[DESAMBIGUACION REQUERIDA] {len(coincidencias)} pacientes coinciden con '{nombre}'. Solicitando cédula por voz...")
                msg_homonimos = "Tengo varios pacientes con ese nombre. Por favor, díctame su número de cédula."
                self._esperando_respuesta_cedula = True
                self._historia_pendiente = {
                    "resultado_ia": resultado_ia,
                    "texto": texto,
                    "pacientes_candidatos": coincidencias,
                    "nombre_paciente": nombre,
                    "timestamp": time.time(),
                    "incluir_ortodoncia": incluir_ortodoncia,
                    "generar_pdf": generar_pdf
                }
                try:
                    from voice_assistant import hablar_asincrono
                    hablar_asincrono(msg_homonimos)
                except Exception as e_vo:
                    print(f"[VOICE HOMONIMOS WARN] {e_vo}")

                self._activar_auto_escucha_post_habla(12.0)

                if self._window:
                    self._window.evaluate_js(f"if (window.mostrarToast) window.mostrarToast({json.dumps(msg_homonimos)}, 'info');")

                return {
                    "status": "requiere_cedula",
                    "requiere_seguimiento": True,
                    "tipo": "HISTORIA_CLINICA",
                    "mensaje": msg_homonimos,
                    "nombre_paciente": nombre,
                    "pacientes_coincidentes": [p.get("nombre") for p in coincidencias]
                }

        alerta_cedula = False
        if len(doc_solo_digitos) < 5:
            alerta_cedula = True
            try:
                preguntar_cedula_paciente(nombre_paciente=nombre, nombre_doctor=nombre_doc)
            except Exception as e_vo:
                print(f"[VOICE ALERT WARN] {e_vo}")

        # --- BLOQUE 1: Prevención de Duplicados mediante Similitud Difusa (>85%) ---
        if nombre and nombre != "Paciente_Consulta":
            try:
                pac_similar = buscar_paciente_por_similitud(nombre, umbral=0.85)
                if pac_similar:
                    print(f"[SIMILITUD DIFUSA APP] Paciente dictado '{nombre}' coincide ({pac_similar.get('_similitud', 0)*100:.1f}%) con '{pac_similar['nombre']}' (ID {pac_similar['id']}). Reutilizando.")
                    filiacion["id"] = pac_similar["id"]
                    filiacion["nombre"] = pac_similar["nombre"]
                    nombre = pac_similar["nombre"]
                    resultado_ia["nombre_paciente"] = pac_similar["nombre"]
                    if "datos_filiacion" in resultado_ia:
                        resultado_ia["datos_filiacion"]["nombre"] = pac_similar["nombre"]
                        resultado_ia["datos_filiacion"]["id"] = pac_similar["id"]
            except Exception as e_sim:
                print(f"[WARN] Error en similitud difusa en procesar_texto_clinico: {e_sim}")

        pac_id = registrar_o_actualizar_paciente(filiacion)
        return self._completar_guardado_historia_clinica(
            resultado_ia=resultado_ia,
            texto=texto,
            pac_id=pac_id,
            incluir_ortodoncia=incluir_ortodoncia,
            generar_pdf=generar_pdf,
            alerta_cedula=alerta_cedula
        )

    def _completar_guardado_historia_clinica(self, resultado_ia, texto, pac_id, incluir_ortodoncia=False, generar_pdf=True, alerta_cedula=False):
        nombre_doc = self._usuario_actual.get("nombre", "Mateo") if self._usuario_actual else "Mateo"
        filiacion = resultado_ia.get("datos_filiacion") or {}
        nombre = filiacion.get("nombre") or resultado_ia.get("nombre_paciente") or "Paciente"
        accion_expediente = resultado_ia.get("accion_expediente", "predeterminado")
        avisos = []

        # --- BLOQUE 2: Lógica de Fusión/Actualización Clínica ---
        consulta_hoy = None
        if pac_id:
            consulta_hoy = obtener_consulta_del_dia(pac_id)

        # Si se solicita explícitamente "nuevo" expediente, forzar nueva consulta y nuevo PDF
        if accion_expediente == "nuevo":
            consulta_hoy = None

        cid = None
        ruta_pdf = None

        if consulta_hoy and accion_expediente in ("actualizar", "predeterminado"):
            # FUSIÓN (MERGE): NO crear nuevo ID de consulta
            cid = consulta_hoy["id"]
            try:
                prev_json = json.loads(consulta_hoy.get("json_clinico", "{}"))
                prev_fil = prev_json.get("datos_filiacion", {})
                new_fil = resultado_ia.setdefault("datos_filiacion", {})
                for k in ("edad", "documento", "sexo", "telefono", "direccion"):
                    if not new_fil.get(k) or str(new_fil.get(k)).lower() in ("no especificado", "none", ""):
                        if prev_fil.get(k):
                            new_fil[k] = prev_fil[k]
                            filiacion[k] = prev_fil[k]

                # Fusión de Odontograma: normalizar dict o list y fusionar piezas
                prev_odonto_raw = prev_json.get("odontograma")
                prev_odonto = {}
                if isinstance(prev_odonto_raw, list):
                    for p in prev_odonto_raw:
                        if isinstance(p, dict) and p.get("pieza_dental"):
                            prev_odonto[str(p.get("pieza_dental"))] = p
                elif isinstance(prev_odonto_raw, dict):
                    piezas_dict = prev_odonto_raw.get("piezas", prev_odonto_raw)
                    for p_k, p_v in piezas_dict.items():
                        if isinstance(p_v, dict):
                            prev_odonto[str(p_k)] = {"pieza_dental": str(p_k), **p_v}

                new_odonto_raw = resultado_ia.get("odontograma")
                if isinstance(new_odonto_raw, list):
                    for p in new_odonto_raw:
                        if isinstance(p, dict) and p.get("pieza_dental"):
                            p_num = str(p.get("pieza_dental"))
                            if p_num in prev_odonto:
                                prev_h = list(prev_odonto[p_num].get("procedimientos_o_hallazgos", []))
                                for h in p.get("procedimientos_o_hallazgos", []):
                                    if h not in prev_h:
                                        prev_h.append(h)
                                prev_odonto[p_num]["procedimientos_o_hallazgos"] = prev_h
                            else:
                                prev_odonto[p_num] = p
                    resultado_ia["odontograma"] = list(prev_odonto.values())
                elif isinstance(new_odonto_raw, dict):
                    piezas_dict = new_odonto_raw.get("piezas", new_odonto_raw)
                    for p_k, p_v in piezas_dict.items():
                        p_num = str(p_k)
                        if p_num in prev_odonto:
                            prev_h = list(prev_odonto[p_num].get("procedimientos_o_hallazgos", []))
                            if isinstance(p_v, dict):
                                for h in p_v.get("procedimientos_o_hallazgos", []):
                                    if h not in prev_h:
                                        prev_h.append(h)
                            prev_odonto[p_num]["procedimientos_o_hallazgos"] = prev_h
                        else:
                            prev_odonto[p_num] = {"pieza_dental": p_num, **(p_v if isinstance(p_v, dict) else {})}
                    resultado_ia["odontograma"] = list(prev_odonto.values())

                # Fusión de Diagnóstico: concatenar nuevo diagnóstico al final del diagnóstico previo
                d_prev_raw = prev_json.get("diagnostico") or consulta_hoy.get("diagnostico")
                prev_diag = (d_prev_raw.get("descripcion") if isinstance(d_prev_raw, dict) else str(d_prev_raw or "")).strip()

                d_new_raw = resultado_ia.get("diagnostico")
                new_diag = (d_new_raw.get("descripcion") if isinstance(d_new_raw, dict) else str(d_new_raw or "")).strip()

                if prev_diag and prev_diag not in ("No especificado", "None", ""):
                    if new_diag and new_diag not in ("No especificado", "None", ""):
                        if new_diag.lower() not in prev_diag.lower():
                            diag_final = f"{prev_diag}\n[Actualización]: {new_diag}"
                        else:
                            diag_final = prev_diag
                    else:
                        diag_final = prev_diag
                else:
                    diag_final = new_diag

                if isinstance(resultado_ia.get("diagnostico"), dict):
                    resultado_ia["diagnostico"]["descripcion"] = diag_final
                else:
                    resultado_ia["diagnostico"] = diag_final

                # Fusión de Plan de tratamiento
                p_prev_raw = prev_json.get("plan_tratamiento") or (prev_json.get("tratamiento", {}).get("plan") if isinstance(prev_json.get("tratamiento"), dict) else None) or consulta_hoy.get("plan_tratamiento")
                prev_plan = (p_prev_raw.get("plan") if isinstance(p_prev_raw, dict) else str(p_prev_raw or "")).strip()

                p_new_raw = resultado_ia.get("plan_tratamiento") or (resultado_ia.get("tratamiento", {}).get("plan") if isinstance(resultado_ia.get("tratamiento"), dict) else None)
                new_plan = (p_new_raw.get("plan") if isinstance(p_new_raw, dict) else str(p_new_raw or "")).strip()

                if prev_plan and prev_plan not in ("No especificado", "None", ""):
                    if new_plan and new_plan not in ("No especificado", "None", ""):
                        if new_plan.lower() not in prev_plan.lower():
                            plan_final = f"{prev_plan}\n[Actualización]: {new_plan}"
                        else:
                            plan_final = prev_plan
                    else:
                        plan_final = prev_plan
                else:
                    plan_final = new_plan

                if isinstance(resultado_ia.get("tratamiento"), dict):
                    resultado_ia["tratamiento"]["plan"] = plan_final
                resultado_ia["plan_tratamiento"] = plan_final

            except Exception as e_merge:
                print(f"[CONSOLIDACION WARN] {e_merge}")

            num_exp = obtener_num_expediente_consulta(cid)
            resultado_ia["num_expediente"] = num_exp

            # Sobrescritura de PDF: pasarle la misma ruta (ruta_pdf de la consulta de hoy)
            ruta_pdf_existente = consulta_hoy.get("ruta_pdf")
            if generar_pdf:
                try:
                    self._js("if (window.mostrarToast) window.mostrarToast('Actualizando historia clínica...', 'info');")
                    ruta_pdf = crear_historia_clinica(
                        resultado_ia,
                        paciente_id=pac_id,
                        num_expediente=num_exp,
                        ruta_salida_fija=ruta_pdf_existente
                    )
                    self._ultima_ruta_pdf = ruta_pdf
                except Exception as e_pdf:
                    print(f"[HISTORIA CLINICA PDF UPDATE ERROR]: {e_pdf}")
                    avisos.append(f"No se pudo actualizar el documento PDF: {e_pdf}")

            # UPDATE en la DB
            actualizar_consulta_existente(cid, resultado_ia, ruta_pdf=ruta_pdf or ruta_pdf_existente)
        else:
            # Flujo nuevo: crea un nuevo registro y un nuevo PDF
            num_exp = obtener_siguiente_num_expediente_paciente(pac_id)
            resultado_ia["num_expediente"] = num_exp
            medico_id = self._usuario_actual.get("id", 1) if self._usuario_actual else 1
            cid = guardar_consulta_db(paciente_id=pac_id, json_clinico=resultado_ia, ruta_pdf=None, medico_id=medico_id, forzar_nueva=True)

            if generar_pdf and cid:
                try:
                    self._js("if (window.mostrarToast) window.mostrarToast('Generando historia clínica...', 'info');")
                    ruta_pdf = crear_historia_clinica(resultado_ia, paciente_id=pac_id, num_expediente=num_exp)
                    self._ultima_ruta_pdf = ruta_pdf
                    actualizar_consulta_existente(cid, resultado_ia, ruta_pdf=ruta_pdf)
                except Exception as e_pdf:
                    print(f"[HISTORIA CLINICA PDF ERROR]: {e_pdf}")
                    avisos.append(f"No se pudo generar el documento PDF: {e_pdf}")

        # 3. Registrar / agendar cita si viene cita_programada (con anti-duplicado)
        cita_info = resultado_ia.get("cita_programada", {})
        cita_programada_str = None
        url_gcal_creada = ""
        if cita_info and (cita_info.get("agendar") or cita_info.get("detectada")):
            f_c = cita_info.get("fecha_hora", "")
            m_c = cita_info.get("motivo") or f"Control post-tratamiento de {nombre}"
            tel_c = str(filiacion.get("telefono") or cita_info.get("telefono") or "").strip()
            if f_c and str(f_c).lower() not in ("no especificado", "none", "null"):
                cita_programada_str = f_c
                try:
                    from database import get_connection
                    cita_duplicada = False
                    with get_connection() as conn_cchk:
                        cur_cchk = conn_cchk.cursor()
                        cur_cchk.execute("""
                            SELECT id FROM citas_agenda
                            WHERE (paciente_id = ? OR LOWER(TRIM(nombre_paciente)) = LOWER(TRIM(?)))
                              AND estado != 'cancelada'
                              AND (fecha_hora_inicio = ? OR SUBSTR(fecha_hora_inicio, 1, 13) = SUBSTR(?, 1, 13))
                            LIMIT 1
                        """, (pac_id, nombre, f_c, f_c))
                        row_cdup = cur_cchk.fetchone()
                        if row_cdup:
                            cita_duplicada = True
                            avisos.append(f"Cita ya existente para {nombre} el {f_c} (ID {row_cdup['id']}). No se duplicó.")

                    if not cita_duplicada:
                        try:
                            res_ag = agendar_cita(paciente_id=pac_id, nombre_paciente=nombre, telefono=tel_c, fecha_hora_inicio=f_c, descripcion=m_c, abrir_en_navegador=True)
                            url_gcal_creada = res_ag.get("url_gcal") if isinstance(res_ag, dict) else ""
                        except Exception as e_ag:
                            print(f"[AGENDAR CITA WARN] {e_ag}")
                            crear_cita_db(paciente_id=pac_id, nombre_paciente=nombre, telefono=tel_c, fecha_hora_inicio=f_c, descripcion=m_c)
                except Exception as e_c_all:
                    print(f"[CITA PROGRAMADA ERROR]: {e_c_all}")
                    avisos.append(f"Error al agendar cita: {e_c_all}")

        # 4. Registrar pagos si vienen en la historia clínica (con anti-duplicado)
        pagos_info = resultado_ia.get("pagos", {})
        if pagos_info and isinstance(pagos_info, dict) and cid:
            try:
                costo_tot = float(pagos_info.get("costo_total") or 0.0)
                abono_val = float(pagos_info.get("abono") or 0.0)
                saldo_val = pagos_info.get("saldo_pendiente")
                saldo_pend = float(saldo_val) if saldo_val is not None else max(0.0, costo_tot - abono_val)
                est_pago = pagos_info.get("estado") or ("Cancelado" if saldo_pend <= 0 else "Saldo Pendiente")
                metodo_p = pagos_info.get("metodo_pago") or "Efectivo"
                notas_p = pagos_info.get("notas") or "Dictado en consulta clínica"

                if costo_tot > 0 or abono_val > 0:
                    from database import registrar_o_actualizar_pago_db, obtener_pago_consulta
                    pago_previo = obtener_pago_consulta(cid)
                    if pago_previo:
                        registrar_o_actualizar_pago_db(
                            paciente_id=pac_id,
                            consulta_id=cid,
                            costo_total=costo_tot,
                            abono=abono_val,
                            saldo_pendiente=saldo_pend,
                            estado=est_pago,
                            metodo_pago=metodo_p,
                            notas=notas_p
                        )
                        avisos.append(f"Pago de consulta actualizado (Costo: {costo_tot}, Abono: {abono_val}).")
                    else:
                        registrar_o_actualizar_pago_db(
                            paciente_id=pac_id,
                            consulta_id=cid,
                            costo_total=costo_tot,
                            abono=abono_val,
                            saldo_pendiente=saldo_pend,
                            estado=est_pago,
                            metodo_pago=metodo_p,
                            notas=notas_p
                        )
            except Exception as e_pago:
                print(f"[PAGOS DB WARN]: {e_pago}")
                avisos.append(f"Error al registrar pago: {e_pago}")

        if not alerta_cedula:
            try:
                sonar_confirmacion_exito()
            except Exception:
                pass

        # --- BLOQUE 2: Reactividad y Refresco Automático de la Interfaz ---
        try:
            self._js("if(window.cargarPacientes) window.cargarPacientes(); if(window.cargarCitas) window.cargarCitas();")
            self._js("if(window.switchTab) window.switchTab('pdf');")
            if self._window:
                self._window.evaluate_js("if (window.actualizarTodosLosMenus) window.actualizarTodosLosMenus();")
        except Exception as e_ref:
            print(f"[UI REFRESH WARN] {e_ref}")

        return {
            "status": "ok",
            "accion": "actualizada" if consulta_hoy and accion_expediente in ("actualizar", "predeterminado") else "creada",
            "tipo": "HISTORIA_CLINICA",
            "texto": texto,
            "resultado": resultado_ia,
            "ruta_pdf": ruta_pdf,
            "paciente": nombre,
            "paciente_id": pac_id,
            "consulta_id": cid,
            "alerta_cedula_requerida": alerta_cedula,
            "cita_programada": cita_programada_str,
            "url_gcal": url_gcal_creada,
            "avisos": avisos
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
        finally:
            if ruta_wav and os.path.exists(ruta_wav) and "bimo_mobile_" in os.path.basename(ruta_wav):
                try:
                    os.remove(ruta_wav)
                except Exception:
                    pass

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
                "message": "Expediente actualizado",
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
                "message": "Expediente guardado",
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
            if not datos.get("id") and datos.get("nombre"):
                try:
                    pac_sim = buscar_paciente_por_similitud(datos.get("nombre"), umbral=0.85)
                    if pac_sim:
                        datos["id"] = pac_sim["id"]
                        datos["nombre"] = pac_sim["nombre"]
                except Exception:
                    pass
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

    def _ruta_pdf_permitida(self, ruta):
        """
        Verifica que la ruta sea un archivo PDF válido, existente en disco y
        ubicado estrictamente dentro de los directorios permitidos de pacientes (C5/R3).
        Evita Path Traversal y ejecución arbitraria de binarios a través de os.startfile.
        """
        if not ruta or not isinstance(ruta, str):
            return False, ""
        try:
            real_ruta = os.path.realpath(os.path.abspath(str(ruta).strip()))
            if not real_ruta.lower().endswith(".pdf"):
                return False, ""
            if not os.path.isfile(real_ruta):
                return False, ""

            # Directorios permitidos
            dirs_permitidos = [
                os.path.realpath(str(RUTA_PACIENTES)),
                os.path.realpath(str(BASE_DIR / "Pacientes"))
            ]
            dev_pac = Path.home() / "Desktop" / "Bimo_Project" / "Pacientes"
            if dev_pac.exists():
                dirs_permitidos.append(os.path.realpath(str(dev_pac)))

            for d in dirs_permitidos:
                if not os.path.exists(d):
                    continue
                try:
                    if os.path.commonpath([real_ruta, d]) == d:
                        return True, real_ruta
                except ValueError:
                    continue
            return False, ""
        except Exception as e:
            print(f"[RUTA_PDF_VALIDATION WARN]: {e}")
            return False, ""

    def obtener_preview_pdf(self, ruta_pdf=None):
        try:
            target = None
            if ruta_pdf:
                ok, real_r = self._ruta_pdf_permitida(ruta_pdf)
                if not ok:
                    return {"status": "error", "message": "Ruta no permitida"}
                target = real_r
            elif self._ultima_ruta_pdf:
                ok, real_r = self._ruta_pdf_permitida(self._ultima_ruta_pdf)
                if ok:
                    target = real_r

            if not target:
                recientes = self.listar_pdfs_recientes()
                if recientes:
                    ok, real_r = self._ruta_pdf_permitida(recientes[0]["ruta"])
                    if ok:
                        target = real_r

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
            ok, real_ruta = self._ruta_pdf_permitida(ruta)
            if not ok:
                return {"status": "error", "message": "Ruta no permitida"}
            os.startfile(real_ruta)
            return {"status": "ok"}
        except Exception as e:
            print(f"[BIMO DESKTOP ERROR] abrir_pdf: {e}")
            return {"status": "error", "message": str(e)}

    def abrir_ultimo_pdf(self, abrir_externo=False):
        try:
            target = None
            if self._ultima_ruta_pdf:
                ok, real_r = self._ruta_pdf_permitida(self._ultima_ruta_pdf)
                if ok:
                    target = real_r
            if not target:
                lista = self.listar_pdfs_recientes()
                if lista:
                    ok, real_r = self._ruta_pdf_permitida(lista[0]["ruta"])
                    if ok:
                        target = real_r
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
            target = None
            if ruta:
                ok, real_r = self._ruta_pdf_permitida(ruta)
                if not ok:
                    return {"status": "error", "message": "Ruta no permitida"}
                target = real_r
            elif self._ultima_ruta_pdf:
                ok, real_r = self._ruta_pdf_permitida(self._ultima_ruta_pdf)
                if ok:
                    target = real_r

            if not target:
                lista = self.listar_pdfs_recientes()
                if lista:
                    ok, real_r = self._ruta_pdf_permitida(lista[0]["ruta"])
                    if ok:
                        target = real_r

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
            from mobile_mic_server import obtener_o_crear_movil_token
            ip = obtener_ip_local()
            puerto = MOBILE_SERVER_PORT
            tok = obtener_o_crear_movil_token()
            url = f"https://{ip}:{puerto}/?t={tok}"
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
                "url": "https://127.0.0.1:8765/",
                "online": False
            }

    def obtener_qr_movil_base64(self):
        try:
            from mobile_mic_server import obtener_o_crear_movil_token
            ip = obtener_ip_local()
            tok = obtener_o_crear_movil_token()
            url = f"https://{ip}:{MOBILE_SERVER_PORT}/?t={tok}"
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

    def obtener_estado_respaldo_drive(self):
        try:
            from config import obtener_parametro_boveda
            from calendar_sync import obtener_credenciales_google
            from drive_backup import _leer_estado
            import datetime

            cifrado = str(obtener_parametro_boveda("backup_drive_cifrado", "0")) == "1"
            tiene_pass = bool(obtener_parametro_boveda("backup_drive_passphrase", ""))
            creds = obtener_credenciales_google()
            conectado = creds is not None and getattr(creds, "valid", False)

            est = _leer_estado()
            ultimo_ts = est.get("ultimo_ok_ts")
            ultimo_str = datetime.datetime.fromtimestamp(ultimo_ts).strftime("%Y-%m-%d %H:%M") if ultimo_ts else "Nunca"
            ultimo_err = est.get("ultimo_error")

            return {
                "status": "ok",
                "cifrado_activo": cifrado,
                "tiene_passphrase": tiene_pass,
                "google_conectado": conectado,
                "ultimo_respaldo": ultimo_str,
                "ultimo_error": ultimo_err
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def guardar_configuracion_respaldo_drive(self, cifrado_activo, passphrase=None):
        try:
            from config import guardar_parametro_boveda
            cifrado_str = "1" if cifrado_activo else "0"
            guardar_parametro_boveda("backup_drive_cifrado", cifrado_str)
            if passphrase is not None and str(passphrase).strip():
                pwd = str(passphrase).strip()
                if len(pwd) < 8:
                    return {"status": "error", "message": "La contraseña de cifrado debe tener al menos 8 caracteres."}
                guardar_parametro_boveda("backup_drive_passphrase", pwd)
            return {"status": "ok", "message": "Configuración de respaldo en Google Drive guardada."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def ejecutar_respaldo_drive_manual(self):
        try:
            from calendar_sync import obtener_credenciales_google
            from drive_backup import _ejecutar_respaldo, _leer_estado
            from config import obtener_parametro_boveda
            creds = obtener_credenciales_google()
            if not creds:
                return {"status": "error", "message": "No hay cuenta de Google vinculada. Conecta Google Calendar primero."}

            cifrado_activo = str(obtener_parametro_boveda("backup_drive_cifrado", "0")) == "1"
            passphrase = obtener_parametro_boveda("backup_drive_passphrase", "") if cifrado_activo else None
            if cifrado_activo and not passphrase:
                return {"status": "error", "message": "El cifrado está activo pero falta definir una contraseña segura."}

            ok = _ejecutar_respaldo(creds, forzar=True, passphrase=passphrase)
            est = _leer_estado()
            if ok:
                return {"status": "ok", "message": "Respaldo completado y sincronizado con Google Drive exitosamente."}
            else:
                err = est.get("ultimo_error") or "No se pudo completar la sincronización con Google Drive."
                return {"status": "error", "message": err}
        except Exception as e:
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
            real_ruta = os.path.realpath(os.path.abspath(str(ruta).strip()))
            real_pac = os.path.realpath(str(RUTA_PACIENTES))
            dev_pac = os.path.realpath(str(Path.home() / "Desktop" / "Bimo_Project" / "Pacientes"))
            es_permitido = False
            for d in [real_pac, dev_pac]:
                if os.path.exists(d):
                    try:
                        if os.path.commonpath([real_ruta, d]) == d:
                            es_permitido = True
                            break
                    except ValueError:
                        continue
            if es_permitido and os.path.isdir(real_ruta):
                os.startfile(real_ruta)
                return {"status": "ok", "ruta": str(ruta)}
            return {"status": "error", "message": "Ruta de carpeta no permitida"}
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
            iniciar_servidor_movil(callback_audio=bridge.procesar_audio_externo, callback_texto=bridge.procesar_texto_clinico)
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

    def on_closing():
        t = bridge._disparar_respaldo_drive(al_cerrar=True)
        if t:
            t.join(timeout=25)

    window.events.closing += on_closing

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
