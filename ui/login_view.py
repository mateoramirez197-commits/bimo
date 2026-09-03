import customtkinter as ctk
from auth import autenticar_usuario, registrar_usuario
from license_manager import validar_licencia, activar_licencia_equipo
from config import obtener_tema_activo_dict
from ui.logo_widget import BimoLogo

class LoginView(ctk.CTkFrame):
    def __init__(self, master, on_login_success):
        t = obtener_tema_activo_dict()
        super().__init__(master, fg_color=t["bg_dark"])
        self.on_login_success = on_login_success
        
        # Verificar estado de la licencia por hardware
        es_valida, self.licencia_info = validar_licencia()
        if es_valida:
            self._build_login_ui()
        else:
            self._build_activation_ui()

    def _build_activation_ui(self):
        t = obtener_tema_activo_dict()
        for w in self.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self, fg_color=t["card_dark"], corner_radius=t["corner_radius"], border_width=1, border_color=t["border"], width=460, height=520)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        # Logotipo
        logo_box = ctk.CTkFrame(card, fg_color="transparent")
        logo_box.pack(pady=(35, 4))
        BimoLogo(logo_box, font_size=38).pack()

        ctk.CTkLabel(card, text="ACTIVACIÓN INICIAL POR HARDWARE", font=("Segoe UI", 11, "bold"), text_color=t["aqua"]).pack(pady=(0, 16))
        
        info_txt = "Bienvenido a BIMO. Para habilitar tu licencia permanente y vincular tu agenda, por favor ingresa tu correo profesional. Esta instalación quedará firmada criptográficamente para esta PC."
        ctk.CTkLabel(card, text=info_txt, font=("Segoe UI", 11), text_color=t["text_muted"], wraplength=380, justify="center").pack(pady=(0, 24))

        # Campo para que el usuario coloque su correo real
        ctk.CTkLabel(card, text="Correo Electrónico del Doctor", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"], anchor="w").pack(fill="x", padx=40, pady=(0, 4))
        self.entry_activacion_email = ctk.CTkEntry(card, height=44, corner_radius=12, placeholder_text="ejemplo@doctor.com", font=("Segoe UI", 12), fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_activacion_email.pack(fill="x", padx=40, pady=(0, 10))

        # Contraseña maestra inicial
        ctk.CTkLabel(card, text="Crear Contraseña de Acceso", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"], anchor="w").pack(fill="x", padx=40, pady=(0, 4))
        self.entry_activacion_pwd = ctk.CTkEntry(card, height=44, corner_radius=12, placeholder_text="••••••••", show="•", font=("Segoe UI", 12), fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_activacion_pwd.pack(fill="x", padx=40, pady=(0, 16))

        self.lbl_act_msg = ctk.CTkLabel(card, text="", font=("Segoe UI", 11), text_color=t["fucsia"])
        self.lbl_act_msg.pack(pady=(0, 10))

        btn_activar = ctk.CTkButton(
            card, text="🔐 Activar Licencia y Vincular Equipo", height=46,
            font=("Segoe UI", 11, "bold"), fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff",
            corner_radius=t["corner_btn"], command=self._ejecutar_activacion
        )
        btn_activar.pack(fill="x", padx=40, pady=(0, 20))

    def _ejecutar_activacion(self):
        email = self.entry_activacion_email.get().strip()
        pwd = self.entry_activacion_pwd.get().strip()

        if not email or "@" not in email:
            self.lbl_act_msg.configure(text="Por favor ingresa un correo electrónico válido")
            return
        if not pwd or len(pwd) < 4:
            self.lbl_act_msg.configure(text="La contraseña debe tener al menos 4 caracteres")
            return

        ok = activar_licencia_equipo(email)
        if ok:
            try:
                registrar_usuario("Dr. Titular", email, pwd, "medico")
            except Exception:
                pass
            
            try:
                from calendar_sync import init_google_calendar
                init_google_calendar(email)
            except Exception:
                pass

            self.licencia_info = {"email": email}
            self._build_login_ui(email_sugerido=email)
        else:
            self.lbl_act_msg.configure(text="Error al generar la firma de hardware")

    def _build_login_ui(self, email_sugerido=""):
        t = obtener_tema_activo_dict()
        for w in self.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self, fg_color=t["card_dark"], corner_radius=t["corner_radius"], border_width=1, border_color=t["border"], width=440, height=490)
        card.place(relx=0.5, rely=0.5, anchor="center")
        card.pack_propagate(False)

        # Logotipo Vanguardista BIMO
        logo_box = ctk.CTkFrame(card, fg_color="transparent")
        logo_box.pack(pady=(35, 4))
        BimoLogo(logo_box, font_size=38).pack()

        ctk.CTkLabel(card, text="SaaS Clínico Odontológico", font=("Segoe UI", 12), text_color=t["text_muted"]).pack(pady=(0, 24))

        # Email
        ctk.CTkLabel(card, text="Correo Electrónico", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"], anchor="w").pack(fill="x", padx=40, pady=(0, 4))
        self.entry_email = ctk.CTkEntry(card, height=44, corner_radius=12, placeholder_text="correo@doctor.com", font=("Segoe UI", 12), fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_email.pack(fill="x", padx=40, pady=(0, 14))
        if email_sugerido:
            self.entry_email.insert(0, email_sugerido)

        # Password
        ctk.CTkLabel(card, text="Contraseña", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"], anchor="w").pack(fill="x", padx=40, pady=(0, 4))
        self.entry_pwd = ctk.CTkEntry(card, height=44, corner_radius=12, placeholder_text="••••••••", show="•", font=("Segoe UI", 12), fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_pwd.pack(fill="x", padx=40, pady=(0, 12))

        # Mensaje de error
        self.lbl_error = ctk.CTkLabel(card, text="", font=("Segoe UI", 11), text_color=t["fucsia"])
        self.lbl_error.pack(pady=(0, 10))

        # Botón Iniciar Sesión
        btn_login = ctk.CTkButton(
            card, text="Iniciar Sesión", height=46, corner_radius=t["corner_btn"],
            font=("Segoe UI", 11, "bold"), fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff",
            command=self._intentar_login
        )
        btn_login.pack(fill="x", padx=40, pady=(0, 20))

    def _intentar_login(self):
        email = self.entry_email.get().strip()
        pwd = self.entry_pwd.get().strip()
        usuario = autenticar_usuario(email, pwd)
        if usuario:
            self.lbl_error.configure(text="")
            self.on_login_success(usuario)
        else:
            self.lbl_error.configure(text="Credenciales incorrectas o usuario no registrado")
