import os
import json
import customtkinter as ctk
from database import registrar_o_actualizar_pago_db, obtener_pago_consulta, get_connection
from generador_pdf import crear_historia_clinica

class VentanaPagosModal(ctk.CTkToplevel):
    """
    Ventanita interactiva ejecutiva para el registro y consulta de pagos,
    abonos y saldo restante / cancelado del paciente.
    """
    def __init__(self, parent, datos_consulta: dict, paciente_id: int, consulta_id: int = None, ruta_pdf: str = None, on_update_callback = None, theme: dict = None):
        super().__init__(parent)
        self.datos = datos_consulta if isinstance(datos_consulta, dict) else {}
        self.paciente_id = paciente_id
        self.consulta_id = consulta_id
        self.ruta_pdf = ruta_pdf
        self.on_update_callback = on_update_callback

        from config import obtener_tema_activo_dict
        self.theme = theme or obtener_tema_activo_dict()
        t = self.theme

        self.title("Control de Pagos y Cuentas Claras")
        self.geometry("480x540")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.configure(fg_color=t.get("bg_dark", "#0f172a"))

        # Extraer datos actuales
        fil = self.datos.get("datos_filiacion", {})
        self.nom_paciente = fil.get("nombre", "Paciente")
        self.doc_paciente = fil.get("documento", "No especificado")
        
        pagos_actuales = self.datos.get("pagos", {})
        if not pagos_actuales and self.consulta_id:
            db_pago = obtener_pago_consulta(self.consulta_id)
            if db_pago:
                pagos_actuales = db_pago

        self.costo_inicial = float(pagos_actuales.get("costo_total") or 0.0)
        self.abono_inicial = float(pagos_actuales.get("abono") or 0.0)
        self.saldo_inicial = float(pagos_actuales.get("saldo_pendiente") if pagos_actuales.get("saldo_pendiente") is not None else max(0.0, round(self.costo_inicial - self.abono_inicial, 2)))
        self.metodo_inicial = str(pagos_actuales.get("metodo_pago") or "Efectivo")
        self.notas_iniciales = str(pagos_actuales.get("notas") or "")

        self._build_ui()

    def _build_ui(self):
        t = self.theme

        # 1. Cabecera Ejecutiva
        head_frame = ctk.CTkFrame(self, fg_color=t.get("card_dark", "#1e293b"), height=72, corner_radius=12, border_width=1, border_color=t.get("border", "#334155"))
        head_frame.pack(fill="x", padx=16, pady=(16, 12))
        head_frame.pack_propagate(False)

        top_r = ctk.CTkFrame(head_frame, fg_color="transparent")
        top_r.pack(fill="x", padx=14, pady=(10, 2))
        ctk.CTkLabel(top_r, text="💳 CONTROL DE PAGOS Y HONORARIOS", font=("Segoe UI", 11, "bold"), text_color=t.get("aqua", "#06b6d4")).pack(side="left")

        sub_txt = f"Paciente: {self.nom_paciente}   |   C.I.: {self.doc_paciente}"
        ctk.CTkLabel(head_frame, text=sub_txt, font=("Segoe UI", 10), text_color=t.get("text_muted", "#94a3b8")).pack(anchor="w", padx=14, pady=(0, 8))

        # 2. Tarjeta Reactiva de Estado Financiero en Vivo (Saldo Cancelado / Saldo Restante)
        self.card_estado = ctk.CTkFrame(self, fg_color="#064e3b" if self.saldo_inicial <= 0 and self.costo_inicial > 0 else "#451a03", corner_radius=14, border_width=1.5, border_color=t.get("aqua", "#06b6d4"))
        self.card_estado.pack(fill="x", padx=16, pady=(0, 14))

        self.lbl_estado_titulo = ctk.CTkLabel(
            self.card_estado,
            text="✅ SALDO CANCELADO" if self.saldo_inicial <= 0 and self.costo_inicial > 0 else (f"⚠️ SALDO RESTANTE: ${self.saldo_inicial:.2f}" if self.saldo_inicial > 0 else "● CUENTAS AL DIA"),
            font=("Segoe UI", 15, "bold"),
            text_color="#10b981" if self.saldo_inicial <= 0 and self.costo_inicial > 0 else ("#fbbf24" if self.saldo_inicial > 0 else "#94a3b8")
        )
        self.lbl_estado_titulo.pack(pady=(12, 2))

        self.lbl_estado_sub = ctk.CTkLabel(
            self.card_estado,
            text=f"Costo: ${self.costo_inicial:.2f}   |   Abonado: ${self.abono_inicial:.2f}   |   Restante: ${self.saldo_inicial:.2f}",
            font=("Segoe UI", 10, "bold"),
            text_color="#ffffff"
        )
        self.lbl_estado_sub.pack(pady=(0, 12))

        # 3. Formulario de Entrada
        form_frame = ctk.CTkFrame(self, fg_color=t.get("card_dark", "#1e293b"), corner_radius=12, border_width=1, border_color=t.get("border", "#334155"))
        form_frame.pack(fill="x", padx=16, pady=(0, 16))

        # Fila Costo Total
        r1 = ctk.CTkFrame(form_frame, fg_color="transparent")
        r1.pack(fill="x", padx=14, pady=(12, 6))
        ctk.CTkLabel(r1, text="Costo del Tratamiento ($):", font=("Segoe UI", 11, "bold"), text_color=t.get("text_primary", "#ffffff"), width=170, anchor="w").pack(side="left")
        self.ent_costo = ctk.CTkEntry(r1, width=220, height=32, font=("Segoe UI", 11, "bold"), fg_color=t.get("input_bg", "#0f172a"), border_color=t.get("input_border", "#334155"), text_color=t.get("text_primary", "#ffffff"))
        self.ent_costo.pack(side="right")
        self.ent_costo.insert(0, f"{self.costo_inicial:.2f}" if self.costo_inicial > 0 else "")
        self.ent_costo.bind("<KeyRelease>", self._recalcular_en_vivo)

        # Fila Abono Realizado
        r2 = ctk.CTkFrame(form_frame, fg_color="transparent")
        r2.pack(fill="x", padx=14, pady=(6, 6))
        ctk.CTkLabel(r2, text="Abono / Pago Realizado ($):", font=("Segoe UI", 11, "bold"), text_color=t.get("text_primary", "#ffffff"), width=170, anchor="w").pack(side="left")
        self.ent_abono = ctk.CTkEntry(r2, width=220, height=32, font=("Segoe UI", 11, "bold"), fg_color=t.get("input_bg", "#0f172a"), border_color=t.get("input_border", "#334155"), text_color=t.get("text_primary", "#ffffff"))
        self.ent_abono.pack(side="right")
        self.ent_abono.insert(0, f"{self.abono_inicial:.2f}" if self.abono_inicial > 0 else "")
        self.ent_abono.bind("<KeyRelease>", self._recalcular_en_vivo)

        # Fila Método de Pago
        r3 = ctk.CTkFrame(form_frame, fg_color="transparent")
        r3.pack(fill="x", padx=14, pady=(6, 6))
        ctk.CTkLabel(r3, text="Método de Pago:", font=("Segoe UI", 11, "bold"), text_color=t.get("text_primary", "#ffffff"), width=170, anchor="w").pack(side="left")
        opciones_metodo = ["Efectivo", "Transferencia Bancaria", "Tarjeta de Débito", "Tarjeta de Crédito", "Otro"]
        metodo_def = self.metodo_inicial if self.metodo_inicial in opciones_metodo else "Efectivo"
        self.opt_metodo = ctk.CTkOptionMenu(r3, values=opciones_metodo, width=220, height=32, font=("Segoe UI", 11, "bold"), fg_color=t.get("azul_acero", "#1e3a8a"), button_color=t.get("azul_pastel", "#38bdf8"), text_color="#ffffff")
        self.opt_metodo.pack(side="right")
        self.opt_metodo.set(metodo_def)

        # Fila Notas / Observaciones
        r4 = ctk.CTkFrame(form_frame, fg_color="transparent")
        r4.pack(fill="x", padx=14, pady=(6, 14))
        ctk.CTkLabel(r4, text="Concepto / Observaciones:", font=("Segoe UI", 11, "bold"), text_color=t.get("text_primary", "#ffffff"), width=170, anchor="w").pack(side="left")
        self.ent_notas = ctk.CTkEntry(r4, width=220, height=32, placeholder_text="Ej: Abono de ortodoncia", font=("Segoe UI", 10), fg_color=t.get("input_bg", "#0f172a"), border_color=t.get("input_border", "#334155"), text_color=t.get("text_primary", "#ffffff"))
        self.ent_notas.pack(side="right")
        if self.notas_iniciales:
            self.ent_notas.insert(0, self.notas_iniciales)

        # 4. Botones de Acción
        btn_bar = ctk.CTkFrame(self, fg_color="transparent")
        btn_bar.pack(fill="x", padx=16, pady=(0, 16))

        btn_guardar = ctk.CTkButton(
            btn_bar,
            text="💾 Guardar y Actualizar PDF",
            height=40,
            font=("Segoe UI", 11, "bold"),
            fg_color=t.get("aqua", "#06b6d4"),
            hover_color=t.get("azul_acero", "#1e3a8a"),
            text_color="#ffffff",
            corner_radius=10,
            command=self._guardar_pago
        )
        btn_guardar.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_cancelar = ctk.CTkButton(
            btn_bar,
            text="Cerrar",
            width=90,
            height=40,
            font=("Segoe UI", 11, "bold"),
            fg_color="#334155",
            hover_color="#475569",
            text_color="#ffffff",
            corner_radius=10,
            command=self.destroy
        )
        btn_cancelar.pack(side="right")

        self._recalcular_en_vivo()

    def _recalcular_en_vivo(self, event=None):
        """Calcula dinámicamente el saldo y actualiza la tarjeta de estado con colores vivos."""
        c_str = self.ent_costo.get().strip().replace(",", ".")
        a_str = self.ent_abono.get().strip().replace(",", ".")

        try:
            costo = float(c_str) if c_str else 0.0
        except ValueError:
            costo = 0.0

        try:
            abono = float(a_str) if a_str else 0.0
        except ValueError:
            abono = 0.0

        saldo = max(0.0, round(costo - abono, 2))

        if costo > 0 and saldo <= 0:
            self.card_estado.configure(fg_color="#064e3b", border_color="#10b981")
            self.lbl_estado_titulo.configure(text="✅ SALDO CANCELADO (Totalmente pagado)", text_color="#34d399")
        elif saldo > 0:
            self.card_estado.configure(fg_color="#451a03", border_color="#f59e0b")
            self.lbl_estado_titulo.configure(text=f"⚠️ SALDO RESTANTE: ${saldo:.2f}", text_color="#fbbf24")
        else:
            self.card_estado.configure(fg_color="#1e293b", border_color="#64748b")
            self.lbl_estado_titulo.configure(text="● CUENTAS AL DIA", text_color="#94a3b8")

        self.lbl_estado_sub.configure(text=f"Costo: ${costo:.2f}   |   Abonado: ${abono:.2f}   |   Restante: ${saldo:.2f}")

    def _guardar_pago(self):
        """Persiste el pago en SQLite, actualiza el JSON clínico, regenera el PDF y refresca la UI."""
        c_str = self.ent_costo.get().strip().replace(",", ".")
        a_str = self.ent_abono.get().strip().replace(",", ".")
        metodo = self.opt_metodo.get()
        notas = self.ent_notas.get().strip()

        try:
            costo = float(c_str) if c_str else 0.0
        except ValueError:
            costo = 0.0

        try:
            abono = float(a_str) if a_str else 0.0
        except ValueError:
            abono = 0.0

        saldo = max(0.0, round(costo - abono, 2))
        estado = "Cancelado" if (costo > 0 and saldo <= 0) else ("Saldo Pendiente" if saldo > 0 else "Cancelado")

        pagos_dict = {
            "costo_total": costo,
            "abono": abono,
            "saldo_pendiente": saldo,
            "estado": estado,
            "metodo_pago": metodo,
            "notas": notas
        }
        self.datos["pagos"] = pagos_dict

        registrar_o_actualizar_pago_db(
            paciente_id=self.paciente_id,
            consulta_id=self.consulta_id,
            costo_total=costo,
            abono=abono,
            saldo_pendiente=saldo,
            estado=estado,
            metodo_pago=metodo,
            notas=notas
        )

        if self.consulta_id:
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE consultas SET json_clinico = ? WHERE id = ?", (json.dumps(self.datos, ensure_ascii=False), self.consulta_id))
                conn.commit()

            if self.ruta_pdf and os.path.exists(self.ruta_pdf):
                try:
                    os.remove(self.ruta_pdf)
                    print(f"[PAGOS] PDF previo eliminado: {self.ruta_pdf}")
                except Exception as e:
                    print(f"[PAGOS] Error al eliminar PDF: {e}")

            nuevo_pdf = crear_historia_clinica(self.datos, paciente_id=self.paciente_id)
            if nuevo_pdf and os.path.exists(nuevo_pdf):
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE consultas SET ruta_pdf = ? WHERE id = ?", (nuevo_pdf, self.consulta_id))
                    conn.commit()
                self.ruta_pdf = nuevo_pdf
        else:
            nuevo_pdf = crear_historia_clinica(self.datos, paciente_id=self.paciente_id)
            self.ruta_pdf = nuevo_pdf

        if self.on_update_callback:
            try:
                self.on_update_callback(self.datos, self.ruta_pdf)
            except Exception as e_cb:
                print(f"[PAGOS] Error en callback: {e_cb}")

        self.destroy()
