import datetime
import webbrowser
import customtkinter as ctk
from database import listar_citas_db
from config import obtener_tema_activo_dict
from calendar_sync import generar_url_evento_google

def extraer_fecha_y_hora(f_str: str):
    """Extrae de forma robusta la fecha ISO (AAAA-MM-DD) y la hora formateada (HH:MM)."""
    if not f_str:
        return "", "--:--"
    limpio = str(f_str).strip().replace("T", " ")
    partes = limpio.split(" ")
    dia_iso = partes[0]
    hora = partes[1][:5] if len(partes) > 1 else "09:00"
    return dia_iso, hora

class VentanaCalendarioSemanalGrande(ctk.CTkToplevel):
    """
    Ventana grande de alta definición para visualizar la agenda completa de Lunes a Sábado
    organizada en 6 columnas proporcionales e indeformables con navegación fluida y sin saltos.
    """
    def __init__(self, master, offset_semanas=0):
        super().__init__(master)
        self.offset_semanas = offset_semanas
        self.title("BIMO Pro - Agenda Semanal Clínica (Lunes a Sábado)")
        self.geometry("1180x720")
        self.minsize(980, 600)
        self.attributes("-topmost", True)
        
        self.t = obtener_tema_activo_dict()
        self.configure(fg_color=self.t["bg_dark"])

        self._build_ui()
        self._cargar_semana()

    def _build_ui(self):
        t = self.t

        # 1. Barra Superior con navegación y controles ejecutivos
        top_bar = ctk.CTkFrame(self, fg_color=t["card_dark"], height=60, corner_radius=0, border_width=1, border_color=t["border"])
        top_bar.pack(fill="x", side="top")

        btn_prev = ctk.CTkButton(
            top_bar, text="◀ Semana Anterior", width=140, height=34, font=("Segoe UI", 11, "bold"),
            fg_color=t["input_bg"], hover_color=t["card_hover"], text_color=t["text_primary"],
            border_width=1, border_color=t["border"], corner_radius=8,
            command=self._prev_semana
        )
        btn_prev.pack(side="left", padx=(18, 8), pady=12)

        btn_hoy = ctk.CTkButton(
            top_bar, text="Hoy / Esta Semana", width=130, height=34, font=("Segoe UI", 11, "bold"),
            fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff",
            corner_radius=8, command=self._reset_semana
        )
        btn_hoy.pack(side="left", padx=4, pady=12)

        btn_next = ctk.CTkButton(
            top_bar, text="Semana Siguiente ▶", width=140, height=34, font=("Segoe UI", 11, "bold"),
            fg_color=t["input_bg"], hover_color=t["card_hover"], text_color=t["text_primary"],
            border_width=1, border_color=t["border"], corner_radius=8,
            command=self._next_semana
        )
        btn_next.pack(side="left", padx=8, pady=12)

        self.lbl_rango_semana = ctk.CTkLabel(
            top_bar, text="Cargando...", font=("Segoe UI", 13, "bold"), text_color=t["aqua"]
        )
        self.lbl_rango_semana.pack(side="left", padx=20, expand=True)

        btn_gcal = ctk.CTkButton(
            top_bar, text="🌐 Abrir Google Calendar Web", width=200, height=34, font=("Segoe UI", 11, "bold"),
            fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff",
            corner_radius=8, command=lambda: webbrowser.open("https://calendar.google.com")
        )
        btn_gcal.pack(side="right", padx=(8, 18), pady=12)

        # 2. Contenedor horizontal de las 6 columnas fijas de la semana (Lunes a Sábado)
        self.container_columnas = ctk.CTkFrame(self, fg_color="transparent")
        self.container_columnas.pack(fill="both", expand=True, padx=14, pady=12)

        # Pre-construir las 6 columnas una sola vez para máxima fluidez y 60 FPS
        self.cols_ui = []
        for i in range(6):
            col_frame = ctk.CTkFrame(
                self.container_columnas,
                fg_color=t["card_dark"],
                corner_radius=12,
                border_width=1,
                border_color=t["border"]
            )
            col_frame.pack(side="left", fill="both", expand=True, padx=4)

            header_col = ctk.CTkFrame(col_frame, fg_color=t["bg_dark"], corner_radius=10, height=48)
            header_col.pack(fill="x", padx=4, pady=4)

            lbl_tit = ctk.CTkLabel(header_col, text="", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"])
            lbl_tit.pack(pady=(6, 2))

            lbl_count = ctk.CTkLabel(header_col, text="", font=("Segoe UI", 9), text_color=t["text_muted"])
            lbl_count.pack(pady=(0, 6))

            scroll_citas_col = ctk.CTkScrollableFrame(col_frame, fg_color="transparent", corner_radius=6)
            scroll_citas_col.pack(fill="both", expand=True, padx=4, pady=(2, 6))

            self.cols_ui.append({
                "frame": col_frame,
                "header": header_col,
                "lbl_tit": lbl_tit,
                "lbl_count": lbl_count,
                "scroll": scroll_citas_col
            })

    def _prev_semana(self):
        self.offset_semanas -= 1
        self._cargar_semana()

    def _next_semana(self):
        self.offset_semanas += 1
        self._cargar_semana()

    def _reset_semana(self):
        self.offset_semanas = 0
        self._cargar_semana()

    def _cargar_semana(self):
        t = self.t

        hoy = datetime.date.today() + datetime.timedelta(weeks=self.offset_semanas)
        lunes = hoy - datetime.timedelta(days=hoy.weekday())
        dias_semana = [lunes + datetime.timedelta(days=i) for i in range(6)]
        sabado = dias_semana[-1]

        meses_es = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        txt_rango = f"🗓️ {lunes.day} {meses_es[lunes.month]} — {sabado.day} {meses_es[sabado.month]} {sabado.year}"
        self.lbl_rango_semana.configure(text=txt_rango)

        todas_citas = listar_citas_db(limite=200)

        # Agrupar citas por fecha ISO
        citas_por_dia = {dia.isoformat(): [] for dia in dias_semana}
        for c in todas_citas:
            f_ini = c.get("fecha_hora_inicio") or c.get("fecha") or ""
            dia_iso, hora_txt = extraer_fecha_y_hora(f_ini)
            if dia_iso in citas_por_dia:
                c_copy = dict(c)
                c_copy["hora_formateada"] = hora_txt
                citas_por_dia[dia_iso].append(c_copy)

        # Ordenar citas cronológicamente dentro de cada día
        for dia_iso in citas_por_dia:
            citas_por_dia[dia_iso].sort(key=lambda x: x.get("hora_formateada", "00:00"))

        nombres_dias = ["LUNES", "MARTES", "MIÉRCOLES", "JUEVES", "VIERNES", "SÁBADO"]
        hoy_real = datetime.date.today()

        # Actualizar en caliente cada una de las 6 columnas sin reconstrucción pesada
        for idx, dia in enumerate(dias_semana):
            if idx >= len(self.cols_ui):
                break

            ui_col = self.cols_ui[idx]
            dia_iso = dia.isoformat()
            citas_este_dia = citas_por_dia[dia_iso]
            es_hoy = (dia == hoy_real)

            # Estilo dinámico de columna
            ui_col["frame"].configure(
                border_width=1.5 if es_hoy else 1,
                border_color=t["aqua"] if es_hoy else t["border"]
            )
            ui_col["header"].configure(
                fg_color=t["card_hover"] if es_hoy else t["bg_dark"]
            )

            titulo_dia = f"{nombres_dias[idx]} {dia.day} {meses_es[dia.month]}"
            if es_hoy:
                titulo_dia += " [HOY]"

            ui_col["lbl_tit"].configure(
                text=titulo_dia,
                text_color=t["aqua"] if es_hoy else t["text_primary"]
            )

            ui_col["lbl_count"].configure(
                text=f"{len(citas_este_dia)} {'cita' if len(citas_este_dia) == 1 else 'citas'}",
                text_color=t["azul_pastel"] if citas_este_dia else t["text_muted"]
            )

            # Limpiar únicamente las tarjetas de citas internas
            scroll = ui_col["scroll"]
            for w in list(scroll.winfo_children()):
                try:
                    w.destroy()
                except Exception:
                    pass

            if citas_este_dia:
                for c in citas_este_dia:
                    paciente = c.get("nombre_paciente", "Paciente")
                    motivo = c.get("descripcion", "Consulta Odontológica")
                    hora_c = c.get("hora_formateada", "--:--")
                    f_inicio_full = c.get("fecha_hora_inicio", "")
                    f_fin_full = c.get("fecha_hora_fin", "")

                    card_cita = ctk.CTkFrame(
                        scroll,
                        fg_color=t["bg_dark"],
                        corner_radius=8,
                        border_width=1,
                        border_color=t["border"]
                    )
                    card_cita.pack(fill="x", pady=4, padx=2)

                    top_c = ctk.CTkFrame(card_cita, fg_color="transparent")
                    top_c.pack(fill="x", padx=8, pady=(6, 2))

                    badge_hora = ctk.CTkFrame(top_c, fg_color=t["aqua"], corner_radius=4)
                    badge_hora.pack(side="left")
                    ctk.CTkLabel(
                        badge_hora, text=f"⏰ {hora_c}", font=("Segoe UI", 9, "bold"),
                        text_color="#0b0f19"
                    ).pack(padx=5, pady=1)

                    # Botón discreto para abrir en Google Calendar
                    url_g = generar_url_evento_google(
                        f"BIMO: {paciente} - {motivo}",
                        f_inicio_full, f_fin_full,
                        f"Paciente: {paciente}\nProcedimiento: {motivo}\nSoftware Clínico BIMO"
                    )
                    btn_open_g = ctk.CTkButton(
                        top_c, text="🌐 Google", width=55, height=20, font=("Segoe UI", 8, "bold"),
                        fg_color=t["input_bg"], hover_color=t["azul_pastel"], text_color=t["text_primary"],
                        corner_radius=4, command=lambda u=url_g: webbrowser.open(u)
                    )
                    btn_open_g.pack(side="right")

                    ctk.CTkLabel(
                        card_cita, text=f"👤 {paciente}", font=("Segoe UI", 10, "bold"),
                        text_color=t["text_primary"], anchor="w"
                    ).pack(fill="x", padx=8, pady=(4, 1))

                    ctk.CTkLabel(
                        card_cita, text=f"🦷 {motivo}", font=("Segoe UI", 8),
                        text_color=t["azul_pastel"], anchor="w", wraplength=145
                    ).pack(fill="x", padx=8, pady=(0, 6))
            else:
                card_vacia = ctk.CTkFrame(scroll, fg_color="transparent")
                card_vacia.pack(fill="both", expand=True, pady=30)
                ctk.CTkLabel(
                    card_vacia, text="✨ Libre\nSin citas", font=("Segoe UI", 9, "italic"),
                    text_color=t["text_muted"], justify="center"
                ).pack()

        self.update_idletasks()


class CalendarWidget(ctk.CTkFrame):
    """
    Widget de Agenda Clínica con vista dual:
    - Vista Diaria (08:00 a 19:00) con indicador en tiempo real.
    - Vista Semanal Completa (Lunes a Sábado) con tarjetas proporcionadas.
    - Botón para abrir ventana completa ampliada.
    """
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self.vista_actual = "dia"
        self._build_ui()
        self.actualizar_citas()

    def _build_ui(self):
        t = obtener_tema_activo_dict()

        h_frame = ctk.CTkFrame(self, fg_color="transparent")
        h_frame.pack(fill="x", pady=(0, 6))

        self.btn_vista_dia = ctk.CTkButton(
            h_frame, text="📅 Hoy", width=68, height=26, font=("Segoe UI", 10, "bold"),
            fg_color=t["aqua"], hover_color=t["azul_pastel"], text_color="#0b0f19",
            corner_radius=6, command=lambda: self.cambiar_vista("dia")
        )
        self.btn_vista_dia.pack(side="left", padx=(0, 4))

        self.btn_vista_semana = ctk.CTkButton(
            h_frame, text="📆 Semana", width=85, height=26, font=("Segoe UI", 10, "bold"),
            fg_color=t["card_dark"], hover_color=t["card_hover"], text_color=t["text_primary"],
            border_width=1, border_color=t["border"], corner_radius=6,
            command=lambda: self.cambiar_vista("semana")
        )
        self.btn_vista_semana.pack(side="left", padx=2)

        btn_expand = ctk.CTkButton(
            h_frame, text="⛶ Ampliar", width=75, height=26, font=("Segoe UI", 9, "bold"),
            fg_color=t["azul_acero"], hover_color=t["azul_pastel"], text_color="#ffffff",
            corner_radius=6, command=self._abrir_ventana_grande
        )
        btn_expand.pack(side="right", padx=(4, 0))

        btn_gcal = ctk.CTkButton(
            h_frame, text="🌐 Google", width=70, height=26, font=("Segoe UI", 9, "bold"),
            fg_color=t["input_bg"], hover_color=t["card_hover"], text_color=t["text_primary"],
            border_width=1, border_color=t["border"], corner_radius=6,
            command=lambda: webbrowser.open("https://calendar.google.com")
        )
        btn_gcal.pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=10)
        self.scroll.pack(fill="both", expand=True)

    def cambiar_vista(self, vista: str):
        t = obtener_tema_activo_dict()
        self.vista_actual = vista
        if vista == "dia":
            self.btn_vista_dia.configure(fg_color=t["aqua"], text_color="#0b0f19")
            self.btn_vista_semana.configure(fg_color=t["card_dark"], text_color=t["text_primary"])
        else:
            self.btn_vista_semana.configure(fg_color=t["aqua"], text_color="#0b0f19")
            self.btn_vista_dia.configure(fg_color=t["card_dark"], text_color=t["text_primary"])
        self.actualizar_citas()

    def _abrir_ventana_grande(self):
        try:
            VentanaCalendarioSemanalGrande(self)
        except Exception as e:
            print(f"[CALENDAR] Error abriendo ventana grande: {e}")

    def actualizar_citas(self):
        import threading
        if threading.current_thread() != threading.main_thread():
            self.after(0, self.actualizar_citas)
            return

        try:
            t = obtener_tema_activo_dict()
            for w in list(self.scroll.winfo_children()):
                try:
                    w.pack_forget()
                    w.destroy()
                except Exception:
                    pass

            citas = listar_citas_db(limite=80)

            if self.vista_actual == "dia":
                self._render_vista_dia(citas, t)
            else:
                self._render_vista_semana(citas, t)
        except Exception as e:
            print(f"[CALENDAR_WIDGET] Error actualizando citas: {e}")

    def _render_vista_dia(self, citas: list, t: dict):
        hoy_iso = datetime.date.today().isoformat()
        citas_hoy = [c for c in citas if c.get("fecha_hora_inicio", "").startswith(hoy_iso) or c.get("fecha", "") == hoy_iso]

        citas_por_hora = {}
        for c in citas_hoy:
            try:
                f_ini = c.get("fecha_hora_inicio", "")
                _, hora_txt = extraer_fecha_y_hora(f_ini)
                hora_num = int(hora_txt.split(":")[0])
                citas_por_hora[hora_num] = c
            except Exception:
                pass

        ahora = datetime.datetime.now()
        hora_actual = ahora.hour

        for h in range(8, 20):
            row = ctk.CTkFrame(self.scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)

            es_pasada = (h < hora_actual)
            es_actual = (h == hora_actual)

            color_hora = t["text_muted"] if es_pasada else (t["aqua"] if es_actual else t["text_primary"])
            ctk.CTkLabel(
                row, text=f"{h:02d}:00", width=42, font=("Segoe UI", 10, "bold"),
                text_color=color_hora, anchor="e"
            ).pack(side="left", padx=(2, 6))

            bg_card = t["bg_dark"] if es_pasada else t["card_dark"]
            slot = ctk.CTkFrame(row, fg_color=bg_card, corner_radius=8, border_width=1, border_color=t["border"])
            slot.pack(side="left", fill="both", expand=True)

            if h in citas_por_hora:
                c = citas_por_hora[h]
                paciente = c.get("nombre_paciente", "Paciente")
                motivo = c.get("descripcion", "Consulta")
                f_ini_c = c.get("fecha_hora_inicio", "")
                f_fin_c = c.get("fecha_hora_fin", "")

                color_bar = t["text_muted"] if es_pasada else (t["amarillo"] if es_actual else t["aqua"])
                color_paciente = t["text_muted"] if es_pasada else t["text_primary"]
                color_motivo = t["text_muted"] if es_pasada else t["azul_pastel"]

                bar = ctk.CTkFrame(slot, fg_color=color_bar, width=4, corner_radius=2)
                bar.pack(side="left", fill="y", padx=(2, 6), pady=2)

                tbox = ctk.CTkFrame(slot, fg_color="transparent")
                tbox.pack(side="left", fill="both", expand=True, pady=2)

                ctk.CTkLabel(tbox, text=paciente, font=("Segoe UI", 10, "bold"), text_color=color_paciente, anchor="w").pack(fill="x")
                estado_txt = " (✓ Pasada)" if es_pasada else (" (● En curso)" if es_actual else "")
                ctk.CTkLabel(tbox, text=f"• {motivo}{estado_txt}", font=("Segoe UI", 8), text_color=color_motivo, anchor="w").pack(fill="x")

                url_g = generar_url_evento_google(f"BIMO: {paciente} - {motivo}", f_ini_c, f_fin_c, motivo)
                btn_g = ctk.CTkButton(
                    slot, text="🌐", width=28, height=24, font=("Segoe UI", 10),
                    fg_color=t["input_bg"], hover_color=t["card_hover"], text_color=t["text_primary"],
                    corner_radius=6, command=lambda u=url_g: webbrowser.open(u)
                )
                btn_g.pack(side="right", padx=6)
            else:
                ctk.CTkLabel(
                    slot, text="— Libre —", font=("Segoe UI", 8),
                    text_color=t["text_muted"], anchor="w"
                ).pack(fill="x", padx=8, pady=4)

    def _render_vista_semana(self, citas: list, t: dict):
        hoy = datetime.date.today()
        lunes = hoy - datetime.timedelta(days=hoy.weekday())
        dias_semana = [lunes + datetime.timedelta(days=i) for i in range(6)]
        nombres_dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]
        meses_es = ["", "Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

        for idx, dia in enumerate(dias_semana):
            dia_iso = dia.isoformat()
            citas_dia = []
            for c in citas:
                f_i = c.get("fecha_hora_inicio") or c.get("fecha") or ""
                d_iso, h_txt = extraer_fecha_y_hora(f_i)
                if d_iso == dia_iso:
                    c_dict = dict(c)
                    c_dict["hora_formateada"] = h_txt
                    citas_dia.append(c_dict)

            citas_dia.sort(key=lambda x: x.get("hora_formateada", "00:00"))
            es_hoy = (dia == hoy)

            dia_card = ctk.CTkFrame(
                self.scroll, 
                fg_color=t["card_dark"], 
                corner_radius=8, 
                border_width=1, 
                border_color=t["aqua"] if es_hoy else t["border"]
            )
            dia_card.pack(fill="x", pady=3)

            h_dia = ctk.CTkFrame(dia_card, fg_color=t["card_hover"] if es_hoy else "transparent", corner_radius=6)
            h_dia.pack(fill="x", padx=4, pady=3)

            txt_badge = f"📅 {nombres_dias[idx]} {dia.day} {meses_es[dia.month]}"
            if es_hoy:
                txt_badge += "  [HOY]"
            ctk.CTkLabel(
                h_dia, text=txt_badge, font=("Segoe UI", 10, "bold"),
                text_color=t["aqua"] if es_hoy else t["text_primary"]
            ).pack(side="left", padx=4, pady=2)

            ctk.CTkLabel(
                h_dia, text=f"{len(citas_dia)} citas", font=("Segoe UI", 8),
                text_color=t["text_muted"]
            ).pack(side="right", padx=6)

            if citas_dia:
                for c in citas_dia:
                    hora_txt = c.get("hora_formateada", "--:--")
                    paciente = c.get("nombre_paciente", "Paciente")
                    motivo = c.get("descripcion", "Consulta")
                    f_ini = c.get("fecha_hora_inicio", "")
                    f_fin = c.get("fecha_hora_fin", "")

                    c_row = ctk.CTkFrame(dia_card, fg_color="transparent")
                    c_row.pack(fill="x", padx=8, pady=2)

                    ctk.CTkLabel(c_row, text=hora_txt, width=42, font=("Segoe UI", 9, "bold"), text_color=t["aqua"], anchor="w").pack(side="left")
                    ctk.CTkLabel(c_row, text=f"{paciente} • {motivo}", font=("Segoe UI", 9), text_color=t["text_primary"], anchor="w").pack(side="left", fill="x", expand=True)

                    url_g = generar_url_evento_google(f"BIMO: {paciente} - {motivo}", f_ini, f_fin, motivo)
                    ctk.CTkButton(
                        c_row, text="🌐", width=24, height=20, font=("Segoe UI", 8),
                        fg_color=t["input_bg"], hover_color=t["card_hover"], text_color=t["text_primary"],
                        corner_radius=4, command=lambda u=url_g: webbrowser.open(u)
                    ).pack(side="right", padx=2)
            else:
                ctk.CTkLabel(dia_card, text="Sin citas agendadas", font=("Segoe UI", 8, "italic"), text_color=t["text_muted"]).pack(padx=8, pady=3)
