import os
import customtkinter as ctk

from ui.login_view import LoginView
from ui.dictation_view import DictationView
from ui.patients_view import PatientsView
from ui.agenda_view import AgendaView
from ui.mobile_view import MobileView
from ui.settings_view import SettingsView
from ui.desktop_floating_widget import DesktopFloatingWidget
from ui.logo_widget import BimoLogo
from auth import set_sesion_activa, cerrar_sesion
from mobile_mic_server import iniciar_servidor_movil
from config import (
    COLOR_BG_DARK, COLOR_SIDEBAR, COLOR_AZUL_ACERO,
    COLOR_AZUL_PASTEL, COLOR_AQUA, COLOR_FUCSIA, COLOR_BORDER,
    aplicar_tema_config, obtener_tema_guardado, obtener_tema_activo_dict, TEMAS_BIMO,
    cargar_datos_clinica, es_onboarding_completado, set_onboarding_completado,
    es_modo_bajo_rendimiento, obtener_pin_doctor,
    obtener_ultimo_usuario_recordado, guardar_ultimo_usuario_recordado
)
from audio_feedback import sonar_confirmacion_exito
from ui.animations import bind_hover_microscale

def ease_out_cubic(t: float) -> float:
    """Función de aceleración/desaceleración suave (Cubic Easing Out)."""
    return 1.0 - pow(1.0 - t, 3)

def animar_propiedad(widget, update_fn, start_val, end_val, duration_ms=220, on_complete=None):
    """Ejecuta una animación fluida a ~60 FPS (16ms por tick) con Easing Out."""
    total_ticks = max(1, int(duration_ms / 16))
    tick_actual = 0

    def _frame():
        nonlocal tick_actual
        tick_actual += 1
        t_val = tick_actual / total_ticks
        factor = ease_out_cubic(t_val)
        valor_actual = start_val + (end_val - start_val) * factor
        try:
            update_fn(valor_actual)
        except Exception:
            return

        if tick_actual < total_ticks:
            widget.after(16, _frame)
        else:
            try:
                update_fn(end_val)
            except Exception:
                pass
            if on_complete:
                on_complete()

    _frame()

class BimoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("BIMO - Asistente Clínico Inteligente (SaaS Odontológico)")
        self.geometry("1220x800")
        self.minsize(1040, 720)

        # Aplicar el tema guardado al arrancar
        tema_ini = obtener_tema_guardado()
        t_ini = aplicar_tema_config(tema_ini)

        ctk.set_appearance_mode(t_ini.get("mode", "light"))
        ctk.set_default_color_theme("blue")

        self.usuario_actual = None
        self.floating_widget = None
        self.vista_actual = "dictation"
        self.configure(fg_color=t_ini.get("bg_dark", "#EEF2F6"))
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)

        # Iniciar con el Splash Screen de bienvenida animado
        self._mostrar_splash_screen()

    def _mostrar_splash_screen(self):
        t = obtener_tema_activo_dict()
        for w in self.container.winfo_children():
            w.destroy()

        datos_c = cargar_datos_clinica()
        nom_clinica = datos_c.get("nombre_clinica", "BIMO Dental Clinic")

        splash = ctk.CTkFrame(self.container, fg_color="transparent")
        splash.place(relx=0.5, rely=0.48, anchor="center")

        BimoLogo(splash, font_size=56).pack(pady=(0, 6))
        ctk.CTkLabel(splash, text="B  I  M  O    P  R  O", font=("Segoe UI", 16, "bold"), text_color=t["aqua"]).pack(pady=(0, 6))
        ctk.CTkLabel(splash, text=f"🏥 {nom_clinica}", font=("Segoe UI", 13), text_color=t["text_muted"]).pack(pady=(0, 24))

        pbar = ctk.CTkProgressBar(splash, mode="indeterminate", width=300, height=6, fg_color=t["card_dark"], progress_color=t["aqua"])
        pbar.pack(pady=(0, 14))
        pbar.start()

        lbl_status = ctk.CTkLabel(splash, text="Iniciando plataforma clínica...", font=("Segoe UI", 11), text_color=t["text_muted"])
        lbl_status.pack()

        delay = 400 if es_modo_bajo_rendimiento() else 1400
        self._splash_timer = self.after(delay, self._transicion_desde_splash)

    def _transicion_desde_splash(self):
        self._splash_timer = None
        if not es_onboarding_completado():
            self._mostrar_onboarding_carousel()
        else:
            self._iniciar_flujo_autenticacion()

    def _mostrar_onboarding_carousel(self):
        t = obtener_tema_activo_dict()
        for w in self.container.winfo_children():
            w.destroy()

        pasos = [
            {
                "icono": "🎙️",
                "titulo": "Dictado Clínico Inteligente Manos Libres",
                "desc": "BIMO escucha tu voz con IA neuronal Whisper. Di 'Bimo' para programar citas o dictar la historia clínica completa de tus pacientes mientras atiendes, sin tocar el teclado ni el ratón."
            },
            {
                "icono": "📱",
                "titulo": "Software en tu Smartphone (PWA)",
                "desc": "Escanea el código QR con tu teléfono para abrir Bimo Clinic desde tu celular y acceder a los expedientes en PDF y dictado remoto en tiempo real."
            },
            {
                "icono": "🦷",
                "titulo": "Odontograma y Evaluación Oclusal",
                "desc": "Mapeo anatómico de las 32 piezas dentales en alta fidelidad y evaluación oclusal/ortodóncica oficial integrada directamente en el informe médico."
            }
        ]

        self._onboarding_idx = 0

        box = ctk.CTkFrame(self.container, fg_color=t["card_dark"], corner_radius=20, border_width=1, border_color=t["border"], width=620, height=490)
        box.place(relx=0.5, rely=0.48, anchor="center")
        box.pack_propagate(False)

        lbl_icon = ctk.CTkLabel(box, text=pasos[0]["icono"], font=("Segoe UI", 52))
        lbl_icon.pack(pady=(32, 10))

        lbl_title = ctk.CTkLabel(box, text=pasos[0]["titulo"], font=("Segoe UI", 16, "bold"), text_color=t["aqua"], justify="center")
        lbl_title.pack(padx=24, pady=(0, 10))

        lbl_desc = ctk.CTkLabel(box, text=pasos[0]["desc"], font=("Segoe UI", 12), text_color=t["text_muted"], justify="center", wraplength=520)
        lbl_desc.pack(padx=30, pady=(0, 16))

        # Indicador de puntos (dots)
        lbl_dots = ctk.CTkLabel(box, text="●  ○  ○", font=("Segoe UI", 14), text_color=t["aqua"])
        lbl_dots.pack(pady=(0, 14))

        # Checkbox "No volver a mostrar"
        self.chk_no_volver = ctk.CTkCheckBox(
            box, text="No volver a mostrar este tutorial al iniciar", font=("Segoe UI", 11),
            fg_color=t["aqua"], text_color=t["text_primary"], border_color=t["border"]
        )
        self.chk_no_volver.pack(pady=(0, 16))
        self.chk_no_volver.select()

        btn_row = ctk.CTkFrame(box, fg_color="transparent")
        btn_row.pack(fill="x", padx=30, pady=(0, 20))

        def actualizar_slide():
            p = pasos[self._onboarding_idx]
            lbl_icon.configure(text=p["icono"])
            lbl_title.configure(text=p["titulo"])
            lbl_desc.configure(text=p["desc"])
            dots = ["○", "○", "○"]
            dots[self._onboarding_idx] = "●"
            lbl_dots.configure(text="  ".join(dots))
            if self._onboarding_idx == len(pasos) - 1:
                btn_next.configure(text="🚀 Comenzar a usar BIMO", fg_color=t["aqua"])
            else:
                btn_next.configure(text="Siguiente ➔", fg_color=t["azul_acero"])

        def finalizar_onboarding():
            if self.chk_no_volver.get():
                set_onboarding_completado(True)
            self._iniciar_flujo_autenticacion()

        def siguiente():
            if self._onboarding_idx < len(pasos) - 1:
                self._onboarding_idx += 1
                actualizar_slide()
            else:
                finalizar_onboarding()

        btn_skip = ctk.CTkButton(
            btn_row, text="Omitir", width=110, height=40, font=("Segoe UI", 11),
            fg_color="transparent", hover_color=t["card_hover"], text_color=t["text_muted"],
            command=finalizar_onboarding
        )
        btn_skip.pack(side="left")

        btn_next = ctk.CTkButton(
            btn_row, text="Siguiente ➔", width=200, height=40, font=("Segoe UI", 12, "bold"),
            fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff",
            corner_radius=12, command=siguiente
        )
        btn_next.pack(side="right")

    def _iniciar_flujo_autenticacion(self):
        # El PIN maestro es el guardián de acceso directo y seguro
        usuario_prev = obtener_ultimo_usuario_recordado()
        if not usuario_prev or not isinstance(usuario_prev, dict) or not usuario_prev.get("nombre"):
            datos_c = cargar_datos_clinica()
            usuario_prev = {
                "id": 1,
                "nombre": datos_c.get("nombre_doctor", "Mateo Ramírez"),
                "email": "doctor@bimo.local",
                "rol": "medico"
            }
        self._mostrar_pin_login(usuario_prev)

    def _mostrar_pin_login(self, usuario):
        t = obtener_tema_activo_dict()
        for w in self.container.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self.container, fg_color=t["card_dark"], corner_radius=20, border_width=1, border_color=t["border"], width=460, height=620)
        card.place(relx=0.5, rely=0.48, anchor="center")
        card.pack_propagate(False)

        self._usuario_en_login = usuario
        nom = self._usuario_en_login.get("nombre", "Dr. Titular")
        email = self._usuario_en_login.get("email", "")

        BimoLogo(card, font_size=28).pack(pady=(22, 6))
        self.lbl_usuario_titular = ctk.CTkLabel(card, text=f"👨‍⚕️ {nom}", font=("Segoe UI", 16, "bold"), text_color=t["text_primary"])
        self.lbl_usuario_titular.pack()
        self.lbl_sub_auth = ctk.CTkLabel(card, text=f"{email}  •  Acceso por PIN Maestro", font=("Segoe UI", 10, "bold"), text_color=t["text_muted"])
        self.lbl_sub_auth.pack(pady=(2, 12))

        # Indicador de 4 dígitos PIN
        self._pin_digits = []
        dots_row = ctk.CTkFrame(card, fg_color="transparent")
        dots_row.pack(pady=(0, 14))

        self._pin_dots_labels = []
        for _ in range(4):
            lbl_d = ctk.CTkLabel(
                dots_row, text="○", font=("Segoe UI", 24, "bold"),
                text_color=t["text_muted"], width=38, height=38, fg_color=t["bg_dark"], corner_radius=10
            )
            lbl_d.pack(side="left", padx=6)
            self._pin_dots_labels.append(lbl_d)

        lbl_msg = ctk.CTkLabel(card, text="Ingrese su PIN de 4 dígitos", font=("Segoe UI", 11), text_color=t["text_muted"])
        lbl_msg.pack(pady=(0, 8))

        # Teclado numérico en pantalla (Keypad)
        pad = ctk.CTkFrame(card, fg_color="transparent")
        pad.pack()

        def actualizar_pin_dots():
            for i in range(4):
                if i < len(self._pin_digits):
                    self._pin_dots_labels[i].configure(text="●", text_color=t["aqua"])
                else:
                    self._pin_dots_labels[i].configure(text="○", text_color=t["text_muted"])

        def verificar_pin():
            pin_ingresado = "".join(self._pin_digits)
            pin_esperado = obtener_pin_doctor()
            if pin_ingresado == pin_esperado:
                lbl_msg.configure(text="✅ PIN Correcto. Ingresando...", text_color=t["aqua"])
                sonar_confirmacion_exito()
                self.unbind("<Key>")
                self.after(300, lambda: self._on_login_success(self._usuario_en_login))
            else:
                lbl_msg.configure(text="⚠️ PIN Incorrecto. Intente de nuevo.", text_color=t.get("fucsia", "#ef4444"))
                self._pin_digits.clear()
                actualizar_pin_dots()

        def press_num(n):
            if len(self._pin_digits) < 4:
                self._pin_digits.append(str(n))
                actualizar_pin_dots()
                if len(self._pin_digits) == 4:
                    self.after(100, verificar_pin)

        def press_back():
            if self._pin_digits:
                self._pin_digits.pop()
                actualizar_pin_dots()
                lbl_msg.configure(text="Ingrese su PIN de 4 dígitos", text_color=t["text_muted"])

        teclas = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["⌫", "0", "✓"]
        ]

        for r in teclas:
            row_f = ctk.CTkFrame(pad, fg_color="transparent")
            row_f.pack(pady=3)
            for c in r:
                if c == "⌫":
                    b = ctk.CTkButton(
                        row_f, text=c, width=70, height=42, font=("Segoe UI", 16, "bold"),
                        fg_color=t["bg_dark"], hover_color=t["card_hover"], text_color=t["text_muted"],
                        corner_radius=10, command=press_back
                    )
                elif c == "✓":
                    b = ctk.CTkButton(
                        row_f, text=c, width=70, height=42, font=("Segoe UI", 16, "bold"),
                        fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff",
                        corner_radius=10, command=verificar_pin
                    )
                else:
                    b = ctk.CTkButton(
                        row_f, text=c, width=70, height=42, font=("Segoe UI", 16, "bold"),
                        fg_color=t["bg_dark"], hover_color=t["card_hover"], text_color=t["text_primary"],
                        corner_radius=10, command=lambda val=c: press_num(val)
                    )
                b.pack(side="left", padx=5)

        def on_key(event):
            if event.char and event.char.isdigit():
                press_num(event.char)
            elif event.keysym == "BackSpace":
                press_back()
            elif event.keysym in ("Return", "KP_Enter"):
                if len(self._pin_digits) == 4:
                    verificar_pin()

        self.bind("<Key>", on_key)

        # Botón para Ingresar como Invitado con validación de PIN Maestro
        def prompt_ingresar_invitado():
            modal_inv = ctk.CTkToplevel(self)
            modal_inv.title("Ingreso de Invitado")
            modal_inv.geometry("380x200")
            modal_inv.resizable(False, False)
            modal_inv.attributes("-topmost", True)
            modal_inv.configure(fg_color=t["bg_dark"])

            ctk.CTkLabel(modal_inv, text="👤 INGRESO DE INVITADO", font=("Segoe UI", 13, "bold"), text_color=t["aqua"]).pack(pady=(16, 6))
            ctk.CTkLabel(modal_inv, text="Ingresa tu nombre para registrar la sesión clínica:", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(pady=(0, 10))

            ent_inv = ctk.CTkEntry(modal_inv, width=280, height=36, corner_radius=10, placeholder_text="Nombre de invitado / asistente...", fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
            ent_inv.pack(pady=(0, 16))
            ent_inv.focus()

            def confirmar_invitado():
                nom_inv = ent_inv.get().strip() or "Invitado"
                modal_inv.destroy()
                self._usuario_en_login = {
                    "id": 99,
                    "nombre": f"Invitado: {nom_inv}",
                    "email": "invitado@bimo.local",
                    "rol": "invitado"
                }
                self.lbl_usuario_titular.configure(text=f"👤 {self._usuario_en_login['nombre']}")
                self.lbl_sub_auth.configure(text="Modo Invitado  •  Autorizado por PIN Maestro")
                lbl_msg.configure(text="Ingrese el PIN Maestro para autorizar:", text_color=t["aqua"])
                self._pin_digits.clear()
                actualizar_pin_dots()

            ctk.CTkButton(modal_inv, text="Continuar", width=140, height=34, font=("Segoe UI", 11, "bold"), fg_color=t["azul_acero"], hover_color=t["azul_pastel"], command=confirmar_invitado).pack()

        btn_guest = ctk.CTkButton(
            card, text="👤 Ingresar como Invitado / Asistente", font=("Segoe UI", 11, "bold"),
            fg_color="transparent", hover_color=t["card_hover"], text_color=t["aqua"],
            command=prompt_ingresar_invitado
        )
        btn_guest.pack(pady=(14, 0))

        # Watermark
        color_wm = "#cbd5e1" if t["mode"] == "light" else "#151d2f"
        lbl_watermark = ctk.CTkLabel(
            self.container, text="Software by Masword",
            font=("Segoe UI", 9), text_color=color_wm
        )
        lbl_watermark.place(relx=0.985, rely=0.988, anchor="se")

    def _mostrar_login(self):
        for w in self.container.winfo_children():
            w.destroy()

        from config import obtener_tema_activo_dict
        t = obtener_tema_activo_dict()
        self.container.configure(fg_color=t["bg_dark"])
        self.login_view = LoginView(self.container, on_login_success=self._on_login_success)
        self.login_view.pack(fill="both", expand=True)

        color_wm = "#cbd5e1" if t["mode"] == "light" else "#151d2f"
        lbl_watermark = ctk.CTkLabel(
            self.container, text="Software by Masword",
            font=("Segoe UI", 9), text_color=color_wm
        )
        lbl_watermark.place(relx=0.985, rely=0.988, anchor="se")

    def _on_login_success(self, usuario):
        if hasattr(self, "_splash_timer") and self._splash_timer:
            try:
                self.after_cancel(self._splash_timer)
            except Exception:
                pass
            self._splash_timer = None

        self.usuario_actual = usuario
        set_sesion_activa(usuario)
        guardar_ultimo_usuario_recordado(usuario)
        self._construir_dashboard()
        # Generar automáticamente el widget en el escritorio al iniciar
        self.after(500, self._toggle_floating_widget)

    def _construir_dashboard(self):
        # Detener listeners previos si existen antes de reconstruir
        if hasattr(self, "views") and "dictation" in self.views:
            try:
                if hasattr(self.views["dictation"], "wake_listener"):
                    self.views["dictation"].wake_listener.detener()
            except Exception:
                pass

        for w in self.container.winfo_children():
            w.destroy()

        from config import obtener_tema_activo_dict
        t = obtener_tema_activo_dict()

        # ---------------------------------------------------------------------
        # REGLA 1: ARQUITECTURA DE LIENZO FLOTANTE (CANVAS SOBRE CANVAS)
        # Fondo pastel en ventana raíz + Marco blanco puro (#FFFFFF) masivo con corner_radius=30
        # ---------------------------------------------------------------------
        self.configure(fg_color=t["bg_dark"])
        self.container.configure(fg_color="transparent")

        # Capa Sombra Suave Neumórfica (desplazada 2px hacia abajo y a la derecha)
        self.canvas_shadow = ctk.CTkFrame(
            self.container, fg_color=t.get("shadow", "#CBD5E1"), corner_radius=30, border_width=0
        )
        self.canvas_shadow.place(relx=0.016, rely=0.018, relwidth=0.968, relheight=0.964)

        # Lienzo Principal Blanco Puro (#FFFFFF) Masivo Flotante
        self.main_app_card = ctk.CTkFrame(
            self.container, fg_color=t["card_dark"], corner_radius=30, border_width=1, border_color=t["border"]
        )
        self.main_app_card.place(relx=0.014, rely=0.015, relwidth=0.968, relheight=0.964)

        # ---------------------------------------------------------------------
        # REGLA 2: MENÚ LATERAL MINIMALISTA (SLIM SIDEBAR)
        # Muy estrecho (width=74), esquinas redondeadas (corner_radius=22),
        # fondo acento violeta (#7C3AED), solo iconos blancos sin texto.
        # ---------------------------------------------------------------------
        self.slim_sidebar = ctk.CTkFrame(
            self.main_app_card, fg_color=t["sidebar"], width=74, corner_radius=22, border_width=0
        )
        self.slim_sidebar.place(relx=0.012, rely=0.016, relheight=0.968)

        # Emblema Superior Minimalista
        lbl_logo = ctk.CTkLabel(
            self.slim_sidebar, text="⚡", font=("Segoe UI", 26, "bold"), text_color="#FFFFFF"
        )
        lbl_logo.pack(pady=(20, 16))

        # Botones de Navegación (Solo íconos blancos, tipo píldora corner_radius=25)
        self.nav_buttons = {}
        items_menu = [
            ("dictation", "🎙️", "Dictado Clínico"),
            ("patients", "👥", "Pacientes & Archivo"),
            ("agenda", "📅", "Agenda de Citas"),
            ("mobile", "📱", "App Smartphone"),
            ("settings", "⚙️", "Configuración"),
        ]

        nav_box = ctk.CTkFrame(self.slim_sidebar, fg_color="transparent")
        nav_box.pack(fill="x", expand=True, pady=10)

        for key, icon, tooltip in items_menu:
            btn = ctk.CTkButton(
                nav_box, text=icon, width=48, height=48, font=("Segoe UI", 20),
                fg_color="transparent", text_color="#FFFFFF",
                hover_color=t.get("azul_pastel", "#8B5CF6"), corner_radius=24,
                border_width=0, command=lambda k=key: self._cambiar_vista(k)
            )
            btn.pack(pady=6)
            bind_hover_microscale(btn, normal_h=48, hover_h=54)
            self.nav_buttons[key] = btn

        # Separador sutil
        sep = ctk.CTkFrame(self.slim_sidebar, width=36, height=2, fg_color=t.get("azul_pastel", "#8B5CF6"))
        sep.pack(pady=12)

        # Botón Widget Flotante Escritorio
        btn_floating = ctk.CTkButton(
            self.slim_sidebar, text="📌", width=48, height=48, font=("Segoe UI", 18),
            fg_color="transparent", text_color="#FFFFFF",
            hover_color=t.get("azul_pastel", "#8B5CF6"), corner_radius=24,
            command=self._toggle_floating_widget
        )
        btn_floating.pack(pady=4)
        bind_hover_microscale(btn_floating, normal_h=48, hover_h=54)

        # Botón Logout
        btn_logout = ctk.CTkButton(
            self.slim_sidebar, text="🚪", width=48, height=48, font=("Segoe UI", 18),
            fg_color="transparent", text_color="#FCA5A5",
            hover_color="#DC2626", corner_radius=24,
            command=self._logout
        )
        btn_logout.pack(side="bottom", pady=20)
        bind_hover_microscale(btn_logout, normal_h=48, hover_h=54)

        # ---------------------------------------------------------------------
        # REGLA 3: TARJETAS FLOTANTES CON SOMBRAS SIMULADAS (SOFT 3D)
        # Frame trasero gris muy claro (#E2E8F0) desplazado 2px (.place())
        # Frame de contenido principal (#F8FAFC) con corner_radius=25 y márgenes amplios (padx=20, pady=20)
        # ---------------------------------------------------------------------
        self.content_shadow = ctk.CTkFrame(
            self.main_app_card, fg_color=t.get("border", "#E2E8F0"), corner_radius=25, border_width=0
        )
        self.content_shadow.place(relx=0.086, rely=0.019, relwidth=0.902, relheight=0.962)

        self.main_content = ctk.CTkFrame(
            self.main_app_card, fg_color=t.get("card_inner", "#F8FAFC"),
            corner_radius=25, border_width=1, border_color=t["border"]
        )
        self.main_content.place(relx=0.084, rely=0.016, relwidth=0.902, relheight=0.962)

        # Instanciar vistas clínicas dentro del lienzo
        self.views = {
            "dictation": DictationView(self.main_content),
            "patients": PatientsView(self.main_content),
            "agenda": AgendaView(self.main_content),
            "mobile": MobileView(self.main_content),
            "settings": SettingsView(self.main_content),
        }

        # Watermark sutil de autoría
        color_wm = "#94A3B8" if t["mode"] == "light" else "#151D2F"
        self.lbl_watermark = ctk.CTkLabel(
            self.main_app_card, text="Software by Masword",
            font=("Segoe UI", 9), text_color=color_wm
        )
        self.lbl_watermark.place(relx=0.985, rely=0.988, anchor="se")

        # Conectar servidor móvil en segundo plano al callback de DictationView
        iniciar_servidor_movil(callback_audio=self.views["dictation"].procesar_audio_externo)

        # Iniciar en vista de dictado
        self._cambiar_vista(getattr(self, "vista_actual", "dictation"))

    # -------------------------------------------------------------------------
    # REGLA 4: BOTONES TIPO PÍLDORA (PILL-SHAPED) Y ACENTOS VIBRANTES
    # -------------------------------------------------------------------------
    def _cambiar_vista(self, key_vista):
        self.vista_actual = key_vista
        for v in self.views.values():
            v.pack_forget()

        from config import obtener_tema_activo_dict
        t = obtener_tema_activo_dict()
        for k, btn in self.nav_buttons.items():
            if k == key_vista:
                btn.configure(
                    fg_color="#FFFFFF", text_color=t["sidebar"],
                    border_width=0, corner_radius=24
                )
            else:
                btn.configure(
                    fg_color="transparent", text_color="#FFFFFF",
                    border_width=0, corner_radius=24
                )

        target_view = self.views[key_vista]
        # Márgenes amplios (padx=20, pady=20) para que la interfaz respire
        target_view.pack(fill="both", expand=True, padx=20, pady=20)

        # Sincronización en caliente
        if key_vista == "patients" and hasattr(self.views["patients"], "_cargar_pacientes"):
            try:
                self.views["patients"]._cargar_pacientes()
            except Exception as e_rf:
                print(f"[APP SYNC] Error refrescando pacientes: {e_rf}")
        elif key_vista == "agenda" and hasattr(self.views["agenda"], "actualizar_citas"):
            try:
                self.views["agenda"].actualizar_citas()
            except Exception as e_ra:
                print(f"[APP SYNC] Error refrescando agenda: {e_ra}")

    def _toggle_floating_widget(self):
        if self.floating_widget is None or not self.floating_widget.winfo_exists():
            self.floating_widget = DesktopFloatingWidget(master_app=self)
        else:
            self.floating_widget.lift()
            self.floating_widget.actualizar_agenda()

    def _logout(self):
        if self.floating_widget and self.floating_widget.winfo_exists():
            self.floating_widget.destroy()
            self.floating_widget = None
        cerrar_sesion()
        self._mostrar_login()

    def aplicar_tema(self, nuevo_tema):
        from config import guardar_tema_visual, aplicar_tema_config, obtener_tema_activo_dict
        guardar_tema_visual(nuevo_tema)
        aplicar_tema_config(nuevo_tema)
        t = obtener_tema_activo_dict()
        ctk.set_appearance_mode(t.get("mode", "light"))
        self.configure(fg_color=t["bg_dark"])
        self.container.configure(fg_color="transparent")
        
        vista_previa = getattr(self, "vista_actual", "settings")
        self._construir_dashboard()
        self._cambiar_vista(vista_previa)
        
        if self.floating_widget and self.floating_widget.winfo_exists():
            self.floating_widget.aplicar_tema(nuevo_tema)
