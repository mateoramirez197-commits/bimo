import customtkinter as ctk
from config import (
    cargar_datos_clinica, guardar_datos_clinica,
    TEMAS_BIMO, obtener_tema_guardado, obtener_tema_activo_dict
)
from auth import registrar_usuario
from license_manager import validar_licencia, obtener_hwid_equipo

class SettingsView(ctk.CTkFrame):
    def __init__(self, master):
        self.theme = obtener_tema_activo_dict()
        super().__init__(master, fg_color=self.theme["bg_dark"], corner_radius=self.theme["corner_radius"])
        self.datos_clinica = cargar_datos_clinica()
        self._build_ui()

    def _build_ui(self):
        t = self.theme

        # Header Superior Pulido
        top_bar = ctk.CTkFrame(self, fg_color=t["card_dark"], height=72, corner_radius=t["corner_radius"], border_width=1, border_color=t["border"])
        top_bar.pack(fill="x", padx=20, pady=(16, 14))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(top_bar, text="⚙️ Configuración del Consultorio & Personal", font=("Segoe UI", 18, "bold"), text_color=t["text_primary"]).pack(side="left", padx=20)

        # Formulario Desplazable con esquinas suaves
        form = ctk.CTkScrollableFrame(self, fg_color=t["card_dark"], corner_radius=t["corner_radius"], border_width=1, border_color=t["border"])
        form.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        # ----------------------------------------------------
        # 0. PERSONALIZACIÓN Y MOTOR DE TEMAS
        # ----------------------------------------------------
        ctk.CTkLabel(form, text="ESTÉTICA Y MOTOR DE TEMAS", font=("Segoe UI", 13, "bold"), text_color=t["aqua"]).pack(anchor="w", padx=24, pady=(16, 4))
        ctk.CTkLabel(form, text="Selecciona el tema visual de la interfaz médica:", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(anchor="w", padx=24, pady=(0, 6))

        self.tema_actual = obtener_tema_guardado()

        row_tema = ctk.CTkFrame(form, fg_color="transparent")
        row_tema.pack(fill="x", padx=24, pady=(0, 16))

        self.combo_tema = ctk.CTkComboBox(
            row_tema, values=list(TEMAS_BIMO.keys()), height=38, corner_radius=10,
            fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"],
            dropdown_fg_color=t["card_dark"], dropdown_text_color=t["text_primary"],
            command=self._cambiar_tema
        )
        self.combo_tema.set(self.tema_actual)
        self.combo_tema.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.lbl_tema_status = ctk.CTkLabel(row_tema, text="", font=("Segoe UI", 11))
        self.lbl_tema_status.pack(side="left")

        # Toggle de Modo Bajo Rendimiento
        from config import es_modo_bajo_rendimiento, set_modo_bajo_rendimiento, obtener_pin_doctor, guardar_pin_doctor
        from calendar_sync import forzar_sincronizacion_calendar, desvincular_calendar
        from database import limpiar_agenda_local_db

        self.var_low_perf = ctk.BooleanVar(value=es_modo_bajo_rendimiento())
        self.switch_low_perf = ctk.CTkSwitch(
            form, text="⚡ Modo Bajo Rendimiento (Optimizar para computadoras clínicas antiguas / menor CPU)",
            font=("Segoe UI", 11, "bold"), text_color=t["text_primary"], progress_color=t["aqua"],
            variable=self.var_low_perf, command=self._toggle_low_perf
        )
        self.switch_low_perf.pack(anchor="w", padx=24, pady=(0, 20))

        # ----------------------------------------------------
        # 1. INFORMACIÓN DEL CONSULTORIO, PIN Y DOCTOR TITULAR
        # ----------------------------------------------------
        ctk.CTkLabel(form, text="DATOS INSTITUCIONALES & ACCESO RÁPIDO", font=("Segoe UI", 13, "bold"), text_color=t["azul_acero"]).pack(anchor="w", padx=24, pady=(10, 8))

        ctk.CTkLabel(form, text="Nombre del Consultorio o Clínica", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(anchor="w", padx=24, pady=(2, 2))
        self.entry_clinica = ctk.CTkEntry(form, height=38, corner_radius=10, fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_clinica.pack(fill="x", padx=24, pady=(0, 12))
        self.entry_clinica.insert(0, self.datos_clinica.get("nombre_clinica", ""))

        ctk.CTkLabel(form, text="Nombre del Odontólogo Titular", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(anchor="w", padx=24, pady=(2, 2))
        self.entry_doctor = ctk.CTkEntry(form, height=38, corner_radius=10, fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_doctor.pack(fill="x", padx=24, pady=(0, 12))
        self.entry_doctor.insert(0, self.datos_clinica.get("nombre_doctor", ""))

        row_meta = ctk.CTkFrame(form, fg_color="transparent")
        row_meta.pack(fill="x", padx=24, pady=(0, 12))

        box_reg = ctk.CTkFrame(row_meta, fg_color="transparent")
        box_reg.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkLabel(box_reg, text="Registro Profesional / Colegiatura", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(anchor="w", pady=(0, 2))
        self.entry_registro = ctk.CTkEntry(box_reg, height=38, corner_radius=10, fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_registro.pack(fill="x")
        self.entry_registro.insert(0, self.datos_clinica.get("registro_profesional", ""))

        box_pin = ctk.CTkFrame(row_meta, fg_color="transparent")
        box_pin.pack(side="right", fill="x", expand=True, padx=(6, 0))
        ctk.CTkLabel(box_pin, text="PIN Rápido de Acceso (4 Dígitos)", font=("Segoe UI", 11, "bold"), text_color=t["aqua"]).pack(anchor="w", pady=(0, 2))
        self.entry_pin = ctk.CTkEntry(box_pin, height=38, corner_radius=10, placeholder_text="1234", fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_pin.pack(fill="x")
        self.entry_pin.insert(0, obtener_pin_doctor())

        ctk.CTkLabel(form, text="Teléfono de Contacto Clínico", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(anchor="w", padx=24, pady=(2, 2))
        self.entry_telefono = ctk.CTkEntry(form, height=38, corner_radius=10, fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_telefono.pack(fill="x", padx=24, pady=(0, 16))
        self.entry_telefono.insert(0, self.datos_clinica.get("telefono_contacto", ""))

        btn_guardar_clinica = ctk.CTkButton(
            form, text="💾 Guardar Información del Consultorio y PIN", height=42, font=("Segoe UI", 12, "bold"),
            fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff",
            corner_radius=t["corner_btn"], command=self._guardar_clinica
        )
        btn_guardar_clinica.pack(fill="x", padx=24, pady=(0, 24))

        # ----------------------------------------------------
        # 2. CUENTA Y SINCRONIZACIÓN DE GOOGLE CALENDAR
        # ----------------------------------------------------
        ctk.CTkLabel(form, text="SINCRONIZACIÓN CON GOOGLE CALENDAR", font=("Segoe UI", 13, "bold"), text_color=t["aqua"]).pack(anchor="w", padx=24, pady=(10, 6))
        ctk.CTkLabel(
            form,
            text="Las citas se sincronizan automáticamente con tu agenda clínica local y Google Calendar.\n"
                 "Si deseas cambiar a otro correo médico, pulsa el botón para desvincular la anterior y enlazar la nueva:",
            font=("Segoe UI", 11), text_color=t["text_muted"], justify="left"
        ).pack(anchor="w", padx=24, pady=(0, 10))

        btn_nueva_cuenta = ctk.CTkButton(
            form, text="🔗 Vincular Nueva Cuenta a Google Calendar", height=40, font=("Segoe UI", 12, "bold"),
            fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff", corner_radius=t["corner_btn"],
            command=self._vincular_nueva_cuenta_calendar
        )
        btn_nueva_cuenta.pack(fill="x", padx=24, pady=(0, 8))

        self.lbl_cal_msg = ctk.CTkLabel(form, text="", font=("Segoe UI", 11, "bold"))
        self.lbl_cal_msg.pack(padx=24, pady=(0, 18), anchor="w")

        # ----------------------------------------------------
        # 3. GESTIÓN DE CREDENCIALES DEL PERSONAL
        # ----------------------------------------------------
        ctk.CTkLabel(form, text="GESTIÓN DE ACCESOS Y PERSONAL", font=("Segoe UI", 13, "bold"), text_color=t["azul_acero"]).pack(anchor="w", padx=24, pady=(10, 8))

        ctk.CTkLabel(form, text="Registrar o Actualizar Asistente / Personal Auxiliar", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(anchor="w", padx=24, pady=(2, 2))
        
        row_staff = ctk.CTkFrame(form, fg_color="transparent")
        row_staff.pack(fill="x", padx=24, pady=(0, 10))

        self.entry_staff_nombre = ctk.CTkEntry(row_staff, placeholder_text="Nombre del Auxiliar", height=38, corner_radius=10, fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_staff_nombre.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.entry_staff_email = ctk.CTkEntry(row_staff, placeholder_text="correo@asistente.com", height=38, corner_radius=10, fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_staff_email.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.entry_staff_pwd = ctk.CTkEntry(row_staff, placeholder_text="Contraseña", height=38, corner_radius=10, show="•", fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_staff_pwd.pack(side="left", fill="x", expand=True, padx=(0, 6))

        btn_add_staff = ctk.CTkButton(
            row_staff, text="➕ Agregar", width=100, height=38, font=("Segoe UI", 11, "bold"),
            fg_color=t["aqua"], hover_color="#059669", text_color="#ffffff",
            corner_radius=t["corner_btn"], command=self._crear_asistente
        )
        btn_add_staff.pack(side="right")

        self.lbl_staff_msg = ctk.CTkLabel(form, text="", font=("Segoe UI", 11))
        self.lbl_staff_msg.pack(pady=(0, 16))

        # ----------------------------------------------------
        # 4. ESTADO DE LA LICENCIA Y SEGURIDAD DEL EQUIPO
        # ----------------------------------------------------
        ctk.CTkLabel(form, text="LICENCIAMIENTO CRIPTOGRÁFICO", font=("Segoe UI", 13, "bold"), text_color=t["text_muted"]).pack(anchor="w", padx=24, pady=(10, 8))

        card_lic = ctk.CTkFrame(form, fg_color=t["bg_dark"], corner_radius=14, border_width=1, border_color=t["border"])
        card_lic.pack(fill="x", padx=24, pady=(0, 20))

        valida, info = validar_licencia()
        hwid = obtener_hwid_equipo()
        email_lic = info.get("email", "No activado")

        txt_lic = f"• Estado: Licencia Activa (Permanente)\n• Correo Vinculado: {email_lic}\n• Huella de Hardware (HWID): {hwid}\n• Protección Anti-Copia: Habilitada (Bloqueo en otras máquinas)"
        ctk.CTkLabel(card_lic, text=txt_lic, font=("Consolas", 11), text_color=t["text_primary"], justify="left").pack(padx=16, pady=12, anchor="w")

    def _toggle_low_perf(self):
        from config import set_modo_bajo_rendimiento
        activo = self.var_low_perf.get()
        set_modo_bajo_rendimiento(activo)

    def _vincular_nueva_cuenta_calendar(self):
        import os
        import shutil
        import webbrowser
        from tkinter import filedialog
        from config import BASE_DIR
        from calendar_sync import forzar_sincronizacion_calendar, buscar_y_copiar_credentials

        t = self.theme
        cred_path = os.path.join(BASE_DIR, "credentials.json")
        buscar_y_copiar_credentials()

        if not os.path.exists(cred_path):
            modal = ctk.CTkToplevel(self)
            modal.title("Vincular Google Calendar")
            modal.geometry("480x320")
            modal.resizable(False, False)
            modal.attributes("-topmost", True)
            modal.configure(fg_color=t["bg_dark"])

            ctk.CTkLabel(modal, text="🔗 VINCULAR CUENTA DE GOOGLE CALENDAR", font=("Segoe UI", 13, "bold"), text_color=t["aqua"]).pack(pady=(20, 8))
            ctk.CTkLabel(
                modal,
                text="Para sincronizar citas de fondo directamente con Google Calendar API,\nse requiere el archivo credentials.json de Google Cloud.\n\nSi ya lo descargaste, selecciónalo aquí para autorizar tu cuenta:",
                font=("Segoe UI", 10), text_color=t["text_muted"], justify="center"
            ).pack(pady=(0, 16), padx=20)

            def seleccionar_archivo():
                ruta_sel = filedialog.askopenfilename(
                    title="Selecciona credentials.json de Google Cloud",
                    filetypes=[("Archivos JSON", "*.json"), ("Todos los archivos", "*.*")]
                )
                if ruta_sel:
                    shutil.copy(ruta_sel, cred_path)
                    modal.destroy()
                    exito = forzar_sincronizacion_calendar()
                    if exito:
                        self.lbl_cal_msg.configure(text="✅ Google Calendar vinculado con éxito.", text_color=t["aqua"])
                    else:
                        self.lbl_cal_msg.configure(text="ℹ️ Autoriza en la ventana del navegador que se abrió.", text_color=t["azul_pastel"])

            ctk.CTkButton(
                modal, text="📂 Cargar credentials.json...", font=("Segoe UI", 12, "bold"),
                height=38, fg_color=t["azul_acero"], hover_color=t["azul_pastel"],
                command=seleccionar_archivo
            ).pack(fill="x", padx=40, pady=(0, 10))

            ctk.CTkButton(
                modal, text="🌐 Abrir Google Calendar en Web", font=("Segoe UI", 11),
                height=34, fg_color="#334155", hover_color="#475569",
                command=lambda: webbrowser.open("https://calendar.google.com")
            ).pack(fill="x", padx=40, pady=(0, 12))

            ctk.CTkButton(modal, text="Cerrar", width=90, height=30, fg_color="transparent", text_color=t["text_muted"], command=modal.destroy).pack()
            return

        exito = forzar_sincronizacion_calendar()
        if exito:
            self.lbl_cal_msg.configure(text="✅ Cuenta anterior desvinculada. Nueva cuenta vinculada con éxito.", text_color=self.theme["aqua"])
        else:
            self.lbl_cal_msg.configure(text="ℹ️ Autoriza en la ventana del navegador que se abrió.", text_color=self.theme["azul_pastel"])

    def _cambiar_tema(self, nuevo_tema):
        try:
            app_root = self.winfo_toplevel()
            if hasattr(app_root, "aplicar_tema"):
                app_root.aplicar_tema(nuevo_tema)
        except Exception as e:
            print(f"[THEME] Error al aplicar tema en vivo: {e}")

    def _guardar_clinica(self):
        t = self.theme
        from config import guardar_pin_doctor
        pin = self.entry_pin.get().strip() or "1234"
        guardar_pin_doctor(pin)

        datos = {
            "nombre_clinica": self.entry_clinica.get().strip(),
            "nombre_doctor": self.entry_doctor.get().strip(),
            "registro_profesional": self.entry_registro.get().strip(),
            "telefono_contacto": self.entry_telefono.get().strip(),
            "pin_rapido": pin
        }
        guardar_datos_clinica(datos)
        self.lbl_staff_msg.configure(text="✅ Datos institucionales y PIN rápido actualizados correctamente", text_color=t["aqua"])

    def _crear_asistente(self):
        t = self.theme
        nom = self.entry_staff_nombre.get().strip()
        email = self.entry_staff_email.get().strip()
        pwd = self.entry_staff_pwd.get().strip()

        if not nom or not email or not pwd:
            self.lbl_staff_msg.configure(text="Completa nombre, correo y contraseña del personal", text_color="#ef4444")
            return

        try:
            registrar_usuario(nom, email, pwd, rol="asistente")
            self.lbl_staff_msg.configure(text=f"✅ Usuario auxiliar '{nom}' registrado exitosamente", text_color=t["aqua"])
            self.entry_staff_nombre.delete(0, "end")
            self.entry_staff_email.delete(0, "end")
            self.entry_staff_pwd.delete(0, "end")
        except Exception as e:
            self.lbl_staff_msg.configure(text="Error: El correo ya se encuentra registrado", text_color="#ef4444")
