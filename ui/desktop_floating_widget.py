import datetime
import webbrowser
import customtkinter as ctk
from database import listar_citas_db
from config import obtener_tema_activo_dict, TEMAS_BIMO

class DesktopFloatingWidget(ctk.CTkToplevel):
    """
    Widget de escritorio flotante auténtico BIMO HUD (Always-on-Top, arrastrable, sin bordes toscos de Windows).
    Estilo Obsidian Violet Glassmorphic con reloj digital neón, acceso rápido a dictado y agenda viva.
    """
    def __init__(self, master_app=None):
        super().__init__()
        self.master_app = master_app
        t = obtener_tema_activo_dict()

        # 1. Eliminar bordes y barra de título de Windows para ser un Widget real de escritorio
        # 1. Eliminar bordes y barra de título de Windows para ser un Widget real de escritorio
        from config import es_modo_bajo_rendimiento, cargar_datos_clinica
        conf = cargar_datos_clinica()
        self.overrideredirect(True)
        self._is_topmost = False
        self.attributes("-topmost", False)
        
        alpha_val = float(conf.get("opacidad_widget", 0.94))
        if not es_modo_bajo_rendimiento():
            self.attributes("-alpha", alpha_val)
        self.configure(fg_color=t["bg_dark"])
        self.resizable(False, False)

        # 2. Posicionar según preferencia guardada (480x230px)
        pos_pref = conf.get("posicion_widget", "superior_derecha")
        self.reposition(pos_pref)

        # Variables para arrastrar y modo dock pill
        self._offset_x = 0
        self._offset_y = 0
        self._colapsado = False

    def reposition(self, pos_pref):
        ancho_pantalla = self.winfo_screenwidth()
        alto_pantalla = self.winfo_screenheight()
        pos_pref = str(pos_pref).lower().strip()
        if pos_pref == "inferior_derecha":
            pos_x = max(10, ancho_pantalla - 505)
            pos_y = max(10, alto_pantalla - 280)
        elif pos_pref == "superior_izquierda":
            pos_x = 25
            pos_y = 45
        elif pos_pref == "inferior_izquierda":
            pos_x = 25
            pos_y = max(10, alto_pantalla - 280)
        else:  # superior_derecha
            pos_x = max(10, ancho_pantalla - 505)
            pos_y = 45
        self.geometry(f"480x230+{pos_x}+{pos_y}")

        self._build_ui()
        self._actualizar_reloj()
        self.actualizar_agenda()
        self._iniciar_auto_refresh()

    def aplicar_tema(self, nombre_tema=None):
        if hasattr(self, "main_frame") and self.main_frame.winfo_exists():
            self.main_frame.destroy()

        t = obtener_tema_activo_dict()
        self.configure(fg_color=t["bg_dark"])
        self._build_ui()
        self._actualizar_reloj()
        self.actualizar_agenda()

    def _build_ui(self):
        t = obtener_tema_activo_dict()
        bg_card = t.get("card_dark", "#0E1224")
        border_col = t.get("border", "#1E2545")
        aqua_col = t.get("aqua", "#38BDF8")
        azul_acero = t.get("azul_acero", "#6366F1")
        azul_pastel = t.get("azul_pastel", "#818CF8")

        self.main_frame = ctk.CTkFrame(
            self, fg_color=t["bg_dark"], corner_radius=18,
            border_width=1.5, border_color=border_col
        )
        self.main_frame.pack(fill="both", expand=True)

        # Barra superior arrastrable (Header HUD)
        self.header = ctk.CTkFrame(self.main_frame, fg_color=bg_card, height=40, corner_radius=14)
        self.header.pack(fill="x", padx=6, pady=(6, 4))
        self.header.pack_propagate(False)

        self.header.bind("<ButtonPress-1>", self._iniciar_arrastre)
        self.header.bind("<B1-Motion>", self._mover_widget)

        left_h = ctk.CTkFrame(self.header, fg_color="transparent")
        left_h.pack(side="left", padx=8)
        left_h.bind("<ButtonPress-1>", self._iniciar_arrastre)
        left_h.bind("<B1-Motion>", self._mover_widget)

        # Brand pill badge
        pill_brand = ctk.CTkFrame(left_h, fg_color="#1E1B4B", corner_radius=8)
        pill_brand.pack(side="left", padx=(0, 6), pady=6)
        pill_brand.bind("<ButtonPress-1>", self._iniciar_arrastre)
        pill_brand.bind("<B1-Motion>", self._mover_widget)

        lbl_tit = ctk.CTkLabel(
            pill_brand, text="● BIMO HUD", font=("Segoe UI", 9, "bold"),
            text_color=azul_pastel
        )
        lbl_tit.pack(padx=8, pady=2)
        lbl_tit.bind("<ButtonPress-1>", self._iniciar_arrastre)
        lbl_tit.bind("<B1-Motion>", self._mover_widget)

        self.lbl_status_dot = ctk.CTkLabel(
            left_h, text="● En Línea", font=("Segoe UI", 9, "bold"),
            text_color="#10B981"
        )
        self.lbl_status_dot.pack(side="left")
        self.lbl_status_dot.bind("<ButtonPress-1>", self._iniciar_arrastre)
        self.lbl_status_dot.bind("<B1-Motion>", self._mover_widget)

        # Botón de colapsar / expandir a la derecha
        self.btn_collapse = ctk.CTkButton(
            self.header, text="─", width=26, height=26, font=("Segoe UI", 11, "bold"),
            fg_color="transparent", text_color=t.get("text_muted", "#94A3B8"),
            hover_color="#1E2545", corner_radius=8, command=self._toggle_collapse
        )
        self.btn_collapse.pack(side="right", padx=(2, 6))

        # Botón toggle Anclado / Flotante normal
        self.btn_pin = ctk.CTkButton(
            self.header, text="📌 Normal", width=70, height=24, font=("Segoe UI", 9, "bold"),
            fg_color="#141B36", hover_color="#1E2545", text_color=t.get("text_muted", "#94A3B8"),
            corner_radius=8, command=self._toggle_topmost
        )
        self.btn_pin.pack(side="right", padx=(2, 4), pady=6)

        # Cuerpo dividido en 2 columnas panorámicas
        self.body_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Columna Izquierda: Reloj digital y botones rápidos
        self.col_left = ctk.CTkFrame(
            self.body_frame, fg_color=bg_card, width=185,
            corner_radius=14, border_width=1, border_color=border_col
        )
        self.col_left.pack(side="left", fill="both", padx=(0, 6), pady=2)
        self.col_left.pack_propagate(False)

        self.lbl_reloj = ctk.CTkLabel(
            self.col_left, text="00:00:00", font=("Segoe UI", 23, "bold"),
            text_color=aqua_col
        )
        self.lbl_reloj.pack(pady=(8, 0))

        self.lbl_fecha = ctk.CTkLabel(
            self.col_left, text="---", font=("Segoe UI", 9),
            text_color=t.get("text_muted", "#94A3B8")
        )
        self.lbl_fecha.pack(pady=(0, 8))

        btn_dictar = ctk.CTkButton(
            self.col_left, text="🎙️ Dictar a BIMO", font=("Segoe UI", 10, "bold"), height=32,
            fg_color=t.get("azul_acero", "#4F46E5"), hover_color=t.get("azul_pastel", "#6366F1"),
            text_color="#FFFFFF", corner_radius=10, command=self._enfocar_dictado
        )
        btn_dictar.pack(fill="x", padx=10, pady=(0, 5))

        btn_gcal_w = ctk.CTkButton(
            self.col_left, text="📅 Google Calendar", font=("Segoe UI", 9, "bold"), height=26,
            fg_color="#1E293B", hover_color="#334155", text_color=t.get("text_primary", "#CBD5E1"),
            corner_radius=8, command=lambda: webbrowser.open("https://calendar.google.com")
        )
        btn_gcal_w.pack(fill="x", padx=10, pady=(0, 6))

        # Columna Derecha: Agenda del día compacta
        self.col_right = ctk.CTkFrame(
            self.body_frame, fg_color=bg_card, corner_radius=14,
            border_width=1, border_color=border_col
        )
        self.col_right.pack(side="left", fill="both", expand=True, pady=2)

        self.header_citas = ctk.CTkFrame(self.col_right, fg_color="transparent")
        self.header_citas.pack(fill="x", padx=8, pady=(6, 2))

        ctk.CTkLabel(
            self.header_citas, text="📅 CITAS DE HOY", font=("Segoe UI", 9, "bold"),
            text_color=t.get("text_muted", "#94A3B8")
        ).pack(side="left")

        self.lbl_count_citas = ctk.CTkLabel(
            self.header_citas, text="", font=("Segoe UI", 8, "bold"),
            text_color=aqua_col
        )
        self.lbl_count_citas.pack(side="right")

        self.scroll_citas = ctk.CTkScrollableFrame(
            self.col_right, fg_color="transparent",
            scrollbar_button_color="#1E2545", scrollbar_button_hover_color="#28315C"
        )
        self.scroll_citas.pack(fill="both", expand=True, padx=4, pady=(0, 4))

    def _iniciar_auto_refresh(self):
        self.actualizar_agenda()
        self.after(30000, self._iniciar_auto_refresh)

    def _actualizar_reloj(self):
        from config import formatear_fecha_corta_es
        ahora = datetime.datetime.now()
        hora_str = ahora.strftime("%H:%M:%S")
        fecha_str = formatear_fecha_corta_es(ahora).capitalize()
        if hasattr(self, "lbl_reloj") and self.lbl_reloj.winfo_exists():
            self.lbl_reloj.configure(text=hora_str)
            self.lbl_fecha.configure(text=fecha_str)
            self.after(1000, self._actualizar_reloj)

    def _toggle_collapse(self):
        cur_geom = self.geometry()
        pos = "+".join(cur_geom.split("+")[1:])
        if not self._colapsado:
            self.body_frame.pack_forget()
            self.geometry(f"260x48+{pos}")
            self.btn_collapse.configure(text="＋")
            self._colapsado = True
        else:
            self.geometry(f"480x230+{pos}")
            self.body_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))
            self.btn_collapse.configure(text="─")
            self._colapsado = False

    def _toggle_topmost(self):
        self._is_topmost = not getattr(self, "_is_topmost", False)
        self.attributes("-topmost", self._is_topmost)
        t = obtener_tema_activo_dict()
        if self._is_topmost:
            self.btn_pin.configure(
                text="📌 Fijado",
                text_color=t.get("azul_pastel", "#818CF8"),
                fg_color="#1E1B4B"
            )
        else:
            self.btn_pin.configure(
                text="📌 Normal",
                text_color=t.get("text_muted", "#94A3B8"),
                fg_color="#141B36"
            )

    def _iniciar_arrastre(self, event):
        self._offset_x = event.x
        self._offset_y = event.y

    def _mover_widget(self, event):
        x = self.winfo_pointerx() - self._offset_x
        y = self.winfo_pointery() - self._offset_y
        self.geometry(f"+{x}+{y}")

    def _enfocar_dictado(self):
        if self.master_app:
            self.master_app.deiconify()
            self.master_app.lift()
            if hasattr(self.master_app, "mostrar_vista"):
                self.master_app.mostrar_vista("dictado")
        else:
            try:
                import ctypes
                user32 = ctypes.windll.user32
                def enum_cb(hwnd, lparam):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        title = buff.value
                        if "BIMO" in title and "HUD" not in title:
                            user32.ShowWindow(hwnd, 9)
                            user32.SetForegroundWindow(hwnd)
                            return False
                    return True
                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
                user32.EnumWindows(WNDENUMPROC(enum_cb), 0)
            except Exception as e:
                print(f"[HUD] Error al enfocar ventana principal: {e}")

    def actualizar_agenda(self):
        import threading
        if threading.current_thread() != threading.main_thread():
            self.after(0, self.actualizar_agenda)
            return

        try:
            t = obtener_tema_activo_dict()
            for w in list(self.scroll_citas.winfo_children()):
                try:
                    w.destroy()
                except Exception:
                    pass

            citas = listar_citas_db(limite=30)
            hoy_iso = datetime.date.today().isoformat()
            citas_hoy = [c for c in citas if c.get("fecha_hora_inicio", "").startswith(hoy_iso)]

            if hasattr(self, "lbl_count_citas") and self.lbl_count_citas.winfo_exists():
                count_txt = f"{len(citas_hoy)} hoy" if citas_hoy else "0 citas"
                self.lbl_count_citas.configure(text=count_txt)

            if not citas_hoy:
                ctk.CTkLabel(
                    self.scroll_citas, text="No hay citas agendadas para hoy.",
                    font=("Segoe UI", 9), text_color=t.get("text_muted", "#64748B")
                ).pack(pady=22)
                return

            ahora = datetime.datetime.now()
            for c in citas_hoy:
                paciente = c.get("nombre_paciente", "Paciente")
                f_ini = c.get("fecha_hora_inicio", "")
                desc = c.get("descripcion", "Consulta")

                hora_solo = f_ini.split(" ")[-1][:5] if " " in f_ini else f_ini[:5]

                try:
                    dt_cita = datetime.datetime.fromisoformat(f_ini.replace(" ", "T"))
                    es_pasada = dt_cita < ahora
                except Exception:
                    es_pasada = False

                color_hora = t.get("text_muted", "#64748B") if es_pasada else t.get("aqua", "#38BDF8")
                color_txt = t.get("text_muted", "#64748B") if es_pasada else t.get("text_primary", "#F8FAFC")

                card_c = ctk.CTkFrame(
                    self.scroll_citas, fg_color=t.get("bg_dark", "#070913"),
                    height=36, corner_radius=10, border_width=1,
                    border_color=t.get("border", "#1E2545")
                )
                card_c.pack(fill="x", pady=2)
                card_c.pack_propagate(False)

                # Pill de hora estilo badge
                pill_h = ctk.CTkFrame(card_c, fg_color="#0C253D" if not es_pasada else "#141A29", corner_radius=6)
                pill_h.pack(side="left", padx=(6, 4), pady=6)
                ctk.CTkLabel(
                    pill_h, text=hora_solo, font=("Segoe UI", 9, "bold"),
                    text_color=color_hora
                ).pack(padx=5, pady=1)

                info_frame = ctk.CTkFrame(card_c, fg_color="transparent")
                info_frame.pack(side="left", fill="both", expand=True, padx=2, pady=2)

                lbl_pac = ctk.CTkLabel(
                    info_frame, text=paciente, font=("Segoe UI", 9, "bold"),
                    text_color=color_txt, anchor="w"
                )
                lbl_pac.pack(side="top", anchor="w")

                if desc and desc != "Consulta":
                    lbl_desc = ctk.CTkLabel(
                        info_frame, text=desc, font=("Segoe UI", 8),
                        text_color=t.get("text_muted", "#94A3B8"), anchor="w"
                    )
                    lbl_desc.pack(side="top", anchor="w")

        except Exception as e:
            print(f"[FLOATING_WIDGET] Error actualizando agenda: {e}")
