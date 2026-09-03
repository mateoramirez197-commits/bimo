import os
import fitz  # PyMuPDF
from PIL import Image
import customtkinter as ctk
from config import abrir_archivo_o_carpeta_nativo, obtener_tema_activo_dict

class VentanaVistaPreviaPDF(ctk.CTkToplevel):
    """
    Visor interactivo nativo de PDFs de alta fidelidad integrado en BIMO.
    Renderiza las páginas del expediente clínico (Anamnesis, Odontograma, Ortodoncia)
    directamente en pantalla sin requerir visores externos.
    """
    def __init__(self, master, ruta_pdf: str, theme: dict = None):
        super().__init__(master)
        self.ruta_pdf = ruta_pdf
        self.theme = theme or obtener_tema_activo_dict()
        
        self.title(f"Vista Previa de Expediente Clínico - {os.path.basename(ruta_pdf)}")
        self.geometry("740x860")
        self.minsize(600, 700)
        self.attributes("-topmost", True)
        self.configure(fg_color=self.theme["bg_dark"])

        self.pagina_actual = 0
        self.total_paginas = 1
        self.zoom_factor = 1.0
        self.doc = None

        self._abrir_documento()
        self._build_ui()
        self._cargar_pagina()

    def _abrir_documento(self):
        try:
            if os.path.exists(self.ruta_pdf):
                self.doc = fitz.open(self.ruta_pdf)
                self.total_paginas = len(self.doc)
        except Exception as e:
            print(f"[PDF PREVIEW ERROR]: {e}")
            self.doc = None

    def _build_ui(self):
        t = self.theme

        # Barra Superior
        top_bar = ctk.CTkFrame(self, fg_color=t["card_dark"], height=56, corner_radius=12, border_width=1, border_color=t["border"])
        top_bar.pack(fill="x", padx=16, pady=(14, 8))
        top_bar.pack_propagate(False)

        ctk.CTkLabel(
            top_bar, text=f"📄 {os.path.basename(self.ruta_pdf)}",
            font=("Segoe UI", 11, "bold"), text_color=t["text_primary"]
        ).pack(side="left", padx=16)

        btn_externo = ctk.CTkButton(
            top_bar, text="Abrir Externo ↗", width=120, height=32,
            font=("Segoe UI", 11, "bold"), fg_color=t["azul_acero"],
            hover_color=t["azul_pastel"], corner_radius=8,
            command=self._abrir_en_sistema
        )
        btn_externo.pack(side="right", padx=(6, 14))

        # Contenedor Central para la imagen renderizada de la página
        self.frame_visor = ctk.CTkScrollableFrame(self, fg_color=t["card_dark"], corner_radius=12, border_width=1, border_color=t["border"])
        self.frame_visor.pack(fill="both", expand=True, padx=16, pady=4)

        self.lbl_imagen_pagina = ctk.CTkLabel(self.frame_visor, text="", image=None)
        self.lbl_imagen_pagina.pack(expand=True, pady=10)

        # Barra Inferior de Navegación y Zoom
        bot_bar = ctk.CTkFrame(self, fg_color=t["card_dark"], height=52, corner_radius=12, border_width=1, border_color=t["border"])
        bot_bar.pack(fill="x", padx=16, pady=(8, 14))
        bot_bar.pack_propagate(False)

        # Botones de navegación
        self.btn_ant = ctk.CTkButton(
            bot_bar, text="◀ Anterior", width=90, height=32,
            font=("Segoe UI", 11, "bold"), fg_color="#334155", hover_color="#475569",
            corner_radius=8, command=self._pagina_anterior
        )
        self.btn_ant.pack(side="left", padx=(14, 6))

        self.lbl_contador_paginas = ctk.CTkLabel(
            bot_bar, text=f"Página 1 de {self.total_paginas}",
            font=("Segoe UI", 11, "bold"), text_color=t["aqua"]
        )
        self.lbl_contador_paginas.pack(side="left", padx=8)

        self.btn_sig = ctk.CTkButton(
            bot_bar, text="Siguiente ▶", width=90, height=32,
            font=("Segoe UI", 11, "bold"), fg_color="#334155", hover_color="#475569",
            corner_radius=8, command=self._pagina_siguiente
        )
        self.btn_sig.pack(side="left", padx=6)

        # Botones de Zoom
        btn_zoom_mas = ctk.CTkButton(
            bot_bar, text="🔍 +", width=44, height=32,
            font=("Segoe UI", 11, "bold"), fg_color="#334155", hover_color="#475569",
            corner_radius=8, command=self._zoom_in
        )
        btn_zoom_mas.pack(side="right", padx=(4, 14))

        btn_zoom_menos = ctk.CTkButton(
            bot_bar, text="🔍 -", width=44, height=32,
            font=("Segoe UI", 11, "bold"), fg_color="#334155", hover_color="#475569",
            corner_radius=8, command=self._zoom_out
        )
        btn_zoom_menos.pack(side="right", padx=4)

    def _cargar_pagina(self):
        if not self.doc or self.pagina_actual >= len(self.doc):
            self.lbl_imagen_pagina.configure(text="No se pudo cargar la página del PDF.")
            return

        try:
            pagina = self.doc.load_page(self.pagina_actual)
            dpi = int(120 * self.zoom_factor)
            pix = pagina.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            ancho_display = int(pix.width * (650 / max(pix.width, 1)))
            alto_display = int(pix.height * (ancho_display / max(pix.width, 1)))

            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(ancho_display, alto_display))
            self.lbl_imagen_pagina.configure(image=ctk_img, text="")

            self.lbl_contador_paginas.configure(text=f"Página {self.pagina_actual + 1} de {self.total_paginas}")
            self.btn_ant.configure(state="normal" if self.pagina_actual > 0 else "disabled")
            self.btn_sig.configure(state="normal" if self.pagina_actual < self.total_paginas - 1 else "disabled")
        except Exception as e:
            print(f"[PDF RENDER ERROR]: {e}")
            self.lbl_imagen_pagina.configure(text=f"Error al renderizar página: {e}")

    def _pagina_anterior(self):
        if self.pagina_actual > 0:
            self.pagina_actual -= 1
            self._cargar_pagina()

    def _pagina_siguiente(self):
        if self.pagina_actual < self.total_paginas - 1:
            self.pagina_actual += 1
            self._cargar_pagina()

    def _zoom_in(self):
        if self.zoom_factor < 1.8:
            self.zoom_factor += 0.2
            self._cargar_pagina()

    def _zoom_out(self):
        if self.zoom_factor > 0.6:
            self.zoom_factor -= 0.2
            self._cargar_pagina()

    def _abrir_en_sistema(self):
        abrir_archivo_o_carpeta_nativo(self.ruta_pdf)

    def destroy(self):
        if self.doc:
            try:
                self.doc.close()
            except Exception:
                pass
        super().destroy()
