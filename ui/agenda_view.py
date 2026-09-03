import datetime
import customtkinter as ctk
from database import buscar_pacientes, buscar_paciente_por_cedula, registrar_o_actualizar_paciente, limpiar_agenda_local_db
from calendar_sync import agendar_cita, obtener_citas, eliminar_cita
from config import (
    obtener_tema_activo_dict,
    COLOR_BG_DARK, COLOR_CARD_DARK, COLOR_AZUL_ACERO, COLOR_AZUL_PASTEL,
    COLOR_AQUA, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED,
    CORNER_RADIUS_CARD, CORNER_RADIUS_BTN
)

from ui.animations import bind_hover_microscale

class AgendaView(ctk.CTkFrame):
    def __init__(self, master):
        self.theme = obtener_tema_activo_dict()
        super().__init__(master, fg_color="transparent")
        self._build_ui()
        self._cargar_citas()

    def _build_ui(self):
        t = self.theme

        # Header Superior Pulido
        top_bar = ctk.CTkFrame(self, fg_color=t["card_dark"], height=68, corner_radius=t["corner_radius"], border_width=1, border_color=t["border"])
        top_bar.pack(fill="x", padx=16, pady=(12, 10))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(top_bar, text="📅 Agenda Médica & Google Calendar", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"]).pack(side="left", padx=16)

        btn_refresh = ctk.CTkButton(
            top_bar, text="🔄 Actualizar", width=110, height=36, font=("Segoe UI", 11, "bold"),
            fg_color="#334155", hover_color="#475569", corner_radius=t["corner_btn"], command=self._cargar_citas
        )
        btn_refresh.pack(side="right", padx=(6, 16))
        bind_hover_microscale(btn_refresh)

        # Contenedor dividido en lista y formulario
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        # Panel Izquierdo: Lista de Citas con scroll
        self.panel_citas = ctk.CTkScrollableFrame(content, fg_color=t["card_dark"], corner_radius=t["corner_radius"], border_width=1, border_color=t["border"])
        self.panel_citas.pack(side="left", fill="both", expand=True, padx=(0, 12))

        # Panel Derecho: Formulario para Agendar Estricto por Cédula (Más amplio y espacioso)
        form_panel = ctk.CTkFrame(content, fg_color=t["card_dark"], corner_radius=t["corner_radius"], border_width=1, border_color=t["border"], width=420)
        form_panel.pack(side="right", fill="both")
        form_panel.pack_propagate(False)

        ctk.CTkLabel(form_panel, text="PROGRAMAR NUEVA CITA", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"]).pack(pady=(16, 10), padx=20, anchor="w")

        # Cédula Prioritaria
        ctk.CTkLabel(form_panel, text="🆔 Cédula de Identidad (Prioritaria)", font=("Segoe UI", 11, "bold"), text_color=t["aqua"]).pack(anchor="w", padx=20, pady=(2, 2))
        self.entry_cedula = ctk.CTkEntry(
            form_panel, height=38, corner_radius=10, placeholder_text="Ingrese cédula para autocompletar...",
            fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"]
        )
        self.entry_cedula.pack(fill="x", padx=20, pady=(0, 4))
        self.entry_cedula.bind("<KeyRelease>", self._on_cedula_change)

        self.lbl_paciente_detectado = ctk.CTkLabel(form_panel, text="", font=("Segoe UI", 10, "bold"), text_color=t["aqua"])
        self.lbl_paciente_detectado.pack(anchor="w", padx=20, pady=(0, 6))

        ctk.CTkLabel(form_panel, text="Nombre Completo del Paciente", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(anchor="w", padx=20, pady=(2, 2))
        self.entry_nombre = ctk.CTkEntry(form_panel, height=36, corner_radius=10, placeholder_text="Nombre completo", fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_nombre.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(form_panel, text="Teléfono de Contacto", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(anchor="w", padx=20, pady=(2, 2))
        self.entry_tel = ctk.CTkEntry(form_panel, height=36, corner_radius=10, placeholder_text="Ej: 0987654321", fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_tel.pack(fill="x", padx=20, pady=(0, 8))

        ctk.CTkLabel(form_panel, text="Fecha y Hora (YYYY-MM-DD HH:MM)", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(anchor="w", padx=20, pady=(2, 2))
        self.entry_fecha = ctk.CTkEntry(form_panel, height=36, corner_radius=10, fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_fecha.pack(fill="x", padx=20, pady=(0, 8))
        ahora_str = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d 10:00")
        self.entry_fecha.insert(0, ahora_str)

        ctk.CTkLabel(form_panel, text="Tratamiento / Procedimiento Odontológico (Opcional)", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(anchor="w", padx=20, pady=(2, 2))
        self.entry_desc = ctk.CTkEntry(form_panel, height=36, corner_radius=10, placeholder_text="Ej: Profilaxis / Calza (opcional)", fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"])
        self.entry_desc.pack(fill="x", padx=20, pady=(0, 12))

        self.lbl_mensaje = ctk.CTkLabel(form_panel, text="", font=("Segoe UI", 11, "bold"))
        self.lbl_mensaje.pack(pady=(0, 6))

        btn_agendar = ctk.CTkButton(
            form_panel, text="🗓️ Agendar y Sincronizar", height=42, font=("Segoe UI", 11, "bold"),
            fg_color=t["azul_acero"], hover_color=t["azul_pastel"], corner_radius=t["corner_btn"],
            command=self._guardar_cita
        )
        btn_agendar.pack(fill="x", padx=20, pady=(0, 14))
        bind_hover_microscale(btn_agendar)

    def _on_cedula_change(self, event=None):
        ced = self.entry_cedula.get().strip().replace(" ", "")
        if len(ced) >= 5:
            pac = buscar_paciente_por_cedula(ced)
            if pac:
                self.lbl_paciente_detectado.configure(text=f"✓ Paciente registrado: {pac.get('nombre')} ({pac.get('edad', 'N/E')} años)", text_color=self.theme["aqua"])
                self.entry_nombre.delete(0, "end")
                self.entry_nombre.insert(0, pac.get("nombre", ""))
                tel = pac.get("telefono") or pac.get("contacto_emergencia") or ""
                if tel and tel.lower() != "no especificado":
                    self.entry_tel.delete(0, "end")
                    self.entry_tel.insert(0, tel)
            else:
                self.lbl_paciente_detectado.configure(text="● Paciente nuevo (se creará con esta cédula)", text_color=self.theme["amarillo"])
        else:
            self.lbl_paciente_detectado.configure(text="")

    def _cargar_citas(self):
        # Auto-reparación silenciosa en segundo plano
        try:
            limpiar_agenda_local_db()
        except Exception:
            pass

        t = self.theme
        for w in self.panel_citas.winfo_children():
            w.destroy()

        citas = obtener_citas()
        if not citas:
            ctk.CTkLabel(self.panel_citas, text="No hay citas programadas actualmente.", font=("Segoe UI", 12), text_color=t["text_muted"]).pack(pady=40)
            return

        ahora = datetime.datetime.now()

        for c in citas:
            f_str = c.get("fecha_hora_inicio", "")
            es_pasada = False
            try:
                dt_cita = datetime.datetime.fromisoformat(f_str.replace(" ", "T"))
                if dt_cita < ahora:
                    es_pasada = True
            except Exception:
                es_pasada = False

            bg_card = "#161d2b" if (es_pasada and t["mode"] == "dark") else ("#f1f5f9" if es_pasada else t["bg_dark"])
            border_col = t["border"] if es_pasada else t["aqua"]
            text_col = t["text_muted"] if es_pasada else t["text_primary"]
            estado_badge = "✓ Pasada" if es_pasada else "● Activa / Próxima"
            badge_col = t["text_muted"] if es_pasada else t["aqua"]

            card = ctk.CTkFrame(self.panel_citas, fg_color=bg_card, corner_radius=14, border_width=1, border_color=border_col)
            card.pack(fill="x", padx=12, pady=5)

            paciente = c.get("nombre_paciente", "Paciente")
            tel = c.get("telefono", "")
            desc = c.get("descripcion", "Consulta general")
            cid = c.get("id")

            left_box = ctk.CTkFrame(card, fg_color="transparent")
            left_box.pack(side="left", fill="both", expand=True, padx=14, pady=8)

            ctk.CTkLabel(left_box, text=f"{paciente}  [{estado_badge}]", font=("Segoe UI", 11, "bold"), text_color=badge_col, anchor="w").pack(fill="x")
            txt_detalles = f"🗓️ {f_str}  |  📞 {tel or 'Sin teléfono'}\n• Tratamiento: {desc}"
            ctk.CTkLabel(left_box, text=txt_detalles, font=("Segoe UI", 10), text_color=text_col, justify="left", anchor="w").pack(fill="x", pady=(2, 0))

            # Botón de borrado individual rápido
            btn_del = ctk.CTkButton(
                card, text="🗑️", width=36, height=36, font=("Segoe UI", 12),
                fg_color="transparent", hover_color="#dc2626", text_color="#ef4444",
                corner_radius=10, command=lambda cita_id=cid: self._borrar_cita(cita_id)
            )
            btn_del.pack(side="right", padx=10, pady=8)

    def _borrar_cita(self, cita_id):
        eliminar_cita(cita_id=cita_id)
        self._cargar_citas()

    def _guardar_cita(self):
        cedula = self.entry_cedula.get().strip().replace(" ", "")
        nombre = self.entry_nombre.get().strip()
        tel = self.entry_tel.get().strip()
        fecha_str = self.entry_fecha.get().strip()
        desc = self.entry_desc.get().strip() or "Consulta Odontológica"

        if not nombre or not fecha_str:
            self.lbl_mensaje.configure(text="⚠️ Nombre y fecha son obligatorios", text_color="#f87171")
            return

        # Registrar o actualizar paciente con cédula
        if cedula:
            registrar_o_actualizar_paciente({
                "nombre": nombre,
                "documento": cedula,
                "contacto_emergencia": tel
            })

        try:
            agendar_cita(nombre, tel, fecha_str, duracion_minutos=30, descripcion=desc)
            self.lbl_mensaje.configure(text="✅ Cita agendada y sincronizada", text_color=self.theme["aqua"])
            self.entry_cedula.delete(0, "end")
            self.entry_nombre.delete(0, "end")
            self.entry_tel.delete(0, "end")
            self.entry_desc.delete(0, "end")
            self.lbl_paciente_detectado.configure(text="")
            self._cargar_citas()
        except Exception as e:
            self.lbl_mensaje.configure(text=f"Error: {e}", text_color="#f87171")
