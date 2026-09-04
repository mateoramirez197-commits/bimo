import customtkinter as ctk
from PIL import Image, ImageDraw
from config import obtener_tema_activo_dict

def render_infinity_88_badge(size=44, fg_color="#FFFFFF", badge_bg="#0F172A", border_color="#334155"):
    """
    Renderiza mediante supersampling de alta definición el emblema oficial BIMO:
    Dos ochos (88) entrelazados formando un nudo infinito simétrico de precisión matemática.
    """
    scale = 4
    img_size = size * scale
    img = Image.new('RGBA', (img_size, img_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Placa de fondo Soft 3D estilo cristal esmerilado
    radius = int(12 * scale)
    
    # Parse badge_bg
    bg_tuple = (15, 23, 42, 235)
    if isinstance(badge_bg, str) and badge_bg.startswith("#") and len(badge_bg) == 7:
        bg_tuple = tuple(int(badge_bg[i:i+2], 16) for i in (1, 3, 5)) + (235,)
    
    border_tuple = (51, 65, 85, 255)
    if isinstance(border_color, str) and border_color.startswith("#") and len(border_color) == 7:
        border_tuple = tuple(int(border_color[i:i+2], 16) for i in (1, 3, 5)) + (255,)

    draw.rounded_rectangle(
        [int(2 * scale), int(2 * scale), img_size - int(2 * scale), img_size - int(2 * scale)],
        radius=radius,
        fill=bg_tuple,
        outline=border_tuple,
        width=max(1, int(1.4 * scale))
    )

    cx, cy = img_size / 2.0, img_size / 2.0
    r = 6.4 * scale
    stroke = max(1, int(2.0 * scale))

    # Color del trazo
    fg_tuple = (255, 255, 255)
    if isinstance(fg_color, str) and fg_color.startswith("#") and len(fg_color) == 7:
        fg_tuple = tuple(int(fg_color[i:i+2], 16) for i in (1, 3, 5))

    rgb_stroke_v = fg_tuple + (245,)
    rgb_stroke_h = fg_tuple + (220,)
    rgb_dot = fg_tuple + (255,)

    # Ocho vertical (8)
    draw.ellipse([cx - r, cy - 2 * r, cx + r, cy], outline=rgb_stroke_v, width=stroke)
    draw.ellipse([cx - r, cy, cx + r, cy + 2 * r], outline=rgb_stroke_v, width=stroke)

    # Ocho horizontal entrelazado (Infinito ∞)
    draw.ellipse([cx - 2 * r, cy - r, cx, cy + r], outline=rgb_stroke_h, width=stroke)
    draw.ellipse([cx, cy - r, cx + 2 * r, cy + r], outline=rgb_stroke_h, width=stroke)

    # Nódulo central de convergencia
    cr = 1.6 * scale
    draw.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=rgb_dot)

    return img.resize((size, size), Image.Resampling.LANCZOS)


class BimoLogo(ctk.CTkFrame):
    """
    Logotipo Vanguardista Oficial BIMO:
    Emblema de dos ochos entrelazados (88 / Infinito) + BIMO by Matsword.
    Adaptable cromáticamente al tema visual activo.
    """
    def __init__(self, master, font_size=28, orientation="horizontal", show_subtitle=True, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.font_size = font_size
        self.orientation = orientation
        self.show_subtitle = show_subtitle
        self.labels = []
        self._build_logo()

    def _build_logo(self):
        t = obtener_tema_activo_dict()
        badge_size = max(28, int(self.font_size * 1.35))
        
        # Color del emblema según tema
        fg_c = "#FFFFFF" if t.get("mode") == "dark" else "#0F172A"
        bg_c = t.get("bg_dark", "#0F172A")
        border_c = t.get("border", "#334155")
        
        img_badge = render_infinity_88_badge(size=badge_size, fg_color=fg_c, badge_bg=bg_c, border_color=border_c)
        self.ctk_emblema = ctk.CTkImage(light_image=img_badge, dark_image=img_badge, size=(badge_size, badge_size))

        if self.orientation == "vertical":
            self.lbl_badge = ctk.CTkLabel(self, text="", image=self.ctk_emblema)
            self.lbl_badge.pack(pady=(0, 6))

            # Fila de Título BIMO + PRO
            row_title = ctk.CTkFrame(self, fg_color="transparent")
            row_title.pack()

            self.lbl_bimo = ctk.CTkLabel(
                row_title, 
                text="BIMO", 
                font=("Segoe UI Black", self.font_size, "bold"), 
                text_color=t.get("text_primary", "#FFFFFF")
            )
            self.lbl_bimo.pack(side="left", padx=(0, 4))
            self.labels.append(self.lbl_bimo)

            pro_font_size = max(8, int(self.font_size * 0.28))
            self.lbl_pro = ctk.CTkLabel(
                row_title,
                text=" PRO ",
                font=("Segoe UI", pro_font_size, "bold"),
                text_color="#CBD5E1",
                fg_color=t.get("card_hover", "#1E293B"),
                corner_radius=4
            )
            self.lbl_pro.pack(side="left", pady=2)

            if self.show_subtitle:
                sub_size = max(9, int(self.font_size * 0.35))
                self.lbl_sub = ctk.CTkLabel(
                    self,
                    text="by Matsword",
                    font=("Segoe UI", sub_size, "bold"),
                    text_color=t.get("text_muted", "#94A3B8")
                )
                self.lbl_sub.pack(pady=(2, 0))
                self.labels.append(self.lbl_sub)
        else:
            # Horizontal (default)
            self.lbl_badge = ctk.CTkLabel(self, text="", image=self.ctk_emblema)
            self.lbl_badge.pack(side="left", padx=(0, 10))

            text_col = ctk.CTkFrame(self, fg_color="transparent")
            text_col.pack(side="left", fill="y", expand=True)

            row_title = ctk.CTkFrame(text_col, fg_color="transparent")
            row_title.pack(anchor="w")

            self.lbl_bimo = ctk.CTkLabel(
                row_title, 
                text="BIMO", 
                font=("Segoe UI Black", self.font_size, "bold"), 
                text_color=t.get("text_primary", "#FFFFFF")
            )
            self.lbl_bimo.pack(side="left", padx=(0, 5))
            self.labels.append(self.lbl_bimo)

            pro_font_size = max(8, int(self.font_size * 0.28))
            self.lbl_pro = ctk.CTkLabel(
                row_title,
                text=" PRO ",
                font=("Segoe UI", pro_font_size, "bold"),
                text_color="#CBD5E1",
                fg_color=t.get("card_hover", "#1E293B"),
                corner_radius=4
            )
            self.lbl_pro.pack(side="left", pady=2)

            if self.show_subtitle:
                sub_size = max(9, int(self.font_size * 0.35))
                self.lbl_sub = ctk.CTkLabel(
                    text_col,
                    text="by Matsword",
                    font=("Segoe UI", sub_size, "bold"),
                    text_color=t.get("text_muted", "#94A3B8")
                )
                self.lbl_sub.pack(anchor="w", pady=(1, 0))
                self.labels.append(self.lbl_sub)

    def actualizar_colores(self):
        """Actualiza los colores del logotipo al cambiar de tema."""
        t = obtener_tema_activo_dict()
        try:
            badge_size = max(28, int(self.font_size * 1.35))
            fg_c = "#FFFFFF" if t.get("mode") == "dark" else "#0F172A"
            bg_c = t.get("bg_dark", "#0F172A")
            border_c = t.get("border", "#334155")
            
            img_badge = render_infinity_88_badge(size=badge_size, fg_color=fg_c, badge_bg=bg_c, border_color=border_c)
            self.ctk_emblema = ctk.CTkImage(light_image=img_badge, dark_image=img_badge, size=(badge_size, badge_size))
            self.lbl_badge.configure(image=self.ctk_emblema)
            self.lbl_bimo.configure(text_color=t.get("text_primary", "#FFFFFF"))
            if hasattr(self, 'lbl_sub'):
                self.lbl_sub.configure(text_color=t.get("text_muted", "#94A3B8"))
        except Exception:
            pass
