import customtkinter as ctk
from config import obtener_tema_activo_dict

class BimoLogo(ctk.CTkFrame):
    """
    Logotipo Vanguardista Oficial BIMO:
    Letras B - I - M - O adaptables cromáticamente al tema visual activo.
    """
    def __init__(self, master, font_size=28):
        super().__init__(master, fg_color="transparent")
        self.font_size = font_size
        self.labels = []
        self._build_letras()

    def _build_letras(self):
        t = obtener_tema_activo_dict()
        colores = t.get("logo_colors", [t.get("aqua", "#00F5D4"), t.get("azul_pastel", "#70D6FF"), t.get("fucsia", "#FF006E"), t.get("amarillo", "#FFBE0B")])
        letras = ["B", "I", "M", "O"]

        for letra, color in zip(letras, colores):
            lbl = ctk.CTkLabel(
                self, 
                text=letra, 
                font=("Segoe UI Black", self.font_size, "bold"), 
                text_color=color
            )
            lbl.pack(side="left", padx=1)
            self.labels.append(lbl)

    def actualizar_colores(self):
        """Actualiza los colores de las letras B-I-M-O al cambiar de tema."""
        t = obtener_tema_activo_dict()
        colores = t.get("logo_colors", [t.get("aqua", "#00F5D4"), t.get("azul_pastel", "#70D6FF"), t.get("fucsia", "#FF006E"), t.get("amarillo", "#FFBE0B")])
        for lbl, color in zip(self.labels, colores):
            try:
                lbl.configure(text_color=color)
            except Exception:
                pass
