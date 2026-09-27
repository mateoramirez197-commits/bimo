# -*- coding: utf-8 -*-
"""
Generador de Icono Oficial de BIMO Pro - Robot Asistente Clínico Inteligente
Renderiza a 1024x1024 con supersampling anti-aliasing y genera:
- assets/bimo_icon.png (alta resolución)
- assets/bimo_icon.ico (256, 128, 64, 48, 32, 16 px)
"""
import os
import math
from PIL import Image, ImageDraw, ImageFilter

def generar_icono_bot():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    # Dimensiones supersampleadas 4x para anti-aliasing perfecto
    S = 1024
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Fondo Squircle con Gradiente Tecnológico Oscuro (Obsidiana a Azul Índigo Profundo)
    margin = 48
    radius = 210
    
    # Máscara para gradiente de fondo
    bg_mask = Image.new("L", (S, S), 0)
    draw_bg = ImageDraw.Draw(bg_mask)
    draw_bg.rounded_rectangle([margin, margin, S - margin, S - margin], radius=radius, fill=255)

    # Crear gradiente
    bg_gradient = Image.new("RGBA", (S, S), (11, 15, 25, 255))
    draw_grad = ImageDraw.Draw(bg_gradient)
    for y in range(margin, S - margin):
        factor = (y - margin) / (S - 2 * margin)
        # De #0b0f19 a #161b33
        r = int(11 + factor * (22 - 11))
        g = int(15 + factor * (27 - 15))
        b = int(25 + factor * (51 - 25))
        draw_grad.line([(margin, y), (S - margin, y)], fill=(r, g, b, 255))

    img.paste(bg_gradient, (0, 0), bg_mask)

    # Borde exterior luminoso Cian / Neón (#00f5d4)
    draw.rounded_rectangle([margin, margin, S - margin, S - margin], radius=radius, outline=(0, 245, 212, 220), width=16)
    # Borde interior sutil
    draw.rounded_rectangle([margin + 12, margin + 12, S - margin - 12, S - margin - 12], radius=radius - 10, outline=(56, 189, 248, 70), width=4)

    # 2. Resplandor / Glow detrás de la cabeza del Bot
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_glow = ImageDraw.Draw(glow)
    draw_glow.ellipse([260, 260, 764, 764], fill=(0, 245, 212, 50))
    glow = glow.filter(ImageFilter.GaussianBlur(60))
    img.alpha_composite(glow)

    # 3. Antena del Bot
    cx = 512
    draw.rectangle([cx - 12, 200, cx + 12, 330], fill=(148, 163, 184, 255))
    # Esfera superior brillante de la antena
    draw.ellipse([cx - 44, 150, cx + 44, 238], fill=(0, 245, 212, 255))
    draw.ellipse([cx - 24, 168, cx + 24, 220], fill=(255, 255, 255, 240))

    # Resplandor de la esfera de la antena
    ant_glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw_ant = ImageDraw.Draw(ant_glow)
    draw_ant.ellipse([cx - 60, 134, cx + 60, 254], fill=(0, 245, 212, 90))
    ant_glow = ant_glow.filter(ImageFilter.GaussianBlur(15))
    img.alpha_composite(ant_glow)

    # 4. Orejeras / Auriculares laterales del Bot (Sensores de audio / escucha activa)
    draw.rounded_rectangle([180, 420, 275, 600], radius=40, fill=(30, 41, 59, 255), outline=(0, 245, 212, 230), width=10)
    draw.ellipse([210, 475, 250, 545], fill=(0, 245, 212, 220))
    
    draw.rounded_rectangle([S - 275, 420, S - 180, 600], radius=40, fill=(30, 41, 59, 255), outline=(0, 245, 212, 230), width=10)
    draw.ellipse([S - 250, 475, S - 210, 545], fill=(0, 245, 212, 220))

    # 5. Cabeza / Casco del Bot (Cuerpo principal)
    head_box = [236, 280, S - 236, 720]
    draw.rounded_rectangle([head_box[0] + 4, head_box[1] + 12, head_box[2] + 4, head_box[3] + 12], radius=150, fill=(15, 23, 42, 140))
    draw.rounded_rectangle(head_box, radius=150, fill=(241, 245, 249, 255), outline=(203, 213, 225, 255), width=8)

    # Detalle en la frente
    draw.line([(cx - 70, 315), (cx + 70, 315)], fill=(203, 213, 225, 255), width=6)
    draw.line([(cx - 50, 330), (cx + 50, 330)], fill=(203, 213, 225, 255), width=4)

    # 6. Pantalla / Visor Facial Oscuro Panorámico
    visor_box = [284, 370, S - 284, 620]
    draw.rounded_rectangle(visor_box, radius=95, fill=(15, 23, 42, 255), outline=(51, 65, 85, 255), width=8)
    draw.arc([visor_box[0] + 20, visor_box[1] + 10, visor_box[2] - 20, visor_box[1] + 90], start=190, end=350, fill=(255, 255, 255, 70), width=8)

    # 7. Ojos Expresivos Digitales del Bot (Cian Neón Luminoso #00f5d4)
    eye_y1 = 435
    eye_y2 = 525
    eye_w = 72
    eye_r = 36

    # Ojo Izquierdo
    eye_lx = 380
    draw.rounded_rectangle([eye_lx - eye_w // 2, eye_y1, eye_lx + eye_w // 2, eye_y2], radius=eye_r, fill=(0, 245, 212, 255))
    draw.ellipse([eye_lx - 15, eye_y1 + 12, eye_lx + 15, eye_y1 + 42], fill=(255, 255, 255, 240))

    # Ojo Derecho
    eye_rx = S - 380
    draw.rounded_rectangle([eye_rx - eye_w // 2, eye_y1, eye_rx + eye_w // 2, eye_y2], radius=eye_r, fill=(0, 245, 212, 255))
    draw.ellipse([eye_rx - 15, eye_y1 + 12, eye_rx + 15, eye_y1 + 42], fill=(255, 255, 255, 240))

    # 8. Sonrisa Sutil / Boca Digital Iluminada
    mouth_y = 570
    draw.arc([cx - 48, mouth_y - 20, cx + 48, mouth_y + 14], start=20, end=160, fill=(0, 245, 212, 255), width=10)

    # 9. Cuello y Pecho con Emblema Odontológico / Médico
    draw.rectangle([452, 715, 572, 755], fill=(51, 65, 85, 255))

    chest_box = [320, 750, S - 320, 910]
    draw.rounded_rectangle(chest_box, radius=70, fill=(226, 232, 240, 255), outline=(203, 213, 225, 255), width=8)

    crest_cy = 825
    draw.ellipse([cx - 36, crest_cy - 36, cx + 36, crest_cy + 36], fill=(15, 23, 42, 255), outline=(0, 245, 212, 255), width=5)
    draw.rectangle([cx - 5, crest_cy - 18, cx + 5, crest_cy + 18], fill=(0, 245, 212, 255))
    draw.rectangle([cx - 18, crest_cy - 5, cx + 18, crest_cy + 5], fill=(0, 245, 212, 255))

    # 10. Guardar imagen PNG (512x512 y 256x256)
    png_path = os.path.join(assets_dir, "bimo_icon.png")
    final_512 = img.resize((512, 512), Image.Resampling.LANCZOS)
    final_512.save(png_path, format="PNG")
    print(f"[OK] Master PNG guardado en: {png_path}")

    # 11. Generar archivo .ICO multi-capa para Windows
    ico_path = os.path.join(assets_dir, "bimo_icon.ico")
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    final_512.save(ico_path, format="ICO", sizes=icon_sizes)
    print(f"[OK] Icono multi-resolución .ICO guardado en: {ico_path}")

    # Sincronizar en dist si existe
    dist_ico = os.path.join(base_dir, "dist", "BIMO_Pro", "_internal", "assets", "bimo_icon.ico")
    if os.path.exists(os.path.dirname(dist_ico)):
        final_512.save(dist_ico, format="ICO", sizes=icon_sizes)
        print(f"[OK] Icono sincronizado en: {dist_ico}")

if __name__ == "__main__":
    generar_icono_bot()
