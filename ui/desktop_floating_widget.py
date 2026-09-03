import datetime
import webbrowser
import customtkinter as ctk
from database import listar_citas_db
from config import obtener_tema_activo_dict, TEMAS_BIMO

class DesktopFloatingWidget(ctk.CTkToplevel):
    """
    Widget de escritorio flotante auténtico (sin barra tosca de ventana, arrastrable y Always-on-Top).
    Estilo Google Calendar con horarios a la izquierda y botón de acceso web.
    """
    def __init__(self, master_app=None):
        super().__init__()
        self.master_app = master_app
        t = obtener_tema_activo_dict()

        # 1. Eliminar bordes y barra de título de Windows para ser un Widget real de escritorio
        from config import es_modo_bajo_rendimiento
        self.overrideredirect(True)
        # NO forzar topmost para no superponerse sobre las ventanas de trabajo del profesional
        self.attributes("-topmost", False)
        if not es_modo_bajo_rendimiento():
            self.attributes("-alpha", 0.90)
        self.configure(fg_color=t["bg_dark"])
        self.resizable(False, False)
        try:
            self.lower()
        except Exception:
            pass

        # 2. Posicionar en formato panorámico (más ancho que largo: 460x220px)
        ancho_pantalla = self.winfo_screenwidth()
        pos_x = max(10, ancho_pantalla - 485)
        self.geometry(f"460x220+{pos_x}+45")

        # Variables para arrastrar y modo dock pill
        self._offset_x = 0
        self._offset_y = 0
        self._colapsado = False

        self._build_ui()
        self._actualizar_reloj()
        self.actualizar_agenda()

    def aplicar_tema(self, nombre_tema):
        t = TEMAS_BIMO.get(nombre_tema, TEMAS_BIMO["Bimo Classic"])
        self.configure(fg_color=t["bg_dark"])
        if hasattr(self, "main_frame"):
            self.main_frame.configure(fg_color=t["bg_dark"], border_color=t["border"])
        if hasattr(self, "header"):
            self.header.configure(fg_color=t["card_dark"])
        self.actualizar_agenda()

    def _build_ui(self):
        t = obtener_tema_activo_dict()
        self.main_frame = ctk.CTkFrame(self, fg_color=t["bg_dark"], corner_radius=16, border_width=1.5, border_color=t["border"])
        self.main_frame.pack(fill="both", expand=True)

        # Barra superior arrastrable (Header)
        self.header = ctk.CTkFrame(self.main_frame, fg_color=t["card_dark"], height=36, corner_radius=12)
        self.header.pack(fill="x", padx=4, pady=4)
        self.header.pack_propagate(False)

        self.header.bind("<ButtonPress-1>", self._iniciar_arrastre)
        self.header.bind("<B1-Motion>", self._mover_widget)

        left_h = ctk.CTkFrame(self.header, fg_color="transparent")
        left_h.pack(side="left", padx=10)
        left_h.bind("<ButtonPress-1>", self._iniciar_arrastre)
        left_h.bind("<B1-Motion>", self._mover_widget)

        lbl_tit = ctk.CTkLabel(left_h, text="🏥 BIMO MEDICAL HUD", font=("Segoe UI", 10, "bold"), text_color=t["aqua"])
        lbl_tit.pack(side="left")
        lbl_tit.bind("<ButtonPress-1>", self._iniciar_arrastre)
        lbl_tit.bind("<B1-Motion>", self._mover_widget)

        self.lbl_status_dot = ctk.CTkLabel(left_h, text=" ● En Línea", font=("Segoe UI", 9, "bold"), text_color="#10b981")
        self.lbl_status_dot.pack(side="left", padx=(4, 0))

        btn_close = ctk.CTkButton(
            self.header, text="✕", width=22, height=22, font=("Segoe UI", 9, "bold"),
            fg_color="transparent", text_color=t["text_muted"], hover_color="#dc2626", command=self.withdraw
        )
        btn_close.pack(side="right", padx=(2, 6))

        self.btn_collapse = ctk.CTkButton(
            self.header, text="➖", width=22, height=22, font=("Segoe UI", 9, "bold"),
            fg_color="transparent", text_color=t["text_muted"], hover_color=t["card_hover"], command=self._toggle_collapse
        )
        self.btn_collapse.pack(side="right", padx=(2, 2))

        # Cuerpo dividido en 2 columnas panorámicas
        self.body_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.body_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))

        # Columna Izquierda: Reloj digital y botones rápidos
        self.col_left = ctk.CTkFrame(self.body_frame, fg_color=t["card_dark"], width=175, corner_radius=12, border_width=1, border_color=t["border"])
        self.col_left.pack(side="left", fill="both", padx=(0, 6), pady=2)
        self.col_left.pack_propagate(False)

        self.lbl_reloj = ctk.CTkLabel(self.col_left, text="00:00:00", font=("Segoe UI", 20, "bold"), text_color=t["aqua"])
        self.lbl_reloj.pack(pady=(10, 0))

        self.lbl_fecha = ctk.CTkLabel(self.col_left, text="---", font=("Segoe UI", 10), text_color=t["text_muted"])
        self.lbl_fecha.pack(pady=(0, 8))

        btn_dictar = ctk.CTkButton(
            self.col_left, text="🎤 Dictar", font=("Segoe UI", 10, "bold"), height=28,
            fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff", corner_radius=8,
            command=self._enfocar_dictado
        )
        btn_dictar.pack(fill="x", padx=12, pady=(0, 4))

        btn_gcal_w = ctk.CTkButton(
            self.col_left, text="🌐 Calendar Web", font=("Segoe UI", 10), height=26,
            fg_color="transparent", hover_color=t["card_hover"], text_color=t["text_primary"], corner_radius=8,
            command=lambda: webbrowser.open("https://calendar.google.com")
        )
        btn_gcal_w.pack(fill="x", padx=12, pady=(0, 4))

        # Columna Derecha: Agenda del día compacta
        self.col_right = ctk.CTkFrame(self.body_frame, fg_color=t["card_dark"], corner_radius=12, border_width=1, border_color=t["border"])
        self.col_right.pack(side="left", fill="both", expand=True, pady=2)

        header_citas = ctk.CTkFrame(self.col_right, fg_color="transparent")
        header_citas.pack(fill="x", padx=10, pady=(6, 2))
        ctk.CTkLabel(header_citas, text="📅 CITAS DE HOY", font=("Segoe UI", 9, "bold"), text_color=t["text_muted"]).pack(side="left")

        self.scroll_citas = ctk.CTkScrollableFrame(self.col_right, fg_color="transparent")
        self.scroll_citas.pack(fill="both", expand=True, padx=4, pady=(0, 4))

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
            self.geometry(f"240x44+{pos}")
            self.btn_collapse.configure(text="➕")
            self._colapsado = True
        else:
            self.geometry(f"460x220+{pos}")
            self.body_frame.pack(fill="both", expand=True, padx=8, pady=(0, 6))
            self.btn_collapse.configure(text="➖")
            self._colapsado = False

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

            if not citas_hoy:
                ctk.CTkLabel(
                    self.scroll_citas, text="No hay citas agendadas para hoy.",
                    font=("Segoe UI", 9), text_color=t["text_muted"]
                ).pack(pady=20)
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

                color_hora = t["text_muted"] if es_pasada else t["aqua"]
                color_txt = t["text_muted"] if es_pasada else t["text_primary"]

                card_c = ctk.CTkFrame(self.scroll_citas, fg_color=t["bg_dark"], height=34, corner_radius=8, border_width=1, border_color=t["border"])
                card_c.pack(fill="x", pady=2)
                card_c.pack_propagate(False)

                ctk.CTkLabel(card_c, text=hora_solo, width=42, font=("Segoe UI", 9, "bold"), text_color=color_hora).pack(side="left", padx=(6, 2))
                ctk.CTkLabel(card_c, text=f"{paciente} • {desc}", font=("Segoe UI", 9), text_color=color_txt, anchor="w").pack(side="left", fill="x", expand=True, padx=4)

        except Exception as e:
            print(f"[FLOATING_WIDGET] Error actualizando agenda: {e}")
