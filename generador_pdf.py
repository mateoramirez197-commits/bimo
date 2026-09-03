import json
import os
import re
import sys
import datetime
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from fpdf import FPDF

# Configurar salida UTF-8 en consola para evitar errores en Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA_BASE_ODONTOGRAMA = os.path.join(BASE_DIR, "base_odontograma.png")

# Coordenadas exactas de 8 puntos por pieza dental (FDI 11 a 48) sobre base_odontograma.png (1664 x 2560)
POLIGONOS_8_PUNTOS = {
    '11': [(802, 178), (754, 299), (727, 313), (682, 299), (625, 174), (628, 161), (751, 131), (801, 137)],
    '12': [(628, 275), (600, 330), (588, 336), (540, 312), (486, 228), (492, 219), (600, 169), (608, 170)],
    '13': [(532, 371), (510, 419), (485, 427), (368, 371), (360, 357), (392, 260), (460, 240), (482, 254)],
    '14': [(436, 489), (433, 501), (382, 527), (276, 490), (275, 487), (280, 423), (342, 372), (423, 426)],
    '15': [(398, 615), (393, 624), (336, 653), (234, 629), (219, 569), (228, 553), (279, 513), (386, 555)],
    '16': [(393, 717), (358, 852), (324, 868), (175, 806), (170, 716), (207, 664), (236, 653), (387, 703)],
    '17': [(361, 1015), (348, 1050), (299, 1072), (158, 1019), (152, 930), (184, 879), (216, 870), (359, 930)],
    '18': [(348, 1205), (342, 1219), (287, 1257), (171, 1225), (157, 1131), (175, 1099), (216, 1077), (344, 1128)],
    '21': [(994, 174), (938, 298), (901, 314), (865, 299), (818, 178), (818, 137), (868, 131), (992, 162)],
    '22': [(1134, 231), (1079, 313), (1031, 336), (1019, 330), (991, 276), (1013, 169), (1018, 168), (1128, 219)],
    '23': [(1260, 355), (1252, 370), (1134, 427), (1109, 419), (1088, 370), (1137, 254), (1160, 240), (1229, 261)],
    '24': [(1344, 487), (1343, 490), (1237, 527), (1187, 502), (1183, 489), (1196, 427), (1278, 372), (1339, 423)],
    '25': [(1400, 568), (1389, 621), (1283, 653), (1226, 624), (1221, 614), (1232, 555), (1340, 513), (1391, 552)],
    '26': [(1449, 715), (1445, 806), (1295, 868), (1260, 851), (1227, 716), (1233, 702), (1383, 653), (1415, 666)],
    '27': [(1467, 929), (1463, 1016), (1321, 1072), (1271, 1049), (1257, 1015), (1261, 930), (1403, 870), (1434, 878)],
    '28': [(1462, 1130), (1447, 1227), (1331, 1256), (1276, 1217), (1272, 1207), (1275, 1129), (1403, 1077), (1448, 1103)],
    '31': [(937, 2410), (937, 2422), (847, 2444), (822, 2441), (817, 2405), (844, 2318), (859, 2304), (896, 2327)],
    '32': [(1069, 2382), (1063, 2392), (966, 2427), (955, 2425), (939, 2341), (962, 2291), (966, 2289), (1012, 2314)],
    '33': [(1176, 2278), (1162, 2346), (1096, 2381), (1072, 2367), (1028, 2268), (1047, 2229), (1070, 2221), (1171, 2267)],
    '34': [(1273, 2214), (1271, 2219), (1200, 2260), (1123, 2211), (1111, 2147), (1114, 2138), (1162, 2105), (1263, 2151)],
    '35': [(1338, 2071), (1336, 2075), (1280, 2114), (1170, 2072), (1156, 2025), (1181, 1973), (1217, 1960), (1326, 2004)],
    '36': [(1408, 1896), (1392, 1935), (1345, 1964), (1191, 1916), (1184, 1900), (1231, 1744), (1252, 1736), (1346, 1743)],
    '37': [(1447, 1676), (1431, 1713), (1378, 1731), (1222, 1686), (1220, 1679), (1236, 1560), (1296, 1525), (1439, 1574)],
    '38': [(1446, 1385), (1418, 1507), (1392, 1518), (1262, 1477), (1256, 1461), (1269, 1357), (1315, 1328), (1431, 1352)],
    '41': [(802, 2405), (797, 2441), (772, 2444), (684, 2425), (682, 2409), (723, 2326), (760, 2304), (775, 2316)],
    '42': [(680, 2342), (664, 2425), (654, 2427), (556, 2392), (551, 2386), (607, 2314), (655, 2290), (657, 2291)],
    '43': [(590, 2269), (546, 2366), (526, 2380), (456, 2345), (443, 2278), (448, 2267), (548, 2221), (569, 2227)],
    '44': [(508, 2147), (496, 2211), (418, 2260), (347, 2218), (344, 2210), (356, 2150), (456, 2105), (507, 2142)],
    '45': [(463, 2028), (448, 2072), (341, 2115), (283, 2076), (281, 2072), (292, 2005), (401, 1960), (441, 1977)],
    '46': [(435, 1898), (429, 1913), (274, 1964), (230, 1939), (210, 1894), (273, 1743), (366, 1736), (386, 1743)],
    '47': [(399, 1679), (398, 1683), (241, 1731), (190, 1715), (172, 1674), (180, 1574), (323, 1525), (384, 1561)],
    '48': [(363, 1461), (358, 1475), (226, 1517), (199, 1505), (173, 1386), (186, 1355), (303, 1328), (352, 1360)]
}

_CACHE_MASCARAS = None

def _calcular_mascaras_dientes(ruta_base=RUTA_BASE_ODONTOGRAMA):
    global _CACHE_MASCARAS
    if _CACHE_MASCARAS is not None:
        return _CACHE_MASCARAS

    if not os.path.exists(ruta_base):
        return {}

    im = Image.open(ruta_base).convert("L")
    arr = np.array(im)

    tooth_mask = (arr >= 210) & (arr <= 245)
    labeled, num_features = ndimage.label(tooth_mask)
    sizes = ndimage.sum(tooth_mask, labeled, range(num_features + 1))

    teeth = {}
    for idx in range(1, num_features + 1):
        if sizes[idx] > 5000:
            cy, cx = ndimage.center_of_mass(tooth_mask, labeled, idx)
            teeth[idx] = {"size": sizes[idx], "cy": cy, "cx": cx}

    # Arcada superior (cy < 1300):
    q1 = sorted([idx for idx, t in teeth.items() if t["cy"] < 1300 and t["cx"] < 832], key=lambda i: -teeth[i]["cy"])
    q2 = sorted([idx for idx, t in teeth.items() if t["cy"] < 1300 and t["cx"] >= 832], key=lambda i: teeth[i]["cy"])

    # Arcada inferior (cy >= 1300):
    q4 = sorted([idx for idx, t in teeth.items() if t["cy"] >= 1300 and t["cx"] < 832], key=lambda i: teeth[i]["cy"])
    q3 = sorted([idx for idx, t in teeth.items() if t["cy"] >= 1300 and t["cx"] >= 832], key=lambda i: -teeth[i]["cy"])

    mascaras = {}
    for n, idx in enumerate(q1):
        mascaras[str(18 - n)] = ndimage.binary_fill_holes(labeled == idx)
    for n, idx in enumerate(q2):
        mascaras[str(21 + n)] = ndimage.binary_fill_holes(labeled == idx)
    for n, idx in enumerate(q4):
        mascaras[str(48 - n)] = ndimage.binary_fill_holes(labeled == idx)
    for n, idx in enumerate(q3):
        mascaras[str(31 + n)] = ndimage.binary_fill_holes(labeled == idx)

    _CACHE_MASCARAS = mascaras
    return _CACHE_MASCARAS

