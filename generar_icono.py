"""
Genera el ícono oficial de BIMO: la muela (Tabler Icons "dental", licencia MIT) que se ve
dentro de la app, en blanco sobre un cuadrado redondeado negro con brillo de vidrio.

Salidas:
- assets/bimo_icon.png  (512 px)
- assets/bimo_icon.ico  (256, 128, 64, 48, 32, 24, 16 px)
- Copia en "Archivos de instalación/assets/" para el instalador.

Uso:  python generar_icono.py
"""
import os
import shutil
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FUENTE = os.path.join(BASE_DIR, "web_ui", "vendor", "tabler-icons", "fonts", "tabler-icons.ttf")
GLIFO_MUELA = ""  # .ti-dental en tabler-icons.min.css
TAMANOS_ICO = [256, 128, 64, 48, 32, 24, 16]


def dibujar_icono(tam: int) -> Image.Image:
    """Dibuja el ícono a 4x y lo reduce para bordes suaves. En tamaños chicos engrosa la muela."""
    s = tam * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    margen = round(s * 0.06)
    radio = round(s * 0.23)
    caja = (margen, margen, s - margen, s - margen)

    # Fondo negro con un leve degradado vertical (#26262A arriba -> #0A0A0A abajo)
    fondo = Image.new("RGBA", (s, s))
    d = ImageDraw.Draw(fondo)
    for y in range(s):
        k = y / s
        c = round(38 * (1 - k) + 10 * k)
        d.line([(0, y), (s, y)], fill=(c, c, c + 2, 255))
    mascara = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mascara).rounded_rectangle(caja, radius=radio, fill=255)
    img.paste(fondo, (0, 0), mascara)

    # Brillo de vidrio en la mitad superior y canto de luz fino
    if tam >= 32:
        # Reflejo que se desvanece hacia la mitad (sin corte duro)
        alfa = Image.new("L", (s, s), 0)
        da = ImageDraw.Draw(alfa)
        alto = (s - 2 * margen) * 0.55
        for y in range(margen, round(margen + alto)):
            da.line([(0, y), (s, y)], fill=round(30 * (1 - (y - margen) / alto) ** 1.6))
        brillo = Image.new("RGBA", (s, s), (255, 255, 255, 0))
        brillo.putalpha(Image.composite(alfa, Image.new("L", (s, s), 0), mascara))
        img = Image.alpha_composite(img, brillo)
        ImageDraw.Draw(img).rounded_rectangle(caja, radius=radio, outline=(255, 255, 255, 46), width=max(2, s // 128))

    # Muela blanca centrada (más gruesa en tamaños pequeños para que se lea)
    tam_glifo = round(s * 0.62)
    fuente = ImageFont.truetype(FUENTE, tam_glifo)
    grosor = 0 if tam >= 64 else (round(s * 0.012) if tam >= 32 else round(s * 0.022))
    capa = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    dc = ImageDraw.Draw(capa)
    x0, y0, x1, y1 = dc.textbbox((0, 0), GLIFO_MUELA, font=fuente, stroke_width=grosor)
    pos = ((s - (x1 - x0)) / 2 - x0, (s - (y1 - y0)) / 2 - y0)
    dc.text(pos, GLIFO_MUELA, font=fuente, fill=(255, 255, 255, 255),
            stroke_width=grosor, stroke_fill=(255, 255, 255, 255))
    if tam >= 64:
        sombra = capa.getchannel("A").filter(ImageFilter.GaussianBlur(s * 0.012))
        img = Image.alpha_composite(img, Image.merge("RGBA", (*[Image.new("L", (s, s), 0)] * 3, sombra.point(lambda a: a * 0.35))))
    img = Image.alpha_composite(img, capa)

    return img.resize((tam, tam), Image.LANCZOS)


def main():
    assets = os.path.join(BASE_DIR, "assets")
    os.makedirs(assets, exist_ok=True)
    png = os.path.join(assets, "bimo_icon.png")
    ico = os.path.join(assets, "bimo_icon.ico")

    dibujar_icono(512).save(png)
    grandes = dibujar_icono(256)
    grandes.save(ico, format="ICO", sizes=[(t, t) for t in TAMANOS_ICO],
                 append_images=[dibujar_icono(t) for t in TAMANOS_ICO[1:]])
    # Copia con nombre nuevo para el acceso directo del escritorio: Windows guarda en caché
    # la imagen por ruta de archivo, y con el nombre antiguo seguía mostrando el robot.
    shutil.copy2(ico, os.path.join(assets, "bimo_muela.ico"))
    print(f"[ICONO] {png}\n[ICONO] {ico}")

    destino_instalador = os.path.join(BASE_DIR, "Archivos de instalación", "assets")
    if os.path.isdir(destino_instalador):
        for f in (png, ico):
            shutil.copy2(f, destino_instalador)
        print(f"[ICONO] Copiado a {destino_instalador}")


if __name__ == "__main__":
    main()
