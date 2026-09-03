import os
import customtkinter as ctk
from config import obtener_tema_activo_dict

class VentanaCorreccionExpediente(ctk.CTkToplevel):
    """
    Modal interactivo para corregir cualquier dato dictado por error
    (Nombre, Cédula, Edad, Diagnóstico, Plan) en 1 solo clic y regenerar
    el PDF inmediatamente eliminando la versión anterior.
    """
    def __init__(self, master, datos_consulta: dict, ruta_pdf_actual: str, paciente_id: int, theme: dict = None, on_guardar=None):
        super().__init__(master)
        self.datos = datos_consulta
        self.ruta_pdf_actual = ruta_pdf_actual
        self.paciente_id = paciente_id
        self.theme = theme or obtener_tema_activo_dict()
        self.on_guardar = on_guardar

        self.title("✏️ Corregir Datos de la Consulta")
        self.geometry("540x680")
        self.minsize(480, 560)
        self.attributes("-topmost", True)
        self.configure(fg_color=self.theme["bg_dark"])

        self._build_ui()

    def _build_ui(self):
        t = self.theme
        filiacion = self.datos.get("datos_filiacion", {})

        # Header
        top = ctk.CTkFrame(self, fg_color=t["card_dark"], height=60, corner_radius=12, border_width=1, border_color=t["border"])
        top.pack(fill="x", padx=16, pady=(14, 8))
        top.pack_propagate(False)

        ctk.CTkLabel(
            top, text="✏️ CORRECCIÓN RÁPIDA DE EXPEDIENTE",
            font=("Segoe UI", 14, "bold"), text_color=t["aqua"]
        ).pack(side="left", padx=16)

        scroll = ctk.CTkScrollableFrame(self, fg_color=t["card_dark"], corner_radius=12, border_width=1, border_color=t["border"])
        scroll.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        ctk.CTkLabel(
            scroll,
            text="Modifica los campos necesarios. Al guardar, se actualizará la base de datos\n"
                 "y se regenerará el PDF eliminando de forma definitiva el documento anterior.",
            font=("Segoe UI", 10), text_color=t["text_muted"], justify="left"
        ).pack(anchor="w", padx=16, pady=(10, 14))

        # Campo: Nombre
        ctk.CTkLabel(scroll, text="Nombre del Paciente:", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"]).pack(anchor="w", padx=16, pady=(4, 2))
        self.ent_nombre = ctk.CTkEntry(scroll, height=36, font=("Segoe UI", 12))
        self.ent_nombre.insert(0, filiacion.get("nombre", ""))
        self.ent_nombre.pack(fill="x", padx=16, pady=(0, 8))

        # Campo: Cédula y Edad en una fila
        row_num = ctk.CTkFrame(scroll, fg_color="transparent")
        row_num.pack(fill="x", padx=16, pady=(0, 8))

        col_ced = ctk.CTkFrame(row_num, fg_color="transparent")
        col_ced.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ctk.CTkLabel(col_ced, text="Cédula / Documento:", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"]).pack(anchor="w", pady=(0, 2))
        self.ent_cedula = ctk.CTkEntry(col_ced, height=36, font=("Segoe UI", 12))
        self.ent_cedula.insert(0, str(filiacion.get("documento", "") if filiacion.get("documento") != "No especificado" else ""))
        self.ent_cedula.pack(fill="x")

        col_edad = ctk.CTkFrame(row_num, fg_color="transparent")
        col_edad.pack(side="right", fill="x", expand=True, padx=(6, 0))
        ctk.CTkLabel(col_edad, text="Edad (Años):", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"]).pack(anchor="w", pady=(0, 2))
        self.ent_edad = ctk.CTkEntry(col_edad, height=36, font=("Segoe UI", 12))
        self.ent_edad.insert(0, str(filiacion.get("edad", "") if filiacion.get("edad") not in (None, "No especificado") else ""))
        self.ent_edad.pack(fill="x")

        # Campo: Motivo de Consulta
        ctk.CTkLabel(scroll, text="Motivo de la Consulta:", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"]).pack(anchor="w", padx=16, pady=(4, 2))
        self.ent_motivo = ctk.CTkEntry(scroll, height=36, font=("Segoe UI", 12))
        self.ent_motivo.insert(0, self.datos.get("motivo_consulta", ""))
        self.ent_motivo.pack(fill="x", padx=16, pady=(0, 8))

        # Campo: Diagnóstico Definitivo
        ctk.CTkLabel(scroll, text="Diagnóstico Definitivo:", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"]).pack(anchor="w", padx=16, pady=(4, 2))
        self.ent_diagnostico = ctk.CTkEntry(scroll, height=36, font=("Segoe UI", 12))
        self.ent_diagnostico.insert(0, self.datos.get("diagnostico", ""))
        self.ent_diagnostico.pack(fill="x", padx=16, pady=(0, 8))

        # Campo: Plan de Tratamiento
        ctk.CTkLabel(scroll, text="Plan de Tratamiento:", font=("Segoe UI", 11, "bold"), text_color=t["text_primary"]).pack(anchor="w", padx=16, pady=(4, 2))
        self.ent_plan = ctk.CTkEntry(scroll, height=36, font=("Segoe UI", 12))
        self.ent_plan.insert(0, self.datos.get("plan_tratamiento", ""))
        self.ent_plan.pack(fill="x", padx=16, pady=(0, 14))

        # Barra Inferior con Botones
        bot = ctk.CTkFrame(self, fg_color=t["card_dark"], height=62, corner_radius=12, border_width=1, border_color=t["border"])
        bot.pack(fill="x", padx=16, pady=(0, 14))
        bot.pack_propagate(False)

        btn_cancel = ctk.CTkButton(
            bot, text="Cancelar", width=110, height=38,
            font=("Segoe UI", 11), fg_color="#334155", hover_color="#475569",
            corner_radius=8, command=self.destroy
        )
        btn_cancel.pack(side="left", padx=16)

        btn_guardar = ctk.CTkButton(
            bot, text="💾 Guardar y Regenerar PDF Definitivo", height=38,
            font=("Segoe UI", 12, "bold"), fg_color=t["aqua"], hover_color=t["azul_acero"],
            text_color="#ffffff", corner_radius=8, command=self._ejecutar_guardado
        )
        btn_guardar.pack(side="right", padx=16)

    def _ejecutar_guardado(self):
        nuevo_nom = self.ent_nombre.get().strip() or "Paciente_Consulta"
        nueva_ced = self.ent_cedula.get().strip()
        nueva_edad_str = self.ent_edad.get().strip()
        nuevo_motivo = self.ent_motivo.get().strip()
        nuevo_diag = self.ent_diagnostico.get().strip()
        nuevo_plan = self.ent_plan.get().strip()

        try:
            nueva_edad = int(nueva_edad_str) if nueva_edad_str.isdigit() else None
        except Exception:
            nueva_edad = None

        # Actualizar estructuras internas
        fil = self.datos.setdefault("datos_filiacion", {})
        fil["nombre"] = nuevo_nom
        fil["documento"] = nueva_ced or "No especificado"
        fil["edad"] = nueva_edad

        self.datos["motivo_consulta"] = nuevo_motivo
        self.datos["diagnostico"] = nuevo_diag
        self.datos["plan_tratamiento"] = nuevo_plan

        if self.on_guardar:
            self.on_guardar(self.datos, fil, self.ruta_pdf_actual, self.paciente_id)

        self.destroy()