def extraer_fdi(pieza_val) -> str:
    """
    Normaliza cualquier mención de pieza dental al formato FDI (11 a 48).
    Soporta:
    - Dígitos estándar: '36', 'Pieza 21', '3.6' -> '36', 'Diente 1.8' -> '18'
    - Nomenclatura anatómica en español:
      'Premolar superior derecho' -> '14' (o '15')
      'Premolar superior izquierdo' -> '24'
      'Premolar inferior izquierdo' -> '34'
      'Premolar inferior derecho' -> '44'
      'Molar superior derecho' / 'Muela superior derecha' -> '16'
      'Molar superior izquierdo' / 'Muela superior izquierda' -> '26'
      'Molar inferior izquierdo' / 'Muela inferior izquierda' -> '36'
      'Molar inferior derecho' / 'Muela inferior derecha' -> '46'
      'Muela del juicio' / 'Tercer molar' -> '18', '28', '38', '48'
    """
    if not pieza_val:
        return ""
    s = str(pieza_val).strip().lower()

    # 1. Búsqueda de dígitos estándar FDI
    m_std = re.search(r'\b([1-4][1-8])\b', s)
    if m_std:
        return m_std.group(1)

    m_dot = re.search(r'([1-4])\.([1-8])', s)
    if m_dot:
        return f"{m_dot.group(1)}{m_dot.group(2)}"

    m_any = re.search(r'([1-4][1-8])', s)
    if m_any:
        return m_any.group(1)

    # 2. Mapeo anatómico en español
    es_sup = any(k in s for k in ['superior', 'arriba', 'maxilar', 'sup.'])
    es_inf = any(k in s for k in ['inferior', 'abajo', 'mandibular', 'inf.'])
    es_der = any(k in s for k in ['derech', 'der.'])
    es_izq = any(k in s for k in ['izquierd', 'izq.'])

    # Premolares (debe evaluarse ANTES de molares porque 'premolar' contiene la subcadena 'molar'):
    if 'premolar' in s:
        es_2do = any(k in s for k in ['segund', '2do', '2°'])
        if es_sup and es_der:
            return "15" if es_2do else "14"
        if es_sup and es_izq:
            return "25" if es_2do else "24"
        if es_inf and es_izq:
            return "35" if es_2do else "34"
        if es_inf and es_der:
            return "45" if es_2do else "44"
        if es_sup:
            return "14"
        if es_inf:
            return "34"
        return "14"

    # Molares / Muelas:
    if any(k in s for k in ['molar', 'muela']):
        es_3er = any(k in s for k in ['tercer', 'tercero', 'juicio', 'cordal', '3er', '3°'])
        es_2do = any(k in s for k in ['segund', '2do', '2°'])
        if es_sup and es_der:
            return "18" if es_3er else ("17" if es_2do else "16")
        if es_sup and es_izq:
            return "28" if es_3er else ("27" if es_2do else "26")
        if es_inf and es_izq:
            return "38" if es_3er else ("37" if es_2do else "36")
        if es_inf and es_der:
            return "48" if es_3er else ("47" if es_2do else "46")
        if es_sup:
            return "16"
        if es_inf:
            return "36"
        return "16"

    # Caninos:
    if any(k in s for k in ['canin', 'colmill']):
        if es_sup and es_der:
            return "13"
        if es_sup and es_izq:
            return "23"
        if es_inf and es_izq:
            return "33"
        if es_inf and es_der:
            return "43"
        return "13"

    # Incisivos:
    if any(k in s for k in ['incisiv', 'paleta', 'frontal']):
        es_lat = any(k in s for k in ['lateral', 'segund'])
        if es_sup and es_der:
            return "12" if es_lat else "11"
        if es_sup and es_izq:
            return "22" if es_lat else "21"
        if es_inf and es_izq:
            return "32" if es_lat else "31"
        if es_inf and es_der:
            return "42" if es_lat else "41"
        return "11"

    return ""

