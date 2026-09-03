import os
import re
import datetime
import customtkinter as ctk
from database import listar_pacientes_por_fecha, listar_consultas_paciente, eliminar_paciente_db, eliminar_consulta_db, listar_citas_paciente
from config import (
    COLOR_BG_DARK, COLOR_CARD_DARK, COLOR_AZUL_ACERO, COLOR_AZUL_PASTEL,
    COLOR_AQUA, COLOR_BORDER, COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED,
    CORNER_RADIUS_CARD, CORNER_RADIUS_BTN, RUTA_PACIENTES,
    abrir_archivo_o_carpeta_nativo
)
from export_excel import exportar_a_excel
from ui.pdf_preview_modal import VentanaVistaPreviaPDF
from ui.animations import bind_hover_microscale, animar_despliegue_tarjeta

class PatientsView(ctk.CTkFrame):
    def __init__(self, master):
        from config import obtener_tema_activo_dict
        self.theme = obtener_tema_activo_dict()
        super().__init__(master, fg_color="transparent")
        self.paciente_seleccionado = None
        self.fecha_filtro = datetime.date.today().isoformat()
        self._build_ui()
        self._cargar_pacientes()

    def _build_ui(self):
        t = self.theme

        # Header Superior Pulido con Esquinas Redondeadas
        top_bar = ctk.CTkFrame(self, fg_color=t["card_dark"], height=68, corner_radius=t["corner_radius"], border_width=1, border_color=t["border"])
        top_bar.pack(fill="x", padx=16, pady=(12, 8))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(top_bar, text="👥 Directorio & Archivo Seccionado", font=("Segoe UI", 16, "bold"), text_color=t["text_primary"]).pack(side="left", padx=16)

        btn_abrir_explorador = ctk.CTkButton(
            top_bar, text="📁 Carpeta Física", width=125, height=36, font=("Segoe UI", 11, "bold"),
            fg_color="#334155", hover_color="#475569", corner_radius=t["corner_btn"], command=self._abrir_raiz_pacientes
        )
        btn_abrir_explorador.pack(side="right", padx=(6, 16))

        btn_excel = ctk.CTkButton(
            top_bar, text="📊 Exportar Excel", width=125, height=36, font=("Segoe UI", 11, "bold"),
            fg_color=t["azul_acero"], hover_color=t["azul_pastel"], corner_radius=t["corner_btn"], command=self._generar_excel
        )
        btn_excel.pack(side="right", padx=(6, 6))

        self.entry_busqueda = ctk.CTkEntry(
            top_bar, width=240, height=36, corner_radius=10, placeholder_text="🔍 Buscar nombre o cédula...",
            font=("Segoe UI", 11), fg_color=t["input_bg"], border_color=t["input_border"], text_color=t["text_primary"]
        )
        self.entry_busqueda.pack(side="right", padx=(0, 6))
        self.entry_busqueda.bind("<KeyRelease>", lambda e: self._cargar_pacientes())

        # Barra de Filtro Temporal (Pacientes de Hoy y 5 Días Previos)
        bar_fechas = ctk.CTkFrame(self, fg_color=t["card_dark"], height=46, corner_radius=t["corner_radius"], border_width=1, border_color=t["border"])
        bar_fechas.pack(fill="x", padx=16, pady=(0, 10))
        bar_fechas.pack_propagate(False)

        self.lbl_fecha_titulo = ctk.CTkLabel(bar_fechas, text="", font=("Segoe UI", 11, "bold"), text_color=t["aqua"])
        self.lbl_fecha_titulo.pack(side="left", padx=16)

        scroll_chips = ctk.CTkFrame(bar_fechas, fg_color="transparent")
        scroll_chips.pack(side="right", padx=10)

        # Generar chips: Hoy, Ayer, -2d, -3d, -4d, -5d, Todos
        hoy = datetime.date.today()
        self.chips_btns = []
        opciones_fecha = [
            ("📅 Hoy", hoy.isoformat()),
            ("Ayer", (hoy - datetime.timedelta(days=1)).isoformat()),
            ("-2 días", (hoy - datetime.timedelta(days=2)).isoformat()),
            ("-3 días", (hoy - datetime.timedelta(days=3)).isoformat()),
            ("-4 días", (hoy - datetime.timedelta(days=4)).isoformat()),
            ("-5 días", (hoy - datetime.timedelta(days=5)).isoformat()),
            ("📁 Todos", "todos")
        ]

        for label, f_iso in opciones_fecha:
            btn_chip = ctk.CTkButton(
                scroll_chips, text=label, width=68, height=28, font=("Segoe UI", 10, "bold"),
                fg_color=t["azul_acero"] if f_iso == self.fecha_filtro else "transparent",
                hover_color=t["card_hover"] if "card_hover" in t else "#374151",
                text_color="#ffffff" if f_iso == self.fecha_filtro else t["text_muted"],
                corner_radius=8,
                command=lambda val=f_iso, b_label=label: self._seleccionar_filtro_fecha(val, b_label)
            )
            btn_chip.pack(side="left", padx=3)
            self.chips_btns.append((btn_chip, f_iso))

        # Contenedor principal de dos paneles
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # Panel Izquierdo: Lista de Pacientes
        self.panel_pacientes = ctk.CTkScrollableFrame(content, fg_color=t["card_dark"], corner_radius=t["corner_radius"], border_width=1, border_color=t["border"], width=460)
        self.panel_pacientes.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # Panel Derecho: Historial y Detalles de Consultas
        self.panel_detalles = ctk.CTkScrollableFrame(content, fg_color=t["card_dark"], corner_radius=t["corner_radius"], border_width=1, border_color=t["border"])
        self.panel_detalles.pack(side="right", fill="both", expand=True)

        ctk.CTkLabel(self.panel_detalles, text="Selecciona un paciente para ver sus historias clínicas", font=("Segoe UI", 12), text_color=t["text_muted"]).pack(pady=40)
        self._actualizar_titulo_fecha()

    def _seleccionar_filtro_fecha(self, fecha_iso, label):
        self.fecha_filtro = fecha_iso
        t = self.theme
        for btn, f_val in self.chips_btns:
            if f_val == fecha_iso:
                btn.configure(fg_color=t["azul_acero"], text_color="#ffffff")
            else:
                btn.configure(fg_color="transparent", text_color=t["text_muted"])
        self._actualizar_titulo_fecha()
        self._cargar_pacientes()

    def _actualizar_titulo_fecha(self):
        hoy = datetime.date.today().isoformat()
        if self.fecha_filtro == hoy:
            d_str = datetime.date.today().strftime("%A %d de %B, %Y").capitalize()
            self.lbl_fecha_titulo.configure(text=f"📌 Pacientes de Hoy: {d_str}")
        elif self.fecha_filtro == "todos":
            self.lbl_fecha_titulo.configure(text="📁 Todos los Pacientes Registrados")
        else:
            self.lbl_fecha_titulo.configure(text=f"📅 Pacientes del {self.fecha_filtro}")

    def _cargar_pacientes(self):
        t = self.theme
        for widget in self.panel_pacientes.winfo_children():
            widget.destroy()

        query = self.entry_busqueda.get()
        pacientes = listar_pacientes_por_fecha(self.fecha_filtro, query)

        if not pacientes:
            txt_vacio = "No hay pacientes registrados para esta fecha." if self.fecha_filtro != "todos" else "No se encontraron pacientes."
            ctk.CTkLabel(self.panel_pacientes, text=txt_vacio, font=("Segoe UI", 11), text_color=t["text_muted"]).pack(pady=30)
            return

        for p in pacientes:
            card = ctk.CTkFrame(self.panel_pacientes, fg_color=t["bg_dark"], corner_radius=12, border_width=1, border_color=t["border"])
            card.pack(fill="x", padx=6, pady=4)

            nombre = p.get("nombre", "Paciente")
            doc = p.get("documento") or "Sin cédula"
            edad_num = p.get("edad", 0) or 0
            edad_str = f"{edad_num} años" if edad_num else "Edad N/E"
            categoria = "👶 Pediátrico" if edad_num < 18 else "🧑 Adulto"
            total_cons = p.get("total_consultas", 0)
            pac_id = p.get("id", 1)

            left_b = ctk.CTkFrame(card, fg_color="transparent")
            left_b.pack(side="left", padx=12, pady=8, fill="x", expand=True)

            ctk.CTkLabel(left_b, text=f"{nombre} (ID: {pac_id})", font=("Segoe UI", 12, "bold"), text_color=t["text_primary"], anchor="w").pack(fill="x")
            info_text = f"🆔 Cédula: {doc}  |  {edad_str}  |  {categoria}\n📋 Consultas archivadas: {total_cons}"
            ctk.CTkLabel(left_b, text=info_text, font=("Segoe UI", 10), text_color=t["text_muted"], justify="left", anchor="w").pack(fill="x", pady=(2, 0))

            btn_box = ctk.CTkFrame(card, fg_color="transparent")
            btn_box.pack(side="right", padx=10, pady=8)

            btn_ver = ctk.CTkButton(
                btn_box, text="Ver Historia", width=85, height=32, font=("Segoe UI", 11, "bold"),
                fg_color=t["azul_acero"], hover_color=t["azul_pastel"], corner_radius=8,
                command=lambda pac=p: self._mostrar_consultas(pac)
            )
            btn_ver.pack(side="left", padx=(0, 6))

            btn_del = ctk.CTkButton(
                btn_box, text="🗑️", width=32, height=32, font=("Segoe UI", 11),
                fg_color="transparent", hover_color="#dc2626", text_color="#ef4444",
                corner_radius=8, command=lambda pac_id=pac_id, nom=nombre, c=card: self._confirmar_eliminar_paciente(pac_id, nom, card_widget=c)
            )
            btn_del.pack(side="left")

    def _confirmar_eliminar_paciente(self, pac_id, nombre, card_widget=None):
        t = self.theme
        modal = ctk.CTkToplevel(self)
        modal.title("Confirmar Eliminación")
        modal.geometry("420x220")
        modal.resizable(False, False)
        modal.attributes("-topmost", True)
        modal.configure(fg_color=t["bg_dark"])

        ctk.CTkLabel(modal, text="⚠️ ¿ELIMINAR PACIENTE?", font=("Segoe UI", 14, "bold"), text_color="#ef4444").pack(pady=(20, 6))
        ctk.CTkLabel(modal, text=f"¿Estás seguro de que deseas eliminar permanentemente a:\n{nombre} (ID: {pac_id})?\nSe borrarán sus consultas y citas asociadas.", font=("Segoe UI", 11), text_color=t["text_muted"], justify="center").pack(pady=(0, 20))

        b_row = ctk.CTkFrame(modal, fg_color="transparent")
        b_row.pack()

        ctk.CTkButton(b_row, text="Cancelar", width=100, height=36, font=("Segoe UI", 11), fg_color="#334155", hover_color="#475569", command=modal.destroy).pack(side="left", padx=10)
        
        def ejecutar_borrado():
            try:
                eliminar_paciente_db(pac_id)
            except Exception as e:
                print(f"[ERROR BORRADO PACIENTE]: {e}")

            try:
                modal.destroy()
            except Exception:
                pass

            if card_widget and card_widget.winfo_exists():
                try:
                    card_widget.destroy()
                except Exception:
                    pass

            for w in self.panel_detalles.winfo_children():
                try:
                    w.destroy()
                except Exception:
                    pass

            ctk.CTkLabel(self.panel_detalles, text=f"✅ Paciente {nombre} y sus expedientes físicos eliminados permanentemente.", font=("Segoe UI", 12, "bold"), text_color=t["aqua"]).pack(pady=40)
            self._cargar_pacientes()

        ctk.CTkButton(b_row, text="Sí, Eliminar", width=120, height=36, font=("Segoe UI", 11, "bold"), fg_color="#dc2626", hover_color="#b91c1c", command=ejecutar_borrado).pack(side="left", padx=10)

    def _mostrar_consultas(self, paciente):
        t = self.theme
        self.paciente_seleccionado = paciente
        for widget in self.panel_detalles.winfo_children():
            widget.destroy()

        nombre = paciente.get("nombre", "")
        doc = paciente.get("documento", "No especificado")
        tel = paciente.get("telefono", "No especificado")
        edad_num = paciente.get("edad", 0) or 0
        pac_id = paciente.get("id", 1)
        categoria_txt = "Pacientes Pediátricos (Menor de edad)" if edad_num < 18 else "Pacientes Adultos"

        header_card = ctk.CTkFrame(self.panel_detalles, fg_color=t["bg_dark"], corner_radius=14, border_width=1, border_color=t["border"])
        header_card.pack(fill="x", padx=10, pady=(6, 12))

        top_row = ctk.CTkFrame(header_card, fg_color="transparent")
        top_row.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(top_row, text=f"📋 Historial Clínico: {nombre} (ID: {pac_id})", font=("Segoe UI", 14, "bold"), text_color=t["text_primary"]).pack(side="left")

        btn_carpeta = ctk.CTkButton(
            top_row, text="📂 Carpeta Windows", height=30, font=("Segoe UI", 10, "bold"),
            fg_color="#334155", hover_color="#475569", corner_radius=8,
            command=lambda: self._abrir_carpeta_paciente_especifica(paciente)
        )
        btn_carpeta.pack(side="right")

        btn_del_pac = ctk.CTkButton(
            top_row, text="🗑️ Eliminar Paciente", height=30, font=("Segoe UI", 10, "bold"),
            fg_color="transparent", hover_color="#dc2626", text_color="#ef4444", corner_radius=8,
            command=lambda pid=pac_id, nom=nombre: self._confirmar_eliminar_paciente(pid, nom)
        )
        btn_del_pac.pack(side="right", padx=(0, 6))

        meta_txt = f"Cédula: {doc}  |  Teléfono: {tel}  |  Sección: {categoria_txt}"
        ctk.CTkLabel(header_card, text=meta_txt, font=("Segoe UI", 10), text_color=t["text_muted"]).pack(anchor="w", padx=14, pady=(0, 10))

        # Citas agendadas asociadas a este paciente
        citas_pac = listar_citas_paciente(paciente_id=pac_id, nombre_paciente=nombre)
        if citas_pac:
            citas_card = ctk.CTkFrame(self.panel_detalles, fg_color=t["bg_dark"], corner_radius=12, border_width=1, border_color=t["border"])
            citas_card.pack(fill="x", padx=10, pady=(0, 10))

            top_c = ctk.CTkFrame(citas_card, fg_color="transparent")
            top_c.pack(fill="x", padx=14, pady=(8, 4))
            ctk.CTkLabel(top_c, text=f"📅 Citas Agendadas ({len(citas_pac)})", font=("Segoe UI", 11, "bold"), text_color=t["azul_pastel"]).pack(side="left")

            for ci in citas_pac:
                row_ci = ctk.CTkFrame(citas_card, fg_color="transparent")
                row_ci.pack(fill="x", padx=14, pady=3)
                f_ini = ci.get("fecha_hora_inicio", "")
                desc_ci = ci.get("descripcion", "Control clínico")
                est_ci = ci.get("estado", "programada").upper()
                ctk.CTkLabel(row_ci, text=f"• {f_ini}  —  {desc_ci}", font=("Segoe UI", 10), text_color=t["text_primary"]).pack(side="left")
                col_badge = t["aqua"] if est_ci == "CONFIRMADA" else t["text_muted"]
                ctk.CTkLabel(row_ci, text=f"[{est_ci}]", font=("Segoe UI", 9, "bold"), text_color=col_badge).pack(side="right")

        consultas = listar_consultas_paciente(paciente["id"])
        if not consultas and not citas_pac:
            ctk.CTkLabel(self.panel_detalles, text="Este paciente aún no tiene consultas ni citas registradas.", font=("Segoe UI", 11), text_color=t["text_muted"]).pack(pady=20)
            return

        for c in consultas:
            c_card = ctk.CTkFrame(self.panel_detalles, fg_color=t["bg_dark"], corner_radius=12, border_width=1, border_color=t["border"])
            c_card.pack(fill="x", padx=10, pady=5)

            fecha_c = c.get("fecha_hora", "")
            motivo = c.get("motivo_consulta", "Sin motivo")
            diag = c.get("diagnostico", "Sin diagnóstico")
            plan = c.get("plan_tratamiento", "Sin tratamiento")
            ruta_pdf = c.get("ruta_pdf")
            c_id = c.get("id")

            r_top = ctk.CTkFrame(c_card, fg_color="transparent")
            r_top.pack(fill="x", padx=12, pady=(8, 2))

            ctk.CTkLabel(r_top, text=f"🗓️ Consulta del {fecha_c}", font=("Segoe UI", 11, "bold"), text_color=t["aqua"]).pack(side="left")

            act_box = ctk.CTkFrame(r_top, fg_color="transparent")
            act_box.pack(side="right")

            if ruta_pdf and os.path.exists(ruta_pdf):
                ctk.CTkButton(
                    act_box, text="👁️ Vista Previa", width=88, height=26, font=("Segoe UI", 10, "bold"),
                    fg_color=t["aqua"], hover_color=t["azul_acero"], text_color="#ffffff", corner_radius=6,
                    command=lambda r=ruta_pdf: VentanaVistaPreviaPDF(self, r, t)
                ).pack(side="left", padx=(0, 4))
                ctk.CTkButton(
                    act_box, text="✏️ Corregir", width=75, height=26, font=("Segoe UI", 10, "bold"),
                    fg_color="#334155", hover_color="#475569", text_color="#ffffff", corner_radius=6,
                    command=lambda cons=c, r=ruta_pdf, pac=paciente: self._abrir_modal_correccion_paciente(cons, r, pac)
                ).pack(side="left", padx=(0, 4))
                ctk.CTkButton(
                    act_box, text="💵 Pagos", width=68, height=26, font=("Segoe UI", 10, "bold"),
                    fg_color=t.get("azul_acero", "#1e3a8a"), hover_color=t.get("azul_pastel", "#38bdf8"), text_color="#ffffff", corner_radius=6,
                    command=lambda cons=c, r=ruta_pdf, pac=paciente: self._abrir_modal_pagos_paciente(cons, r, pac)
                ).pack(side="left", padx=(0, 4))
                ctk.CTkButton(
                    act_box, text="↗ Abrir", width=65, height=26, font=("Segoe UI", 10, "bold"),
                    fg_color=t["azul_acero"], hover_color=t["azul_pastel"], corner_radius=6,
                    command=lambda r=ruta_pdf: abrir_archivo_o_carpeta_nativo(r)
                ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                act_box, text="🗑️", width=28, height=26, font=("Segoe UI", 10),
                fg_color="transparent", hover_color="#dc2626", text_color="#ef4444", corner_radius=6,
                command=lambda cid=c_id: self._confirmar_eliminar_consulta(cid, paciente)
            ).pack(side="left")

            txt_info = f"• Motivo: {motivo}\n• Diagnóstico: {diag}\n• Tratamiento: {plan}"
            ctk.CTkLabel(c_card, text=txt_info, font=("Segoe UI", 10), text_color=t["text_primary"], justify="left", anchor="w").pack(fill="x", padx=12, pady=(0, 4))

            # Franja de honorarios y estado de cuentas claras
            from database import obtener_pago_consulta
            pago_c = obtener_pago_consulta(c_id)
            if pago_c and (float(pago_c.get("costo_total") or 0) > 0 or float(pago_c.get("abono") or 0) > 0 or float(pago_c.get("saldo_pendiente") or 0) > 0):
                c_tot = float(pago_c.get("costo_total") or 0.0)
                c_ab = float(pago_c.get("abono") or 0.0)
                c_sal = float(pago_c.get("saldo_pendiente") or 0.0)
                if c_sal <= 0 and c_tot > 0:
                    txt_b = "✅ Saldo Cancelado ($0.00)"
                    col_b = "#10b981"
                    bg_b = "#064e3b" if t["mode"] == "dark" else "#d1fae5"
                else:
                    txt_b = f"⚠️ Saldo Restante: ${c_sal:.2f}"
                    col_b = "#fbbf24"
                    bg_b = "#451a03" if t["mode"] == "dark" else "#fef3c7"

                row_p_info = ctk.CTkFrame(c_card, fg_color="transparent")
                row_p_info.pack(fill="x", padx=12, pady=(0, 6))

                lbl_fin = f"💳 Costo: ${c_tot:.2f}  |  Abono: ${c_ab:.2f}  |  Saldo: ${c_sal:.2f}"
                ctk.CTkLabel(row_p_info, text=lbl_fin, font=("Segoe UI", 9, "bold"), text_color=t["aqua"]).pack(side="left")
                ctk.CTkLabel(row_p_info, text=txt_b, font=("Segoe UI", 9, "bold"), text_color=col_b, fg_color=bg_b, corner_radius=6, padx=6, pady=1).pack(side="right")

    def _abrir_modal_pagos_paciente(self, c, ruta_pdf, paciente):
        from ui.payment_modal import VentanaPagosModal
        import json

        json_str = c.get("json_clinico", "{}")
        try:
            datos = json.loads(json_str) if isinstance(json_str, str) else json_str
        except Exception:
            datos = {}

        VentanaPagosModal(
            self,
            datos_consulta=datos,
            paciente_id=paciente["id"],
            consulta_id=c.get("id"),
            ruta_pdf=ruta_pdf,
            on_update_callback=lambda d_up, r_up: self.after(0, lambda: self._seleccionar_paciente(paciente)),
            theme=self.theme
        )

    def _confirmar_eliminar_consulta(self, c_id, paciente):
        t = self.theme
        modal = ctk.CTkToplevel(self)
        modal.title("Eliminar Consulta")
        modal.geometry("380x180")
        modal.resizable(False, False)
        modal.attributes("-topmost", True)
        modal.configure(fg_color=t["bg_dark"])

        ctk.CTkLabel(modal, text="⚠️ ¿ELIMINAR ESTA CONSULTA?", font=("Segoe UI", 12, "bold"), text_color="#ef4444").pack(pady=(18, 4))
        ctk.CTkLabel(modal, text="Se eliminará la consulta y su archivo PDF.", font=("Segoe UI", 10), text_color=t["text_muted"]).pack(pady=(0, 16))

        b_row = ctk.CTkFrame(modal, fg_color="transparent")
        b_row.pack()

        ctk.CTkButton(b_row, text="Cancelar", width=90, height=32, font=("Segoe UI", 11), fg_color="#334155", hover_color="#475569", command=modal.destroy).pack(side="left", padx=8)

        def borrar():
            eliminar_consulta_db(c_id)
            modal.destroy()
            self._mostrar_consultas(paciente)
            self._cargar_pacientes()

        ctk.CTkButton(b_row, text="Sí, Eliminar", width=110, height=32, font=("Segoe UI", 11, "bold"), fg_color="#dc2626", hover_color="#b91c1c", command=borrar).pack(side="left", padx=8)

    def _abrir_raiz_pacientes(self):
        os.makedirs(RUTA_PACIENTES, exist_ok=True)
        abrir_archivo_o_carpeta_nativo(RUTA_PACIENTES)

    def _abrir_carpeta_paciente_especifica(self, paciente):
        nombre_paciente = paciente.get('nombre', 'Paciente')
        nombre_limpio_carpeta = re.sub(r'[^a-zA-Z0-9_]', '', nombre_paciente.replace(' ', '_')) or "Paciente"
        edad_num = paciente.get('edad', 0) or 18
        categoria_edad = "Pacientes_Pediatricos" if edad_num < 18 else "Pacientes_Adultos"
        nombre_carpeta = f"{nombre_limpio_carpeta}_{edad_num}_anos_ID{paciente['id']}"
        ruta_carpeta = os.path.join(RUTA_PACIENTES, categoria_edad, nombre_carpeta)
        os.makedirs(ruta_carpeta, exist_ok=True)
        abrir_archivo_o_carpeta_nativo(ruta_carpeta)

    def _generar_excel(self):
        try:
            ruta_excel = exportar_a_excel()
            abrir_archivo_o_carpeta_nativo(ruta_excel)
        except Exception as e:
            print(f"Error al generar Excel: {e}")

    def _abrir_modal_correccion_paciente(self, consulta, ruta_pdf, paciente):
        from ui.correction_modal import VentanaCorreccionExpediente
        from generador_pdf import crear_historia_clinica
        from database import actualizar_consulta_existente, registrar_o_actualizar_paciente
        import json

        json_str = consulta.get("json_clinico", "{}")
        try:
            datos = json.loads(json_str) if isinstance(json_str, str) else json_str
        except Exception:
            datos = {}

        if not isinstance(datos, dict) or not datos:
            datos = {
                "datos_filiacion": {
                    "nombre": paciente.get("nombre", ""),
                    "documento": paciente.get("documento", ""),
                    "edad": paciente.get("edad", ""),
                    "sexo": paciente.get("sexo", "")
                },
                "motivo_consulta": consulta.get("motivo_consulta", ""),
                "diagnostico": consulta.get("diagnostico", ""),
                "plan_tratamiento": consulta.get("plan_tratamiento", ""),
                "odontograma": []
            }

        def al_guardar(datos_nuevos):
            try:
                # 1. Actualizar datos de filiación del paciente
                fil_nueva = datos_nuevos.get("datos_filiacion", {})
                fil_nueva["id"] = paciente["id"]
                registrar_o_actualizar_paciente(fil_nueva)

                # 2. Compilar nuevo PDF
                nueva_ruta = crear_historia_clinica(datos_nuevos, paciente_id=paciente["id"])

                # 3. Eliminar PDF antiguo para evitar duplicados
                if ruta_pdf and os.path.exists(ruta_pdf) and os.path.abspath(ruta_pdf) != os.path.abspath(nueva_ruta):
                    try:
                        os.remove(ruta_pdf)
                        print(f"[ARCHIVO CORRECCION] PDF previo eliminado con éxito: {ruta_pdf}")
                    except Exception as e_del:
                        print(f"[ARCHIVO CORRECCION] Advertencia al borrar previo: {e_del}")

                # 4. Actualizar consulta en SQLite
                actualizar_consulta_existente(consulta["id"], datos_nuevos, ruta_pdf=nueva_ruta)

                # 5. Refrescar interfaz
                self._cargar_pacientes()
                paciente_actualizado = dict(paciente)
                paciente_actualizado.update(fil_nueva)
                self._cargar_detalles_paciente(paciente_actualizado)
            except Exception as err_c:
                print(f"[ERROR CORREGIR PACIENTE] {err_c}")

        VentanaCorreccionExpediente(self, datos, ruta_pdf, paciente_id=paciente["id"], on_save_callback=al_guardar)