def colorear_odontograma(odontograma_datos, ruta_base=RUTA_BASE_ODONTOGRAMA, ruta_salida=None):
    """
    Pinta sobre base_odontograma.png la anatomía dental completa hasta el contorno exterior:
    - ROJO translúcido vibrante (220, 38, 38, alpha=195): Patologías activas a tratar.
    - AZUL translúcido vibrante (37, 99, 235, alpha=195): Tratamientos previos en buen estado.
    - GRIS clínico (100, 116, 139, alpha=210): Piezas ausentes o exodoncias previas.
    Pintado nítido al 100% de la corona y fisuras, sin sobrepintado y sin dejar bordes a medias.
    """
    if not os.path.exists(ruta_base):
        print(f"[ODONTOGRAMA] Advertencia: No se encontró la imagen base en {ruta_base}")
        return None, {}

    base_im = Image.open(ruta_base).convert("RGBA")
    mascaras = _calcular_mascaras_dientes(ruta_base)
    overlay_arr = np.zeros((*base_im.size[::-1], 4), dtype=np.uint8)

    overlay = Image.new("RGBA", base_im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Colores nítidos y vibrantes de alta definición clínica
    COLOR_ROJO_RGBA = (220, 38, 38, 195)    # Rojo translúcido nítido para patologías activas / pendientes
    COLOR_AZUL_RGBA = (37, 99, 235, 195)   # Azul translúcido nítido para tratamientos previos / realizados
    COLOR_GRIS_RGBA = (100, 116, 139, 210)  # Gris clínico para ausencias / extracciones / exodoncias

    ausentes_kw = (
        'ausent', 'perd', 'extrac', 'exodoncia', 'extraíd', 'extraida',
        'extraído', 'extraido', 'sacar', 'sacó', 'sacaron', 'sacada',
        'sacado', 'no presente', 'agenesia', 'faltant', 'removid',
        'ausencia', 'diente perdido', 'muela perdida', 'sin pieza'
    )
    indicaciones_futuras_kw = (
        'indicar extraccion', 'indicada extraccion', 'indicada exodoncia',
        'requiere extraccion', 'para extraccion', 'indicar exodoncia'
    )
    patologias_kw = (
        'caries', 'fractur', 'movil', 'absces', 'fistul', 'pulpit',
        'necros', 'lesi', 'dolor', 'remanent', 'radicular', 'impactad',
        'retenid', 'filtraci', 'recidiv', 'desadapt', 'infecc',
        'corona defectuosa', 'desajust', 'obturar'
    )
    tratamientos_kw = (
        'resina', 'calza', 'amalgam', 'endodonci', 'conducto',
        'corona', 'obturaci', 'incrustaci', 'puente', 'implant',
        'sellant', 'perno', 'poste', 'carill', 'rehabilitad', 'buen estado',
        'restaurad', 'restauraci', 'curaci', 'calzad'
    )

    resumen_estados = {"rojo": 0, "azul": 0, "gris": 0, "total_evaluadas": 0}

    # Asegurar que odontograma_datos sea una lista
    if isinstance(odontograma_datos, dict):
        odontograma_datos = [odontograma_datos]
    elif not isinstance(odontograma_datos, list):
        odontograma_datos = []

    for item in odontograma_datos:
        if not isinstance(item, dict):
            continue

        pieza_val = item.get("pieza_dental") or item.get("pieza") or item.get("diente") or item.get("numero") or ""
        fdi = extraer_fdi(pieza_val)
        if not fdi:
            continue

        hallazgos = item.get("procedimientos_o_hallazgos", [])
        if isinstance(hallazgos, str):
            hallazgos = [hallazgos]

        texto_h = " ".join(hallazgos).lower()
        if not texto_h.strip():
            continue

        negaciones_tratamiento_kw = (
            'no se hizo', 'no se realizo', 'no se realizó', 'no realizada', 'no realizado',
            'no se corrigio', 'no se corrigió', 'no corregid', 'pendiente', 'sin restaurar',
            'cancelad', 'no resuelt', 'falta realizar', 'planificad', 'se planifica',
            'a realizar', 'por realizar', 'a tratar', 'por tratar'
        )

        tiene_negacion = any(k in texto_h for k in negaciones_tratamiento_kw)
        es_indicacion_futura = any(k in texto_h for k in indicaciones_futuras_kw)
        es_ausente = (not es_indicacion_futura) and any(k in texto_h for k in ausentes_kw)
        es_rojo = es_indicacion_futura or tiene_negacion or any(k in texto_h for k in patologias_kw)
        es_azul = (not tiene_negacion) and any(k in texto_h for k in tratamientos_kw)

        resumen_estados["total_evaluadas"] += 1

        if es_ausente:
            color_rgba = COLOR_GRIS_RGBA
            resumen_estados["gris"] += 1
        elif es_azul:
            # Tratamiento realizado en consulta sin negación -> AZUL
            color_rgba = COLOR_AZUL_RGBA
            resumen_estados["azul"] += 1
        elif es_rojo:
            # Patología activa o tratamiento pendiente/planificado -> ROJO
            color_rgba = COLOR_ROJO_RGBA
            resumen_estados["rojo"] += 1
        else:
            # Si no especifica patología activa y se menciona extracción o ausencia
            if any(k in texto_h for k in ausentes_kw):
                color_rgba = COLOR_GRIS_RGBA
                resumen_estados["gris"] += 1
            else:
                color_rgba = COLOR_ROJO_RGBA
                resumen_estados["rojo"] += 1

        # Colorear la pieza dental completa hasta el contorno anatómico
        if fdi in mascaras:
            overlay_arr[mascaras[fdi]] = color_rgba
        elif fdi in POLIGONOS_8_PUNTOS:
            pts = POLIGONOS_8_PUNTOS[fdi]
            draw.polygon(pts, fill=color_rgba)

    # Integrar capa de máscara anatómica sin sobrepintar
    if overlay_arr.any():
        mask_im = Image.fromarray(overlay_arr, "RGBA")
        overlay = Image.alpha_composite(overlay, mask_im)

    # Fusionar con imagen base del odontograma
    resultado_final = Image.alpha_composite(base_im, overlay).convert("RGB")

    if ruta_salida is None:
        ruta_salida = os.path.join(BASE_DIR, "temp_odontograma.png")

    resultado_final.save(ruta_salida, format="PNG")
    print(f"[ODONTOGRAMA] Imagen procesada guardada en: {ruta_salida} (Evaluadas: {resumen_estados['total_evaluadas']})")
    return ruta_salida, resumen_estados

def generar_nombre_archivo_corto(nombre_completo: str, edad: int, fecha_obj: datetime.datetime) -> str:
    partes = [p for p in re.sub(r'[^a-zA-Z0-9\s]', '', nombre_completo).split() if p]
    if not partes:
        nombre_corto = "Paciente"
    elif len(partes) == 1:
        nombre_corto = partes[0].capitalize()
    else:
        nombre_corto = f"{partes[0].capitalize()}{partes[-1][0].upper()}"
    
    fecha_corta = fecha_obj.strftime("%d-%m-%Y")
    return f"Consulta_{nombre_corto}_{edad}a_{fecha_corta}.pdf"

def sanitizar_cedula(doc: str) -> str:
    """Limpia cédula o documento extrayendo dígitos y eliminando comas, puntos o espacios del dictado."""
    if not doc or str(doc).lower() in ("no especificado", "none", ""):
        return "No especificado"
    solo_digitos = "".join([c for c in str(doc) if c.isdigit()])
    if len(solo_digitos) >= 5:
        return solo_digitos
    return str(doc).replace(",", "").replace(" ", "").strip()

def formatear_edad(edad_raw, texto_contexto: str = "") -> str:
    """
    Normaliza la edad del paciente a un formato uniforme 'X años'.
    Corrige confusiones acústicas comunes como 'diez y seis' -> '10 años y 6 meses' -> '16 años'.
    """
    if not edad_raw or str(edad_raw).strip().lower() in ("no especificado", "none", ""):
        s = ""
    else:
        s = str(edad_raw).strip()

    # Confusiones fonéticas acústicas explícitas (diez y seis -> 10 años y 6 meses o 10 y 6)
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?6\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "16 años"
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?7\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "17 años"
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?8\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "18 años"
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?9\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "19 años"

    # Si el contexto del texto contiene la mención explícita de edad
    if texto_contexto:
        t_low = texto_contexto.lower()
        if re.search(r'\b(?:16|diecis[eé]is|diez y seis)\s*a[ñn]os?\b', t_low):
            return "16 años"
        if re.search(r'\b(?:17|diecisiete|diez y siete)\s*a[ñn]os?\b', t_low):
            return "17 años"
        if re.search(r'\b(?:18|dieciocho|diez y ocho)\s*a[ñn]os?\b', t_low):
            return "18 años"
        if re.search(r'\b(?:19|diecinueve|diez y nueve)\s*a[ñn]os?\b', t_low):
            return "19 años"
        m_num = re.search(r'\b(\d{1,3})\s*a[ñn]os?\b', t_low)
        if m_num:
            return f"{m_num.group(1)} años"

    m = re.search(r'\b(\d{1,3})\b', s)
    if m:
        return f"{m.group(1)} años"

    if "año" in s.lower():
        return s
    return f"{s} años" if s else "No especificado"

def es_caso_de_ortodoncia(datos: dict) -> bool:
    """
    Determina si la consulta involucra tratamiento o evaluación de ortodoncia
    (pasado, presente o futuro/planificado). Si es falso, la ficha especializada de ortodoncia
    se omite y el consentimiento informado se ubica al final de la página 2.
    """
    if not isinstance(datos, dict):
        return False

    campos_texto = [
        str(datos.get("motivo_consulta", "")),
        str(datos.get("enfermedad_actual", "")),
        str(datos.get("diagnostico", "")),
        str(datos.get("plan_tratamiento", ""))
    ]

    cita_p = datos.get("cita_programada", {})
    if isinstance(cita_p, dict):
        campos_texto.append(str(cita_p.get("motivo", "")))

    orto_eval = datos.get("evaluacion_ortodoncia", {})
    if isinstance(orto_eval, dict):
        apar = str(orto_eval.get("aparatologia", "")).lower()
        if any(k in apar for k in ["bracket", "alineador", "retenedor", "arco", "banda", "frenillo", "ortopédic", "ortopedic"]) and "sin " not in apar:
            return True

    odonto = datos.get("odontograma", [])
    if isinstance(odonto, list):
        for d in odonto:
            if isinstance(d, dict):
                hallazgos = d.get("procedimientos_o_hallazgos", [])
                h_str = ", ".join(hallazgos) if isinstance(hallazgos, list) else str(hallazgos)
                campos_texto.append(h_str)

    texto_unificado = " ".join(campos_texto).lower()

    palabras_clave_orto = [
        "ortodoncia", "ortodoncic", "ortodóncic", "bracket", "frenillo",
        "alineador", "invisalign", "apiñamiento", "diastema", "mordida abierta",
        "mordida cruzada", "mordida profunda", "arco niti", "activacion de arco",
        "activación de arco", "cambio de ligas", "elásticos intermaxilares",
        "retenedor", "disyuntor"
    ]

    return any(kw in texto_unificado for kw in palabras_clave_orto)

def crear_historia_clinica(json_data, paciente_id: int = 1):
    """
    Genera un único archivo PDF profesional:
    - Página 1: Anamnesis, filiación, antecedentes, examen y diagnóstico.
    - Página 2: Odontograma visual con polígonos a color, leyenda oficial, resumen.
                (Si no es ortodoncia, incluye al final el Consentimiento Informado).
    - Página 3 (Opcional): Ficha Especializada de Ortodoncia y Evolución si el caso lo amerita.
    """
    ruta_temp_img = None
    try:
        if isinstance(json_data, str):
            datos = json.loads(json_data)
        else:
            datos = json_data

        tiene_ortodoncia = es_caso_de_ortodoncia(datos)
        total_paginas = 3 if tiene_ortodoncia else 2

        pdf = FPDF()
        pdf.set_auto_page_break(auto=False)
        pdf.add_page()
    
        # Encabezado Ejecutivo Página 1
        pdf.set_fill_color(27, 54, 93)
        pdf.rect(0, 0, 210, 14, style='F')
        pdf.set_xy(15, 4)
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(100, 6, "BIMO  |  HISTORIA CLÍNICA ODONTOLÓGICA", align="L")

        fecha_obj = datetime.datetime.now()
        fecha_texto = fecha_obj.strftime("%d/%m/%Y - %H:%M")
        pdf.set_xy(115, 4)
        pdf.set_font("helvetica", "I", 9)
        pdf.cell(80, 6, f"Generado: {fecha_texto}", align="R")

        pdf.set_text_color(0, 0, 0)
        pdf.set_y(24)

        def card_box(x, y, w, h, titulo, lineas_o_texto):
            """Dibuja una tarjeta clínica ejecutiva con recuadro limpio y encabezado sutil."""
            pdf.set_xy(x, y)
            pdf.set_fill_color(240, 244, 249)
            pdf.set_draw_color(195, 208, 225)
            pdf.set_text_color(27, 54, 93)
            pdf.set_font("helvetica", "B", 8.2)
            pdf.cell(w, 5.0, f" {titulo}", border=1, fill=True)

            pdf.set_xy(x, y + 5.0)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(x, y + 5.0, w, h - 5.0, style='D')

            curr_y = y + 6.2
            pdf.set_text_color(35, 42, 55)

            if isinstance(lineas_o_texto, list):
                for linea in lineas_o_texto:
                    if curr_y > (y + h - 4.2):
                        break
                    linea_str = str(linea).strip()
                    if ":" in linea_str:
                        partes = linea_str.split(":", 1)
                        lbl_txt = f"- {partes[0].strip()}: "
                        val_txt = partes[1].strip()

                        pdf.set_font("helvetica", "B", 7.2)
                        w_lbl = pdf.get_string_width(lbl_txt) + 1.0

                        # Si caben en una sola línea (label corto y valor corto):
                        if w_lbl < (w * 0.48) and (pdf.get_string_width(val_txt) < (w - 6.0 - w_lbl)):
                            pdf.set_xy(x + 2.5, curr_y)
                            pdf.cell(w_lbl, 3.6, lbl_txt, border=0)
                            pdf.set_font("helvetica", "", 7.2)
                            pdf.set_xy(x + 2.5 + w_lbl, curr_y)
                            pdf.cell(w - 5.0 - w_lbl, 3.6, val_txt, border=0)
                            curr_y += 3.8
                        else:
                            # Si el valor o el label son largos, imprimir label arriba y valor abajo con indentación
                            pdf.set_xy(x + 2.5, curr_y)
                            pdf.cell(w - 5.0, 3.5, lbl_txt, border=0)
                            curr_y += 3.6
                            if curr_y > (y + h - 4.0):
                                break
                            pdf.set_xy(x + 5.5, curr_y)
                            pdf.set_font("helvetica", "", 7.2)
                            pdf.multi_cell(w - 8.0, 3.4, val_txt, border=0)
                            curr_y = max(pdf.get_y(), curr_y + 3.6) + 0.6
                    else:
                        pdf.set_xy(x + 2.5, curr_y)
                        pdf.set_font("helvetica", "", 7.2)
                        pdf.multi_cell(w - 5.0, 3.5, f"- {linea_str}", border=0)
                        curr_y = max(pdf.get_y(), curr_y + 3.6) + 0.6
            else:
                pdf.set_xy(x + 2.5, curr_y)
                pdf.set_font("helvetica", "", 7.4)
                pdf.multi_cell(w - 5.0, 3.5, str(lineas_o_texto).strip(), border=0)

        # 1. DATOS DE FILIACIÓN (Fila superior 180mm dividida internamente en 2 columnas fijas)
        filiacion = datos.get("datos_filiacion", {})
        nom_p = filiacion.get('nombre', 'No especificado')
        doc_crudo = str(filiacion.get('documento', ''))
        doc_limpio = sanitizar_cedula(doc_crudo)
        ctx_texto = str(datos.get('motivo_consulta', '')) + " " + str(datos.get('enfermedad_actual', ''))
        edad_p = formatear_edad(filiacion.get('edad', 'No especificado'), ctx_texto)
        sexo_p = filiacion.get('sexo', 'No especificado')
        tel_p = filiacion.get('contacto_emergencia') or filiacion.get('telefono') or "No especificado"
        ocup_p = filiacion.get('ocupacion', 'No especificado')
        dir_p = filiacion.get('direccion', 'No especificado')

        pdf.set_xy(15, 22)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 8.5)
        pdf.cell(180, 5.2, " 1. DATOS DE FILIACIÓN DEL PACIENTE", border=1, fill=True)
        pdf.rect(15, 27.2, 180, 29.5, style='D')

        # Columna Izquierda Filiación (x=17.5, w=84)
        pdf.set_xy(17.5, 28.5)
        pdf.set_font("helvetica", "B", 8.0)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(16, 4.2, "Paciente: ", border=0)
        pdf.set_font("helvetica", "", 8.0)
        pdf.cell(68, 4.2, str(nom_p)[:42], border=0)

        pdf.set_xy(17.5, 33.8)
        pdf.set_font("helvetica", "B", 8.0)
        pdf.cell(32, 4.2, "Documento / Cédula: ", border=0)
        pdf.set_font("helvetica", "", 8.0)
        pdf.cell(52, 4.2, str(doc_limpio)[:28], border=0)

        pdf.set_xy(17.5, 39.0)
        pdf.set_font("helvetica", "B", 8.0)
        pdf.cell(18, 4.2, "Ocupación: ", border=0)
        pdf.set_font("helvetica", "", 8.0)
        pdf.cell(66, 4.2, str(ocup_p)[:38], border=0)

        # Columna Derecha Filiación (x=105, w=88)
        pdf.set_xy(105, 28.5)
        pdf.set_font("helvetica", "B", 8.0)
        pdf.cell(20, 4.2, "Edad / Sexo: ", border=0)
        pdf.set_font("helvetica", "", 8.0)
        pdf.cell(68, 4.2, f"{edad_p}   |   {sexo_p}", border=0)

        pdf.set_xy(105, 33.8)
        pdf.set_font("helvetica", "B", 8.0)
        pdf.cell(30, 4.2, "Teléfono / Contacto: ", border=0)
        pdf.set_font("helvetica", "", 8.0)
        pdf.cell(58, 4.2, str(tel_p)[:32], border=0)

        pdf.set_xy(105, 39.0)
        pdf.set_font("helvetica", "B", 8.0)
        pdf.cell(16, 4.2, "Dirección: ", border=0)
        pdf.set_font("helvetica", "", 8.0)
        pdf.cell(72, 4.2, str(dir_p)[:42], border=0)

        # Franja Ejecutiva de Honorarios y Estado de Cuenta (Cuentas Claras)
        pagos_info = datos.get("pagos", {})
        costo_val = float(pagos_info.get("costo_total") or 0.0)
        abono_val = float(pagos_info.get("abono") or 0.0)
        saldo_val = float(pagos_info.get("saldo_pendiente") if pagos_info.get("saldo_pendiente") is not None else max(0.0, round(costo_val - abono_val, 2)))

        y_pago_bar = 44.8
        pdf.set_xy(16.0, y_pago_bar)
        if saldo_val > 0.0:
            # Ámbar suave para saldo pendiente
            pdf.set_fill_color(254, 243, 199)
            pdf.set_draw_color(245, 158, 11)
            col_badge = (180, 83, 9)
            txt_badge = f"SALDO PENDIENTE: ${saldo_val:.2f}"
        elif costo_val > 0.0 and saldo_val <= 0.0:
            # Verde esmeralda suave para cancelado
            pdf.set_fill_color(209, 250, 229)
            pdf.set_draw_color(16, 185, 129)
            col_badge = (4, 120, 87)
            txt_badge = "SALDO TOTALMENTE CANCELADO"
        else:
            # Gris azulado neutro si no se dictaron costos
            pdf.set_fill_color(241, 245, 249)
            pdf.set_draw_color(203, 213, 225)
            col_badge = (71, 85, 105)
            txt_badge = "ESTADO: AL DIA"

        pdf.rect(16.0, y_pago_bar, 178.0, 9.5, style='DF')

        # Texto de honorarios a la izquierda
        pdf.set_xy(18.5, y_pago_bar + 1.2)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.set_text_color(27, 54, 93)
        costo_txt = f"${costo_val:.2f}" if costo_val > 0 else "Por definir"
        abono_txt = f"${abono_val:.2f}" if abono_val > 0 else "$0.00"
        saldo_txt = f"${saldo_val:.2f}" if saldo_val > 0 else "$0.00"
        pdf.cell(116, 7.0, f"HONORARIOS Y CONTROL DE CUENTAS:  Costo: {costo_txt}   |   Abono: {abono_txt}   |   Saldo: {saldo_txt}", border=0)

        # Insignia / Badge destacado a la derecha
        pdf.set_xy(135.0, y_pago_bar + 1.2)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.set_text_color(*col_badge)
        pdf.cell(57.0, 7.0, f"[{txt_badge}]", align="R", border=0)

        # FILA 2: Lado a Lado (Motivo de Consulta & Enfermedad Actual)
        w_col = 88
        gap = 4
        x_col1 = 15
        x_col2 = x_col1 + w_col + gap
        y_fila2 = 59
        h_fila2 = 24

        card_box(x_col1, y_fila2, w_col, h_fila2, "2. MOTIVO DE CONSULTA", datos.get("motivo_consulta", "No especificado"))
        card_box(x_col2, y_fila2, w_col, h_fila2, "3. ENFERMEDAD ACTUAL", datos.get("enfermedad_actual", "No especificado"))

        # FILA 3: Lado a Lado (Antecedentes Médicos & Examen Estomatológico)
        y_fila3 = 86
        h_fila3 = 35

        antecedentes = datos.get("antecedentes", {})
        lineas_ant = []
        if isinstance(antecedentes, dict):
            labels = [
                ("enfermedades_sistemicas", "Enf. Sistémicas"),
                ("alergias", "Alergias"),
                ("medicamentos", "Medicamentos"),
                ("trastornos_coagulacion", "Coagulación"),
                ("cirugias_previas", "Cirugías previas")
            ]
            for k, lbl in labels:
                v = antecedentes.get(k, "No refiere")
                v_clean = v if v and v.lower() != "no especificado" else "No refiere"
                lineas_ant.append(f"{lbl}: {v_clean}")
        else:
            lineas_ant = [str(antecedentes)]

        card_box(x_col1, y_fila3, w_col, h_fila3, "4. ANTECEDENTES MÉDICOS Y SISTÉMICOS", lineas_ant)

        extra = datos.get("examen_extraoral", "Sin alteraciones evidentes")
        intra = datos.get("examen_intraoral", "Mucosas y tejidos blandos normales")
        hig = datos.get("indices_higiene", {})
        placa = hig.get("placa_bacteriana", "No evaluado") if isinstance(hig, dict) else "No evaluado"
        sangrado = hig.get("sangrado_gingival", "No evaluado") if isinstance(hig, dict) else "No evaluado"

        lineas_ex = [
            f"Examen Extraoral: {extra}",
            f"Examen Intraoral: {intra}",
            f"Placa bacteriana: {placa}",
            f"Sangrado gingival: {sangrado}"
        ]
        card_box(x_col2, y_fila3, w_col, h_fila3, "5. EXAMEN CLÍNICO ESTOMATOLÓGICO", lineas_ex)

        # FILA 4: Lado a Lado (Evaluación Oclusal/Ortodoncia & Diagnóstico y Plan)
        y_fila4 = 124
        h_fila4 = 35

        orto = datos.get("evaluacion_ortodoncia", {})
        if not isinstance(orto, dict):
            orto = {}
        lineas_orto = [
            f"Clasificación Angle: {orto.get('clase_angle', 'Clase I (Normo-oclusión)')}",
            f"Relación de Mordida: {orto.get('mordida', 'Normo-oclusión')}",
            f"Alineamiento dental: {orto.get('alineacion', 'Alineación adecuada')}",
            f"Aparatología activa: {orto.get('aparatologia', 'Sin aparatología activa')}"
        ]
        card_box(x_col1, y_fila4, w_col, h_fila4, "6. EVALUACIÓN OCLUSAL Y DE ORTODONCIA", lineas_orto)

        diag = datos.get("diagnostico", "No especificado")
        plan = datos.get("plan_tratamiento", "No especificado")
        lineas_diag = [
            f"Diagnóstico Definitivo: {diag}",
            f"Plan de Tratamiento: {plan}"
        ]
        card_box(x_col2, y_fila4, w_col, h_fila4, "8. DIAGNÓSTICO Y PLAN DE TRATAMIENTO", lineas_diag)

        # FILA 5: DETALLE DENTAL POR PIEZA (Ancho completo 180mm)
        y_fila5 = 162
        h_fila5 = 32

        odontograma_lista = datos.get("odontograma", [])
        if not isinstance(odontograma_lista, list):
            odontograma_lista = [odontograma_lista] if isinstance(odontograma_lista, dict) else []

        lineas_dientes = []
        for diente in odontograma_lista:
            pieza = diente.get("pieza_dental") or diente.get("pieza") or diente.get("diente") or ""
            fdi = extraer_fdi(pieza)
            hallazgos = diente.get("procedimientos_o_hallazgos", [])
            hallazgos_str = ", ".join(hallazgos) if isinstance(hallazgos, list) else str(hallazgos)
            etiqueta = f"Pieza {fdi}" if fdi else f"Pieza {pieza}"
            if pieza and fdi and str(pieza).strip() != fdi:
                etiqueta = f"Pieza {fdi} ({pieza})"
            if etiqueta or hallazgos_str:
                lineas_dientes.append(f"{etiqueta}: {hallazgos_str}")

        if not lineas_dientes:
            lineas_dientes = ["Sin hallazgos clínicos patológicos registrados en piezas dentales (Fórmula dental sana)."]

        card_box(15, y_fila5, 180, h_fila5, "7. DETALLE DENTAL CLÍNICO POR PIEZA", lineas_dientes)

        # Pie de página Página 1
        pdf.set_xy(15, 284)
        pdf.set_font("helvetica", "I", 7.5)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(180, 4, f"BIMO Software Odontológico  -  Página 1 de {total_paginas}  -  Expediente Clínico Confidencial", align="C")

        # ==========================================
        # PÁGINA 2: ODONTOGRAMA VISUAL DIGITALIZADO
        # ==========================================
        pdf.add_page()

        pdf.set_fill_color(27, 54, 93)
        pdf.rect(0, 0, 210, 18, style='F')
        pdf.set_xy(15, 4)
        pdf.set_font("helvetica", "B", 13)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(100, 6, "BIMO  |  ODONTOGRAMA VISUAL DIGITALIZADO", align="L")
        pdf.set_xy(115, 4)
        pdf.set_font("helvetica", "I", 9)
        pdf.cell(80, 6, f"Paciente: {filiacion.get('nombre', 'Paciente')}", align="R")

        pdf.set_text_color(0, 0, 0)
        pos_y_inicial = 26

        # Procesar odontograma sobre la imagen base
        ruta_temp_img, resumen_odonto = colorear_odontograma(odontograma_lista, ruta_base=RUTA_BASE_ODONTOGRAMA)

        if tiene_ortodoncia:
            # =========================================================================
            # CASO CON ORTODONCIA: 3 PÁGINAS TOTALES
            # PÁGINA 2: Odontograma visual completo (w=110) y panel derecho oficial
            # =========================================================================
            w_img = 110
            x_img = 15

            if ruta_temp_img and os.path.exists(ruta_temp_img):
                pdf.image(ruta_temp_img, x=x_img, y=pos_y_inicial, w=w_img)
            elif os.path.exists(RUTA_BASE_ODONTOGRAMA):
                pdf.image(RUTA_BASE_ODONTOGRAMA, x=x_img, y=pos_y_inicial, w=w_img)
            else:
                print("[PDF] Advertencia: No se pudo cargar imagen del odontograma")

            # Columna Derecha: Simbología + Resumen + Validación (w=65)
            x_r = 130
            w_r = 65

            # 1. Simbología Oficial
            pdf.set_xy(x_r, pos_y_inicial)
            pdf.set_fill_color(248, 250, 252)
            pdf.set_draw_color(205, 215, 225)
            pdf.rect(x_r, pos_y_inicial, w_r, 92, style='DF')

            pdf.set_xy(x_r, pos_y_inicial + 2.5)
            pdf.set_font("helvetica", "B", 9.5)
            pdf.set_text_color(27, 54, 93)
            pdf.cell(w_r, 5.5, "SIMBOLOGÍA OFICIAL", align="C")

            items_simbologia = [
                ((255, 75, 75), "ROJO - Patología", "Caries, fracturas, movilidad, dolor o infecciones activas a tratar."),
                ((75, 140, 255), "AZUL - Tratamiento", "Resinas, amalgamas, endodoncias y coronas en buen estado."),
                ((135, 135, 135), "GRIS - Ausente", "Exodoncias previas, agenesias o dientes perdidos."),
                ((235, 235, 235), "NATURAL - Sano", "Estructura dental sana sin alteraciones registradas.")
            ]

            curr_y = pos_y_inicial + 11
            for rgb, tit, desc in items_simbologia:
                pdf.set_fill_color(*rgb)
                pdf.set_draw_color(180, 180, 180)
                pdf.rect(x_r + 4, curr_y + 1, 4.5, 4.5, style='DF')

                pdf.set_xy(x_r + 11, curr_y)
                pdf.set_font("helvetica", "B", 8)
                pdf.set_text_color(30, 30, 30)
                pdf.cell(w_r - 14, 3.8, tit)

                pdf.set_xy(x_r + 11, curr_y + 4.2)
                pdf.set_font("helvetica", "", 7)
                pdf.set_text_color(80, 80, 80)
                pdf.multi_cell(w_r - 14, 3.2, desc)
                curr_y += 19.5

            # 2. Resumen Cuantitativo
            pos_met_y = pos_y_inicial + 96
            pdf.set_xy(x_r, pos_met_y)
            pdf.set_fill_color(238, 242, 248)
            pdf.set_draw_color(205, 215, 225)
            pdf.rect(x_r, pos_met_y, w_r, 26, style='DF')

            pdf.set_xy(x_r, pos_met_y + 2)
            pdf.set_font("helvetica", "B", 8)
            pdf.set_text_color(27, 54, 93)
            pdf.cell(w_r, 4, "RESUMEN DEL ODONTOGRAMA", align="C")

            pdf.set_xy(x_r + 4, pos_met_y + 7.5)
            pdf.set_font("helvetica", "", 7.5)
            pdf.set_text_color(40, 40, 40)
            n_rojo = resumen_odonto.get("rojo", 0)
            n_azul = resumen_odonto.get("azul", 0)
            n_gris = resumen_odonto.get("gris", 0)
            pdf.cell(w_r - 8, 3.8, f"- Patologías activas: {n_rojo} pieza(s)")
            pdf.set_xy(x_r + 4, pos_met_y + 11.5)
            pdf.cell(w_r - 8, 3.8, f"- Tratamientos previos: {n_azul} pieza(s)")
            pdf.set_xy(x_r + 4, pos_met_y + 15.5)
            pdf.cell(w_r - 8, 3.8, f"- Dientes ausentes: {n_gris} pieza(s)")

            # 3. Validación y Firma
            pos_firma_y = pos_y_inicial + 126
            pdf.set_xy(x_r, pos_firma_y)
            pdf.set_fill_color(255, 255, 255)
            pdf.set_draw_color(205, 215, 225)
            pdf.rect(x_r, pos_firma_y, w_r, 68, style='DF')

            pdf.set_xy(x_r, pos_firma_y + 2.5)
            pdf.set_font("helvetica", "B", 8.5)
            pdf.set_text_color(27, 54, 93)
            pdf.cell(w_r, 4.5, "VALIDACIÓN Y FIRMA", align="C")

            pdf.set_draw_color(160, 160, 160)
            pdf.line(x_r + 8, pos_firma_y + 47, x_r + w_r - 8, pos_firma_y + 47)

            pdf.set_xy(x_r, pos_firma_y + 49)
            pdf.set_font("helvetica", "B", 8)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(w_r, 4, "Firma del Profesional", align="C")

            pdf.set_xy(x_r, pos_firma_y + 53.5)
            pdf.set_font("helvetica", "", 7)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(w_r, 3.5, "Registro Profesional Odontológico", align="C")

            # Pie de página Página 2
            pdf.set_xy(15, 284)
            pdf.set_font("helvetica", "I", 7.5)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(180, 4, f"BIMO Software Odontológico  -  Página 2 de {total_paginas}  -  Documento Clínico Confidencial", align="C")

            # =========================================================================
            # PÁGINA 3: FICHA ESPECIALIZADA DE ORTODONCIA, ESTUDIOS Y EVOLUCIÓN CLÍNICA
            # =========================================================================
            pdf.add_page()

            # Banner superior institucional
            pdf.set_fill_color(27, 54, 93)
            pdf.rect(0, 0, 210, 18, style='F')

            pdf.set_xy(15, 4)
            pdf.set_font("helvetica", "B", 12)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(120, 6, "BIMO  |  FICHA ESPECIALIZADA DE ORTODONCIA Y ESTUDIOS", align="L")

            pdf.set_xy(135, 4)
            pdf.set_font("helvetica", "I", 9)
            pdf.cell(60, 6, f"Paciente: {nom_p}", align="R")

            pdf.set_text_color(0, 0, 0)

            # FILA 1: Hábitos Orales / Biotipo & Planificación de Ortodoncia (Y=22, h=38mm)
            y_p3_f1 = 22
            h_p3_f1 = 38

            orto_info = datos.get("evaluacion_ortodoncia", {})
            if not isinstance(orto_info, dict):
                orto_info = {}

            habitos_str = orto_info.get("habitos_orales", "No refiere hábitos perniciosos activos")
            perfil_str = orto_info.get("perfil_facial", "Perfil recto - armónico")
            biotipo_str = orto_info.get("biotipo_facial", "Mesofacial armónico")
            simetria_str = orto_info.get("simetria_facial", "Simetría frontal conservada sin desviaciones")

            lineas_habitos = [
                f"Perfil Facial: {perfil_str}",
                f"Biotipo Facial: {biotipo_str}",
                f"Simetría Facial: {simetria_str}",
                f"Hábitos Orales: {habitos_str}"
            ]
            card_box(x_col1, y_p3_f1, w_col, h_p3_f1, "1. EVALUACIÓN FACIAL Y HÁBITOS ORALES", lineas_habitos)

            lineas_fases = [
                "Fase I (Alineación): Arcos NiTi redondos (.012 a .016)",
                "Fase II (Trabajo): Arcos de Acero rectangular (.019x.025)",
                "Fase III (Finalización): Arcos TMA y elásticos intermaxilares",
                "Fase IV (Retención): Termoformado Essix y/o barra fija lingual"
            ]
            card_box(x_col2, y_p3_f1, w_col, h_p3_f1, "2. PLANIFICACIÓN Y FASES DE ORTODONCIA", lineas_fases)

            # FILA 2: Estudios Complementarios (Radiografías y Fotos Clínicas) (Y=63, h=66mm)
            y_p3_f2 = 63
            h_p3_f2 = 66

            pdf.set_xy(15, y_p3_f2)
            pdf.set_fill_color(240, 244, 249)
            pdf.set_draw_color(195, 208, 225)
            pdf.set_text_color(27, 54, 93)
            pdf.set_font("helvetica", "B", 8.2)
            pdf.cell(180, 5.0, " 3. ESTUDIOS COMPLEMENTARIOS (RADIOGRAFÍAS Y FOTOGRAFÍAS CLÍNICAS)", border=1, fill=True)

            pdf.set_xy(15, y_p3_f2 + 5.0)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(15, y_p3_f2 + 5.0, 180, h_p3_f2 - 5.0, style='D')

            from database import listar_fotos_paciente
            fotos_cargadas = []
            if paciente_id:
                try:
                    for f_item in listar_fotos_paciente(paciente_id):
                        p_img = f_item.get("ruta_archivo", "")
                        if p_img and os.path.exists(p_img):
                            fotos_cargadas.append(f_item)
                except Exception:
                    pass

            if fotos_cargadas:
                x_f = 18
                w_f = 85
                h_f = 52
                for idx_f, f_obj in enumerate(fotos_cargadas[:2]):
                    ruta_f = f_obj["ruta_archivo"]
                    cat_f = f_obj.get("categoria", "Estudio Clínico").replace("_", " ").title()
                    pdf.image(ruta_f, x=x_f, y=y_p3_f2 + 7.0, w=w_f, h=h_f)
                    pdf.set_xy(x_f, y_p3_f2 + 7.0 + h_f + 0.5)
                    pdf.set_font("helvetica", "I", 7)
                    pdf.set_text_color(80, 80, 80)
                    pdf.cell(w_f, 3.2, f"Foto {idx_f+1}: {cat_f}", align="C")
                    x_f += w_f + 8
            else:
                p_diag1 = os.path.join(BASE_DIR, "assets", "ortodoncia", "ortodoncia_fases_referencia.png")
                p_diag2 = os.path.join(BASE_DIR, "assets", "ortodoncia", "placeholder_estudio.png")
                if os.path.exists(p_diag1) and os.path.exists(p_diag2):
                    pdf.image(p_diag1, x=18, y=y_p3_f2 + 7.0, w=114, h=52)
                    pdf.image(p_diag2, x=136, y=y_p3_f2 + 7.0, w=55, h=52)
                else:
                    pdf.set_xy(20, y_p3_f2 + 25)
                    pdf.set_font("helvetica", "I", 9)
                    pdf.set_text_color(100, 100, 100)
                    pdf.cell(170, 10, "Sin estudios radiográficos adjuntados. (Puedes adjuntarlos en tiempo real desde la App Móvil)", align="C")

            # FILA 3: Registro de Evolución Clínica y Activaciones (Y=133, h=62mm)
            y_p3_f3 = 133
            h_p3_f3 = 62

            pdf.set_xy(15, y_p3_f3)
            pdf.set_fill_color(240, 244, 249)
            pdf.set_draw_color(195, 208, 225)
            pdf.set_text_color(27, 54, 93)
            pdf.set_font("helvetica", "B", 8.2)
            pdf.cell(180, 5.0, " 4. HOJA DE EVOLUCIÓN CLÍNICA Y CONTROL DE ACTIVACIONES", border=1, fill=True)

            pdf.set_xy(15, y_p3_f3 + 5.0)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(15, y_p3_f3 + 5.0, 180, h_p3_f3 - 5.0, style='D')

            col_widths = [22, 82, 26, 26, 24]
            col_headers = ["Fecha", "Procedimiento / Arco / Activación", "Higiene Oral", "Próxima Cita", "Firma Dr."]

            pdf.set_xy(15, y_p3_f3 + 5.0)
            pdf.set_fill_color(230, 238, 248)
            pdf.set_draw_color(195, 208, 225)
            pdf.set_font("helvetica", "B", 7.2)
            pdf.set_text_color(27, 54, 93)

            for i, h_name in enumerate(col_headers):
                pdf.cell(col_widths[i], 5.0, f" {h_name}", border=1, fill=True)
            pdf.ln()

            # Descripción dinámica de evolución clínica (evitar frase por defecto invariable)
            fecha_hoy_str = fecha_obj.strftime("%d/%m/%Y")
            motivo_orto = str(datos.get("motivo_consulta", "")).lower()
            plan_orto = str(datos.get("plan_tratamiento", ""))
            if any(k in motivo_orto for k in ["instalacion", "instalación", "colocacion", "colocación"]):
                desc_act = "Instalación de aparatología ortodóncica. Diagnóstico y fases aprobadas."
            elif any(k in motivo_orto for k in ["control", "activacion", "activación", "ajuste", "cambio"]):
                desc_act = f"Control ortodóncico: {plan_orto[:60]}" if plan_orto else "Control de ortodoncia y ajuste de arcos/ligaduras."
            else:
                desc_act = f"Valoración de ortodoncia: {plan_orto[:60]}" if plan_orto else "Valoración clínica y planificación ortodóncica aprobada."

            filas_evolucion = [
                (fecha_hoy_str, desc_act, "Adecuada", "1 mes", ""),
                ("", "", "", "", ""),
                ("", "", "", "", ""),
                ("", "", "", "", "")
            ]

            y_row = y_p3_f3 + 10.0
            h_row_evo = 11.5
            for f_idx, fila in enumerate(filas_evolucion):
                x_curr = 15
                for c_idx, val in enumerate(fila):
                    w_c = col_widths[c_idx]
                    pdf.rect(x_curr, y_row, w_c, h_row_evo, style='D')
                    if val:
                        pdf.set_xy(x_curr + 1.2, y_row + 1.5)
                        pdf.set_font("helvetica", "", 7.0)
                        pdf.set_text_color(40, 40, 40)
                        if c_idx == 1:
                            pdf.multi_cell(w_c - 2.4, 3.8, str(val), border=0)
                        else:
                            pdf.cell(w_c - 2.4, 6.0, str(val), border=0)
                    x_curr += w_c
                y_row += h_row_evo

            # FILA 4: Consentimiento Informado Resumido de Ortodoncia (Y=199, h=56mm)
            y_p3_f4 = 199
            h_p3_f4 = 56

            pdf.set_xy(15, y_p3_f4)
            pdf.set_fill_color(240, 244, 249)
            pdf.set_draw_color(195, 208, 225)
            pdf.set_text_color(27, 54, 93)
            pdf.set_font("helvetica", "B", 8.2)
            pdf.cell(180, 5.0, " 5. CONSENTIMIENTO INFORMADO Y COMPROMISO TERAPÉUTICO", border=1, fill=True)

            pdf.set_xy(15, y_p3_f4 + 5.0)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(15, y_p3_f4 + 5.0, 180, h_p3_f4 - 5.0, style='D')

            txt_consentimiento = (
                "El paciente o su representante legal declara haber sido informado con claridad acerca de los objetivos, "
                "fases, alternativas, cuidados y duración estimada del tratamiento ortodóncico. Se compromete a mantener una "
                "óptima higiene bucodental, evitar alimentos perjudiciales para la aparatología, portar los aditamentos y "
                "elásticos según prescripción, acudir puntualmente a los controles periódicos y usar los retenedores prescritos "
                "al finalizar el tratamiento activo para evitar recidivas."
            )

            pdf.set_xy(18, y_p3_f4 + 6.8)
            pdf.set_font("helvetica", "", 7.0)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(174, 3.4, txt_consentimiento)

            # Dos líneas de firma paralelas
            y_linea_firmas = y_p3_f4 + 40.0
            pdf.set_draw_color(160, 160, 160)
            pdf.line(22, y_linea_firmas, 92, y_linea_firmas)
            pdf.line(118, y_linea_firmas, 188, y_linea_firmas)

            pdf.set_xy(22, y_linea_firmas + 1.5)
            pdf.set_font("helvetica", "B", 7.2)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(70, 3.5, "Firma del Paciente / Tutor Legal", align="C")

            pdf.set_xy(22, y_linea_firmas + 5.0)
            pdf.set_font("helvetica", "", 7.0)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(70, 3.2, f"C.I.: {doc_limpio}", align="C")

            pdf.set_xy(118, y_linea_firmas + 1.5)
            pdf.set_font("helvetica", "B", 7.2)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(70, 3.5, "Firma del Médico Tratante", align="C")

            pdf.set_xy(118, y_linea_firmas + 5.0)
            pdf.set_font("helvetica", "", 7.0)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(70, 3.2, "Registro Profesional Odontológico", align="C")

            # Pie de página Página 3
            pdf.set_xy(15, 284)
            pdf.set_font("helvetica", "I", 7.5)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(180, 4, f"BIMO Software Odontológico  -  Página 3 de {total_paginas}  -  Documento Clínico Confidencial", align="C")

        else:
            # =========================================================================
            # CASO GENERAL (SIN ORTODONCIA): 2 PÁGINAS TOTALES
            # PÁGINA 2: Odontograma visual + Simbología + Resumen + Consentimiento General
            # =========================================================================
            # Columna Izquierda: Odontograma Gráfico Compacto (w=90, h=138mm)
            w_img = 90
            x_img = 15

            if ruta_temp_img and os.path.exists(ruta_temp_img):
                pdf.image(ruta_temp_img, x=x_img, y=pos_y_inicial, w=w_img)
            elif os.path.exists(RUTA_BASE_ODONTOGRAMA):
                pdf.image(RUTA_BASE_ODONTOGRAMA, x=x_img, y=pos_y_inicial, w=w_img)
            else:
                print("[PDF] Advertencia: No se pudo cargar imagen del odontograma")

            # Columna Derecha Superior (x=110, w=85)
            x_r = 110
            w_r = 85

            # 1. Simbología Oficial (h=84mm)
            pdf.set_xy(x_r, pos_y_inicial)
            pdf.set_fill_color(248, 250, 252)
            pdf.set_draw_color(205, 215, 225)
            pdf.rect(x_r, pos_y_inicial, w_r, 84, style='DF')

            pdf.set_xy(x_r, pos_y_inicial + 2.0)
            pdf.set_font("helvetica", "B", 9.0)
            pdf.set_text_color(27, 54, 93)
            pdf.cell(w_r, 5.0, "SIMBOLOGÍA OFICIAL", align="C")

            items_simbologia = [
                ((255, 75, 75), "ROJO - Patología", "Caries, fracturas, movilidad, dolor o infecciones activas."),
                ((75, 140, 255), "AZUL - Tratamiento", "Resinas, amalgamas, endodoncias y coronas en buen estado."),
                ((135, 135, 135), "GRIS - Ausente", "Exodoncias previas, agenesias o piezas ausentes."),
                ((235, 235, 235), "NATURAL - Sano", "Estructura dental sana sin alteraciones registradas.")
            ]

            curr_y = pos_y_inicial + 9.5
            for rgb, tit, desc in items_simbologia:
                pdf.set_fill_color(*rgb)
                pdf.set_draw_color(180, 180, 180)
                pdf.rect(x_r + 4, curr_y + 1, 4.2, 4.2, style='DF')

                pdf.set_xy(x_r + 11, curr_y)
                pdf.set_font("helvetica", "B", 7.8)
                pdf.set_text_color(30, 30, 30)
                pdf.cell(w_r - 14, 3.6, tit)

                pdf.set_xy(x_r + 11, curr_y + 3.8)
                pdf.set_font("helvetica", "", 6.8)
                pdf.set_text_color(80, 80, 80)
                pdf.multi_cell(w_r - 14, 3.0, desc)
                curr_y += 18.0

            # 2. Resumen Cuantitativo (h=47mm, Y=113)
            pos_met_y = pos_y_inicial + 87
            pdf.set_xy(x_r, pos_met_y)
            pdf.set_fill_color(238, 242, 248)
            pdf.set_draw_color(205, 215, 225)
            pdf.rect(x_r, pos_met_y, w_r, 47, style='DF')

            pdf.set_xy(x_r, pos_met_y + 2.5)
            pdf.set_font("helvetica", "B", 8.2)
            pdf.set_text_color(27, 54, 93)
            pdf.cell(w_r, 4.5, "RESUMEN DEL ODONTOGRAMA", align="C")

            n_rojo = resumen_odonto.get("rojo", 0)
            n_azul = resumen_odonto.get("azul", 0)
            n_gris = resumen_odonto.get("gris", 0)
            n_tot = resumen_odonto.get("total_evaluadas", 0)

            pdf.set_font("helvetica", "", 7.5)
            pdf.set_text_color(40, 40, 40)
            pdf.set_xy(x_r + 5, pos_met_y + 9.0)
            pdf.cell(w_r - 10, 4.0, f"- Patologías activas a tratar: {n_rojo}")
            pdf.set_xy(x_r + 5, pos_met_y + 14.5)
            pdf.cell(w_r - 10, 4.0, f"- Tratamientos previos realizados: {n_azul}")
            pdf.set_xy(x_r + 5, pos_met_y + 20.0)
            pdf.cell(w_r - 10, 4.0, f"- Piezas ausentes / perdidas: {n_gris}")
            pdf.set_xy(x_r + 5, pos_met_y + 25.5)
            pdf.cell(w_r - 10, 4.0, f"- Total piezas evaluadas: {n_tot}")
            pdf.set_xy(x_r + 5, pos_met_y + 32.0)
            pdf.set_font("helvetica", "I", 7.0)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(w_r - 10, 3.5, "Fórmula dental permanente estandarizada FDI")

            # Bloque Inferior: Consentimiento Informado y Compromiso Terapéutico General (Y=167, h=108mm)
            y_consent = 167
            pdf.set_xy(15, y_consent)
            pdf.set_fill_color(240, 244, 249)
            pdf.set_draw_color(195, 208, 225)
            pdf.set_text_color(27, 54, 93)
            pdf.set_font("helvetica", "B", 8.2)
            pdf.cell(180, 5.0, " 3. CONSENTIMIENTO INFORMADO Y COMPROMISO TERAPÉUTICO", border=1, fill=True)

            pdf.set_xy(15, y_consent + 5.0)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(15, y_consent + 5.0, 180, 105.0, style='D')

            txt_consentimiento_gen = (
                "El paciente o su representante legal declara haber sido informado con claridad acerca de su estado de salud bucodental, "
                "diagnóstico clínico, alternativas y cuidados necesarios para los tratamientos planificados. Se compromete a seguir las "
                "indicaciones terapéuticas, mantener una adecuada higiene oral, acudir puntualmente a sus citas de control y comunicar cualquier "
                "eventualidad para garantizar el éxito y la durabilidad de los procedimientos realizados."
            )

            pdf.set_xy(18, y_consent + 7.5)
            pdf.set_font("helvetica", "", 7.2)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(174, 3.6, txt_consentimiento_gen)

            # Dos líneas de firma paralelas
            y_firmas_p2 = y_consent + 65.0
            pdf.set_draw_color(160, 160, 160)
            pdf.line(22, y_firmas_p2, 92, y_firmas_p2)
            pdf.line(118, y_firmas_p2, 188, y_firmas_p2)

            pdf.set_xy(22, y_firmas_p2 + 1.5)
            pdf.set_font("helvetica", "B", 7.2)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(70, 3.5, "Firma del Paciente / Tutor Legal", align="C")

            pdf.set_xy(22, y_firmas_p2 + 5.0)
            pdf.set_font("helvetica", "", 7.0)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(70, 3.2, f"C.I.: {doc_limpio}", align="C")

            pdf.set_xy(118, y_firmas_p2 + 1.5)
            pdf.set_font("helvetica", "B", 7.2)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(70, 3.5, "Firma del Médico Tratante", align="C")

            pdf.set_xy(118, y_firmas_p2 + 5.0)
            pdf.set_font("helvetica", "", 7.0)
            pdf.set_text_color(90, 90, 90)
            pdf.cell(70, 3.2, "Registro Profesional Odontológico", align="C")

            # Pie de página Página 2
            pdf.set_xy(15, 284)
            pdf.set_font("helvetica", "I", 7.5)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(180, 4, f"BIMO Software Odontológico  -  Página 2 de {total_paginas}  -  Documento Clínico Confidencial", align="C")

        # ==========================================
        # RUTEO ANTI-HOMÓNIMOS Y GUARDADO DEL PDF
        # ==========================================
        nombre_paciente = filiacion.get('nombre', 'Paciente_Desconocido')
        nombre_limpio_carpeta = re.sub(r'[^a-zA-Z0-9_]', '', nombre_paciente.replace(' ', '_')) or "Paciente"
        
        # Clasificación por edad: Pediátrico SOLO si se especifica estrictamente entre 1 y 17 años
        if not edad_p or str(edad_p).strip().lower() in ('0', 'no especificado', 'n/e', 'none', ''):
            if paciente_id:
                from database import obtener_paciente_por_id
                p_db = obtener_paciente_por_id(paciente_id)
                if p_db and p_db.get("edad"):
                    edad_num = int(p_db["edad"])
                    categoria_edad = "Pacientes_Pediatricos" if edad_num < 18 else "Pacientes_Adultos"
                else:
                    edad_num = 25
                    categoria_edad = "Pacientes_Adultos"
            else:
                edad_num = 25
                categoria_edad = "Pacientes_Adultos"
        else:
            numeros = re.findall(r'\d+', str(edad_p))
            if numeros and int(numeros[0]) > 0:
                edad_num = int(numeros[0])
                categoria_edad = "Pacientes_Pediatricos" if edad_num < 18 else "Pacientes_Adultos"
            else:
                if paciente_id:
                    from database import obtener_paciente_por_id
                    p_db = obtener_paciente_por_id(paciente_id)
                    if p_db and p_db.get("edad"):
                        edad_num = int(p_db["edad"])
                        categoria_edad = "Pacientes_Pediatricos" if edad_num < 18 else "Pacientes_Adultos"
                    else:
                        edad_num = 25
                        categoria_edad = "Pacientes_Adultos"
                else:
                    edad_num = 25
                    categoria_edad = "Pacientes_Adultos"

        # Ruteo anti-homónimos por ID único: [Nombre]_[Edad]_anos_ID[paciente_id]
        id_str = f"ID{paciente_id}"
        nombre_carpeta = f"{nombre_limpio_carpeta}_{edad_num}_anos_{id_str}"
        ruta_carpeta = os.path.join(BASE_DIR, "Pacientes", categoria_edad, nombre_carpeta)
        os.makedirs(ruta_carpeta, exist_ok=True)

        # Nombre de archivo corto: Consulta_[NombreCorto]_[Edad]a_[Fecha_Corta].pdf
        nombre_archivo = generar_nombre_archivo_corto(nombre_paciente, edad_num, fecha_obj)
        ruta_final = os.path.join(ruta_carpeta, nombre_archivo)

        # Generar un único PDF con la historia y el odontograma
        pdf.output(ruta_final)
        print(f"[OK] Historia clínica unificada con odontograma guardada en: {ruta_final}")

        # Limpieza de archivo temporal
        if ruta_temp_img and os.path.exists(ruta_temp_img):
            try:
                os.remove(ruta_temp_img)
            except Exception:
                pass

        return ruta_final

    except Exception as e:
        print(f"[ERROR] Error al construir el PDF: {e}")
        if ruta_temp_img and os.path.exists(ruta_temp_img):
            try:
                os.remove(ruta_temp_img)
            except Exception:
                pass
        return None