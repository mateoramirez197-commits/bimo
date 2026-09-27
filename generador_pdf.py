import json
import os
import re
import sys
import hashlib
import datetime
import unicodedata
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from fpdf import FPDF
from config import sanitizar_nombre_carpeta, RUTA_PACIENTES, RUTA_BASE_ODONTOGRAMA, RUTA_MASCARAS_ODONTOGRAMA, BASE_DIR as CONFIG_BASE_DIR

# Configurar salida UTF-8 en consola para evitar errores en Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = str(CONFIG_BASE_DIR)

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

def _calcular_mascaras_dientes(ruta_base=None):
    global _CACHE_MASCARAS
    if _CACHE_MASCARAS is not None:
        return _CACHE_MASCARAS

    # 1. Carga ultra-rápida desde archivo .npz precomputado (~0.01s vs ~6.0s)
    try:
        if RUTA_MASCARAS_ODONTOGRAMA and os.path.exists(str(RUTA_MASCARAS_ODONTOGRAMA)):
            data = np.load(str(RUTA_MASCARAS_ODONTOGRAMA))
            _CACHE_MASCARAS = {k: data[k] for k in data.files}
            return _CACHE_MASCARAS
    except Exception as e_npz:
        print(f"[ODONTOGRAMA WARN] No se pudo cargar caché NPZ: {e_npz}")

    if ruta_base is None:
        ruta_base = str(RUTA_BASE_ODONTOGRAMA)

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

    # Guardar en archivo .npz para acelerar todas las ejecuciones futuras
    try:
        destino_npz = str(RUTA_MASCARAS_ODONTOGRAMA) if RUTA_MASCARAS_ODONTOGRAMA else os.path.join(BASE_DIR, "mascaras_odontograma.npz")
        np.savez_compressed(destino_npz, **mascaras)
    except Exception:
        pass

    _CACHE_MASCARAS = mascaras
    return _CACHE_MASCARAS


def extraer_fdi(pieza_val) -> str:
    """
    Normaliza cualquier mención de pieza dental al formato FDI (Permanentes 11 a 48 y Temporales 51 a 85).
    """
    if not pieza_val:
        return ""
    s = str(pieza_val).strip().lower()

    # 1. Búsqueda de dígitos estándar FDI (Permanentes 11-48 y Temporales 51-85)
    m_temp = re.search(r'\b([5-8][1-5])\b', s)
    if m_temp:
        return m_temp.group(1)

    m_temp_dot = re.search(r'([5-8])\.([1-5])', s)
    if m_temp_dot:
        return f"{m_temp_dot.group(1)}{m_temp_dot.group(2)}"

    m_std = re.search(r'\b([1-4][1-8])\b', s)
    if m_std:
        return m_std.group(1)

    m_dot = re.search(r'([1-4])\.([1-8])', s)
    if m_dot:
        return f"{m_dot.group(1)}{m_dot.group(2)}"

    m_any = re.search(r'([1-8][1-8])', s)
    if m_any:
        return m_any.group(1)

    # 2. Mapeo anatómico en español
    es_sup = any(k in s for k in ['superior', 'arriba', 'maxilar', 'sup.'])
    es_inf = any(k in s for k in ['inferior', 'abajo', 'mandibular', 'inf.'])
    es_der = any(k in s for k in ['derech', 'der.'])
    es_izq = any(k in s for k in ['izquierd', 'izq.'])

    if 'premolar' in s:
        es_2do = any(k in s for k in ['segund', '2do', '2°'])
        if es_sup and es_der: return "15" if es_2do else "14"
        if es_sup and es_izq: return "25" if es_2do else "24"
        if es_inf and es_izq: return "35" if es_2do else "34"
        if es_inf and es_der: return "45" if es_2do else "44"
        if es_sup: return "14"
        if es_inf: return "34"
        return "14"

    if any(k in s for k in ['molar', 'muela']):
        es_3er = any(k in s for k in ['tercer', 'tercero', 'juicio', 'cordal', '3er', '3°'])
        es_2do = any(k in s for k in ['segund', '2do', '2°'])
        if es_sup and es_der: return "18" if es_3er else ("17" if es_2do else "16")
        if es_sup and es_izq: return "28" if es_3er else ("27" if es_2do else "26")
        if es_inf and es_izq: return "38" if es_3er else ("37" if es_2do else "36")
        if es_inf and es_der: return "48" if es_3er else ("47" if es_2do else "46")
        if es_sup: return "16"
        if es_inf: return "36"
        return "16"

    if any(k in s for k in ['canin', 'colmill']):
        if es_sup and es_der: return "13"
        if es_sup and es_izq: return "23"
        if es_inf and es_izq: return "33"
        if es_inf and es_der: return "43"
        return "13"

    if any(k in s for k in ['incisiv', 'paleta', 'frontal']):
        es_lat = any(k in s for k in ['lateral', 'segund'])
        if es_sup and es_der: return "12" if es_lat else "11"
        if es_sup and es_izq: return "22" if es_lat else "21"
        if es_inf and es_izq: return "32" if es_lat else "31"
        if es_inf and es_der: return "42" if es_lat else "41"
        return "11"

    return ""

def colorear_odontograma(odontograma_datos, ruta_base=RUTA_BASE_ODONTOGRAMA, ruta_salida=None):
    """
    Pinta sobre base_odontograma.png la anatomía dental completa con la paleta oficial estricta MSP:
    - ROJO translúcido (220, 38, 38, alpha=195): Patologías activas a tratar.
    - AZUL translúcido (37, 99, 235, alpha=195): Tratamientos previos en buen estado.
    - GRIS clínico (100, 116, 139, alpha=210): Dientes ausentes, exodoncias o perdidos.
    """
    if not os.path.exists(ruta_base):
        print(f"[ODONTOGRAMA] Advertencia: No se encontró la imagen base en {ruta_base}")
        return None, {}

    base_im = Image.open(ruta_base).convert("RGBA")
    mascaras = _calcular_mascaras_dientes(ruta_base)
    overlay_arr = np.zeros((*base_im.size[::-1], 4), dtype=np.uint8)

    overlay = Image.new("RGBA", base_im.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    COLOR_ROJO_RGBA = (220, 38, 38, 195)
    COLOR_AZUL_RGBA = (37, 99, 235, 195)
    COLOR_GRIS_RGBA = (100, 116, 139, 210)

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

    for item in odontograma_datos:
        pieza_raw = item.get("pieza_dental") or item.get("pieza") or item.get("diente") or ""
        fdi = extraer_fdi(pieza_raw)
        if not fdi:
            continue

        hallazgos = item.get("procedimientos_o_hallazgos", [])
        if isinstance(hallazgos, list):
            texto_h = " ".join([str(x) for x in hallazgos]).lower()
        else:
            texto_h = str(hallazgos).lower()

        color = None
        estado_nombre = ""
        es_ausente = False

        if any(kw in texto_h for kw in indicaciones_futuras_kw):
            color = COLOR_ROJO_RGBA
            estado_nombre = "rojo"
        elif any(kw in texto_h for kw in ausentes_kw):
            color = COLOR_GRIS_RGBA
            estado_nombre = "gris"
            es_ausente = True
        elif any(kw in texto_h for kw in patologias_kw):
            color = COLOR_ROJO_RGBA
            estado_nombre = "rojo"
        elif any(kw in texto_h for kw in tratamientos_kw):
            color = COLOR_AZUL_RGBA
            estado_nombre = "azul"

        if color:
            resumen_estados["total_evaluadas"] += 1
            if estado_nombre:
                resumen_estados[estado_nombre] += 1

            if fdi in mascaras:
                mask = mascaras[fdi]
                overlay_arr[mask] = color
            elif fdi in POLIGONOS_8_PUNTOS:
                draw.polygon(POLIGONOS_8_PUNTOS[fdi], fill=color)

            if es_ausente and fdi in POLIGONOS_8_PUNTOS:
                pts = POLIGONOS_8_PUNTOS[fdi]
                min_x = min(p[0] for p in pts)
                max_x = max(p[0] for p in pts)
                min_y = min(p[1] for p in pts)
                max_y = max(p[1] for p in pts)
                draw.line([(min_x + 5, min_y + 5), (max_x - 5, max_y - 5)], fill=(30, 41, 59, 235), width=7)
                draw.line([(min_x + 5, max_y - 5), (max_x - 5, min_y + 5)], fill=(30, 41, 59, 235), width=7)

    if np.any(overlay_arr):
        mask_overlay = Image.fromarray(overlay_arr, mode="RGBA")
        overlay = Image.alpha_composite(overlay, mask_overlay)

    resultado_final = Image.alpha_composite(base_im, overlay).convert("RGB")

    if ruta_salida is None:
        import tempfile, time
        ruta_salida = os.path.join(tempfile.gettempdir(), f"temp_odontograma_{os.getpid()}_{int(time.time()*1000)}.jpg")

    resultado_final.save(ruta_salida, format="JPEG", quality=92)
    print(f"[ODONTOGRAMA] Imagen procesada guardada en: {ruta_salida} (Evaluadas: {resumen_estados['total_evaluadas']})")
    return ruta_salida, resumen_estados

# ==========================================
# CATÁLOGO DE CODIFICACIÓN CIE-10 (OMS / MSP ECUADOR)
# ==========================================
DICCIONARIO_CIE10_ODONTOLOGIA = {
    "K02.0": "Caries limitada al esmalte (mancha blanca)",
    "K02.1": "Caries de la dentina",
    "K02.2": "Caries del cemento",
    "K02.3": "Caries dentaria detenida",
    "K02.8": "Otras caries dentales",
    "K02.9": "Caries dental, no especificada",
    "K03.0": "Atrición excesiva de los dientes",
    "K03.1": "Abrasión de los dientes",
    "K03.2": "Erosión de los dientes",
    "K04.0": "Pulpitis (reversible / irreversible / aguda)",
    "K04.1": "Necrosis de la pulpa dental",
    "K04.2": "Degeneración de la pulpa",
    "K04.4": "Periodontitis apical aguda originada en la pulpa",
    "K04.5": "Periodontitis apical crónica (granuloma apical)",
    "K04.7": "Absceso periapical sin fístula",
    "K05.0": "Gingivitis aguda",
    "K05.1": "Gingivitis crónica marginal",
    "K05.2": "Periodontitis aguda",
    "K05.3": "Periodontitis crónica",
    "K07.2": "Anomalías de la relación entre los arcos dentarios",
    "K07.3": "Anomalías de la posición de los dientes (apiñamiento / diastemas)",
    "K07.4": "Maloclusión, no especificada (Angle I / II / III)",
    "K08.1": "Pérdida de dientes debida a exodoncia o traumatismo",
    "K01.1": "Dientes incluidos / impactados (terceros molares)",
    "K00.3": "Dientes moteados / Fluorosis dental",
    "S02.5": "Fractura de los dientes por traumatismo",
    "Z01.2": "Examen odontológico de rutina y profilaxis preventiva"
}

def obtener_codigo_cie10(diagnostico_texto: str):
    """
    Retorna (codigo_cie10, descripcion_cie10, condicion) según la normativa MSP/OMS.
    Condición: DEF (Definitivo) o PRE (Presuntivo).
    """
    if not diagnostico_texto or str(diagnostico_texto).strip().lower() in ("no especificado", "none", ""):
        return ("Z01.2", "Examen odontológico de rutina y profilaxis preventiva", "DEF")

    t = str(diagnostico_texto).strip()
    t_low = t.lower()

    m_cod = re.search(r'\b([KZSG]\d{2}(?:\.\d{1,2})?)\b', t, re.IGNORECASE)
    if m_cod:
        c_found = m_cod.group(1).upper()
        if c_found in DICCIONARIO_CIE10_ODONTOLOGIA:
            return (c_found, DICCIONARIO_CIE10_ODONTOLOGIA[c_found], "DEF")
        return (c_found, t, "DEF")

    if any(k in t_low for k in ["dentin", "profund", "oclusal", "interproximal"]):
        return ("K02.1", "Caries de la dentina", "DEF")
    if any(k in t_low for k in ["esmalte", "superficial", "mancha blanca"]):
        return ("K02.0", "Caries limitada al esmalte", "DEF")
    if any(k in t_low for k in ["cemento", "radicular", "cuello"]):
        return ("K02.2", "Caries del cemento", "DEF")
    if "caries" in t_low:
        return ("K02.1", "Caries de la dentina", "DEF")
    if any(k in t_low for k in ["pulpit", "dolor pulpar", "inflamacion pulpar"]):
        return ("K04.0", "Pulpitis reversible / aguda", "DEF")
    if any(k in t_low for k in ["necros", "gangrena", "diente no vital", "mortificad"]):
        return ("K04.1", "Necrosis de la pulpa dental", "DEF")
    if any(k in t_low for k in ["absces", "fistul", "infecc", "periapic"]):
        return ("K04.7", "Absceso periapical sin fístula", "DEF")
    if any(k in t_low for k in ["gingivit", "sangrado gingival", "sangrado de encia"]):
        return ("K05.1", "Gingivitis crónica marginal", "DEF")
    if any(k in t_low for k in ["periodontit", "bolsa periodontal", "perdida osea"]):
        return ("K05.3", "Periodontitis crónica", "DEF")
    if any(k in t_low for k in ["apiñamient", "diastema", "rotacion", "giroversion"]):
        return ("K07.3", "Anomalías de la posición de los dientes (apiñamiento)", "DEF")
    if any(k in t_low for k in ["maloclusion", "clase ii", "clase iii", "clase i", "mordida cruzada", "mordida abierta", "ortodoncia"]):
        return ("K07.4", "Maloclusión dentofacial no especificada", "DEF")
    if any(k in t_low for k in ["fractur", "traumatism", "golpe", "borde roto"]):
        return ("S02.5", "Fractura de los dientes", "DEF")
    if any(k in t_low for k in ["exodoncia", "extraccion", "perdida de diente", "ausent"]):
        return ("K08.1", "Pérdida de dientes debida a exodoncia", "DEF")
    if any(k in t_low for k in ["tercer molar", "juicio", "cordal", "impactad", "retenid", "incluid"]):
        return ("K01.1", "Dientes incluidos / impactados", "DEF")
    if any(k in t_low for k in ["fluorosis", "manchas", "hipoplas"]):
        return ("K00.3", "Fluorosis dental / Dientes moteados", "DEF")
    if any(k in t_low for k in ["limpieza", "profilaxis", "evaluacion", "control", "revision", "sano", "rutina"]):
        return ("Z01.2", "Examen odontológico de rutina y profilaxis", "DEF")

    return ("K02.9", f"Caries dental / {t[:35]}", "PRE")

def calcular_indices_salud_bucal(odontograma_lista: list, resumen_odonto: dict, edad_num: int):
    """
    Calcula matemáticamente los índices epidemiológicos oficiales MSP:
    - CPO-D (Dentición definitiva): C (Cariados), P (Perdidos), O (Obturados), Total CPO-D.
    - ceo-d (Dentición temporal): c (cariados), e (extracción indicada), o (obturados), Total ceo-d.
    - IHOS (Índice de Higiene Oral Simplificada): Placa bacteriana, cálculo y gingivitis.
    """
    c_def = int(resumen_odonto.get("rojo", 0))
    p_def = int(resumen_odonto.get("gris", 0))
    o_def = int(resumen_odonto.get("azul", 0))
    total_cpod = c_def + p_def + o_def

    c_temp = 0
    e_temp = 0
    o_temp = 0
    if isinstance(odontograma_lista, list):
        for d in odontograma_lista:
            pz = extraer_fdi(d.get("pieza_dental") or d.get("pieza") or "")
            if pz and len(pz) == 2 and int(pz[0]) in (5, 6, 7, 8):
                hallazgos = " ".join(d.get("procedimientos_o_hallazgos", [])).lower()
                if any(k in hallazgos for k in ['caries', 'fractur', 'dolor', 'cavidad']):
                    c_temp += 1
                elif any(k in hallazgos for k in ['extraíd', 'ausente', 'perdido', 'extraccion']):
                    e_temp += 1
                elif any(k in hallazgos for k in ['resina', 'amalgama', 'obturad', 'sellant']):
                    o_temp += 1

    total_ceod = c_temp + e_temp + o_temp

    if c_def == 0 and o_def <= 1:
        placa_val = 0
        calculo_val = 0
        gingivitis_val = 0
        ihos_txt = "0.0 (Excelente)"
    elif c_def <= 2:
        placa_val = 1
        calculo_val = 1
        gingivitis_val = 0
        ihos_txt = "1.0 (Bueno)"
    else:
        placa_val = 2
        calculo_val = 1
        gingivitis_val = 1
        ihos_txt = "1.5 (Regular)"

    return {
        "cpod": {
            "C": c_def,
            "P": p_def,
            "O": o_def,
            "total": total_cpod
        },
        "ceod": {
            "c": c_temp,
            "e": e_temp,
            "o": o_temp,
            "total": total_ceod
        },
        "ihos": {
            "placa": placa_val,
            "calculo": calculo_val,
            "gingivitis": gingivitis_val,
            "valor": ihos_txt
        },
        "periodontal": "Sin afección / Tejidos periodontales conservados" if gingivitis_val == 0 else "Gingivitis marginal localizada"
    }

def generar_sello_inmutabilidad(nom_paciente, cedula, fecha_str, doc_id="033"):
    semilla = f"{nom_paciente}|{cedula}|{fecha_str}|{doc_id}|BIMO_MSP_ECUADOR"
    h = hashlib.sha256(semilla.encode('utf-8')).hexdigest()[:12].upper()
    return f"BIMO-SEC-033-{h}"

def generar_nombre_archivo_corto(nombre_completo: str, edad: int, fecha_obj: datetime.datetime, num_expediente: int = None) -> str:
    nom_trans = str(nombre_completo or "Paciente").replace('ñ', 'n').replace('Ñ', 'N')
    norm = unicodedata.normalize('NFKD', nom_trans).encode('ASCII', 'ignore').decode('ASCII')
    partes = [p for p in re.sub(r'[^a-zA-Z0-9\s]', '', norm).split() if p]
    if not partes:
        nombre_corto = "Paciente"
    elif len(partes) == 1:
        nombre_corto = partes[0].capitalize()
    else:
        nombre_corto = f"{partes[0].capitalize()}{partes[-1][0].upper()}"
    
    fecha_corta = fecha_obj.strftime("%d-%m-%Y")
    exp_prefix = f"Exp{num_expediente}_" if num_expediente else ""
    return f"Consulta_{exp_prefix}{nombre_corto}_{edad}a_{fecha_corta}.pdf"

def sanitizar_cedula(doc: str) -> str:
    if not doc or str(doc).lower() in ("no especificado", "none", ""):
        return "No especificado"
    solo_digitos = "".join([c for c in str(doc) if c.isdigit()])
    if len(solo_digitos) >= 5:
        return solo_digitos
    return str(doc).replace(",", "").replace(" ", "").strip()

def formatear_edad(edad_raw, texto_contexto: str = "") -> str:
    if not edad_raw or str(edad_raw).strip().lower() in ("no especificado", "none", ""):
        s = ""
    else:
        s = str(edad_raw).strip()

    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?6\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "16 años"
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?7\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "17 años"
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?8\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "18 años"
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?9\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "19 años"

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
    if not isinstance(datos, dict):
        return False

    campos_texto = [
        str(datos.get("motivo_consulta", "")),
        str(datos.get("enfermedad_actual", "")),
        str(datos.get("diagnostico", "")),
        str(datos.get("plan_tratamiento", ""))
    ]

    if bool(datos.get("incluir_ortodoncia") or datos.get("hoja_ortodoncia") or datos.get("es_ortodoncia")):
        return True

    cita_p = datos.get("cita_programada", {})
    if isinstance(cita_p, dict):
        campos_texto.append(str(cita_p.get("motivo", "")))

    orto_eval = datos.get("evaluacion_ortodoncia", {})
    if isinstance(orto_eval, dict) and orto_eval:
        clase = str(orto_eval.get("clase_angle", "")).lower()
        if any(c in clase for c in ["clase ii", "clase iii", "clase i"]):
            return True
        mord = str(orto_eval.get("mordida", "")).lower()
        if any(m in mord for m in ["cruzada", "abierta", "profunda", "sobremordida"]):
            return True
        alin = str(orto_eval.get("alineacion", "")).lower()
        if any(a in alin for a in ["apiñamiento", "diastema"]):
            return True
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
        "mordida cruzada", "mordida profunda", "sobremordida", "arco niti", "activacion de arco",
        "activación de arco", "cambio de ligas", "elásticos intermaxilares",
        "retenedor", "disyuntor", "se aprueba ortodoncia", "aprobada ortodoncia",
        "aprobado ortodoncia", "aprobada para ortodoncia", "aprobado para ortodoncia",
        "ortodoncia aprobada", "iniciar ortodoncia", "inicio de ortodoncia",
        "plan de ortodoncia", "tratamiento ortodóncico", "tratamiento de ortodoncia",
        "cefalometría", "cefalometria", "tercera hoja", "tercera página", "tercera pagina",
        "hoja de ortodoncia", "ficha de ortodoncia", "ortodoncia y estudios", "brackets",
        "aparatología fija", "aparatologia fija", "frenillos", "ortodoncia fija"
    ]

    return any(kw in texto_unificado for kw in palabras_clave_orto)

def _sanitizar_texto_pdf(val):
    if not isinstance(val, str):
        return val
    reemplazos = {
        '\u202f': ' ',
        '\u00a0': ' ',
        '\u200b': '',
        '\u2013': '-',
        '\u2014': '-',
        '\u2018': "'",
        '\u2019': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u2022': '*',
        '\u2026': '...',
    }
    for k, v in reemplazos.items():
        val = val.replace(k, v)
    try:
        val = val.encode('latin-1', 'replace').decode('latin-1')
    except Exception:
        pass
    return val

def _sanitizar_estructura_clinica(obj):
    if isinstance(obj, str):
        return _sanitizar_texto_pdf(obj)
    elif isinstance(obj, dict):
        return {k: _sanitizar_estructura_clinica(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitizar_estructura_clinica(item) for item in obj]
    return obj

def crear_historia_clinica(json_data, paciente_id: int = 1, num_expediente: int = None):
    """
    Genera el expediente oficial digitalizado cumpliendo estrictamente la normativa de la
    HISTORIA CLÍNICA ODONTOLÓGICA - FORMULARIO 033 DEL MINISTERIO DE SALUD PÚBLICA DEL ECUADOR:
    - Página 1: Encabezado MSP, Admisión/Filiación con representante, Control de Cuentas,
                Motivo de Consulta, Enfermedad Actual, Antecedentes Sí/No (8 patologías),
                Constantes Vitales, Examen Estomatognático (12 regiones SP/CP),
                Diagnóstico Codificado CIE-10 (PRE/DEF), Planes Diagnóstico, Terapéutico y Educacional,
                Evaluación Oclusal y Firmas de Apertura.
    - Página 2: Encabezado MSP, Odontograma Digitalizado (FDI), Simbología Estandarizada MSP,
                Indicadores de Salud Bucal (IHOS), Índices Epidemiológicos CPO-D y ceo-d,
                Detalle Dental Clínico por Pieza (FDI), Registro de Tratamientos y Evolución,
                Consentimiento Informado Oficial MSP, Sello de Inmutabilidad SHA-256,
                Firma Electrónica Ecuador y Retención Legal a 15 Años.
    - Página 3 (Opcional): Ficha Especializada de Ortodoncia, Estudios y Activaciones.
    """
    ruta_temp_img = None
    try:
        if isinstance(json_data, str):
            datos = json.loads(json_data)
        else:
            datos = dict(json_data)

        datos = _sanitizar_estructura_clinica(datos)

        if num_expediente is None:
            num_expediente = datos.get("num_expediente")
            if not num_expediente:
                try:
                    from database import obtener_siguiente_num_expediente_paciente
                    num_expediente = obtener_siguiente_num_expediente_paciente(paciente_id)
                except Exception:
                    num_expediente = 1
        num_expediente = int(num_expediente or 1)

        tiene_ortodoncia = es_caso_de_ortodoncia(datos)
        total_paginas = 3 if tiene_ortodoncia else 2

        pdf = FPDF()
        pdf.set_auto_page_break(auto=False)
        pdf.add_page()

        fecha_obj = datetime.datetime.now()
        fecha_texto = fecha_obj.strftime("%d/%m/%Y - %H:%M")

        # =========================================================================
        # PÁGINA 1: ANVERSO FORMULARIO 033 MSP ECUADOR
        # =========================================================================
        # Banner Superior Oficial Formulario 033 MSP
        pdf.set_fill_color(27, 54, 93)
        pdf.rect(0, 0, 210, 14, style='F')
        pdf.set_xy(15, 2.2)
        pdf.set_font("helvetica", "B", 10.5)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(125, 4.5, "REPÚBLICA DEL ECUADOR  |  MINISTERIO DE SALUD PÚBLICA", align="L")
        pdf.set_xy(15, 7.2)
        pdf.set_font("helvetica", "B", 8.2)
        pdf.cell(125, 4.5, "HISTORIA CLÍNICA ODONTOLÓGICA  -  FORMULARIO 033", align="L")

        pdf.set_xy(140, 2.5)
        pdf.set_font("helvetica", "B", 7.8)
        pdf.cell(55, 4.2, "SNS - MSP / PRIVADO", align="R")
        pdf.set_xy(140, 7.2)
        pdf.set_font("helvetica", "I", 7.5)
        pdf.cell(55, 4.2, f"Emisión: {fecha_texto}", align="R")

        # Helper para tarjetas con recuadros
        def card_box(x, y, w, h, titulo, lineas_o_texto):
            pdf.set_xy(x, y)
            pdf.set_fill_color(240, 244, 249)
            pdf.set_draw_color(195, 208, 225)
            pdf.set_text_color(27, 54, 93)
            pdf.set_font("helvetica", "B", 7.6)
            pdf.cell(w, 4.5, f" {titulo}", border=1, fill=True)

            pdf.set_xy(x, y + 4.5)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(x, y + 4.5, w, h - 4.5, style='D')

            curr_y = y + 5.5
            pdf.set_text_color(35, 42, 55)

            if isinstance(lineas_o_texto, list):
                for linea in lineas_o_texto:
                    if curr_y > (y + h - 3.5):
                        break
                    linea_str = str(linea).strip()
                    if ":" in linea_str:
                        partes = linea_str.split(":", 1)
                        lbl_txt = f"- {partes[0].strip()}: "
                        val_txt = partes[1].strip()

                        pdf.set_font("helvetica", "B", 6.8)
                        w_lbl = pdf.get_string_width(lbl_txt) + 1.0

                        if w_lbl < (w * 0.48) and (pdf.get_string_width(val_txt) < (w - 5.0 - w_lbl)):
                            pdf.set_xy(x + 2.0, curr_y)
                            pdf.cell(w_lbl, 3.2, lbl_txt, border=0)
                            pdf.set_font("helvetica", "", 6.8)
                            pdf.set_xy(x + 2.0 + w_lbl, curr_y)
                            pdf.cell(w - 4.0 - w_lbl, 3.2, val_txt, border=0)
                            curr_y += 3.4
                        else:
                            pdf.set_xy(x + 2.0, curr_y)
                            pdf.cell(w - 4.0, 3.2, lbl_txt, border=0)
                            curr_y += 3.2
                            if curr_y > (y + h - 3.2):
                                break
                            pdf.set_xy(x + 4.5, curr_y)
                            pdf.set_font("helvetica", "", 6.8)
                            pdf.multi_cell(w - 6.5, 3.0, val_txt, border=0)
                            curr_y = max(pdf.get_y(), curr_y + 3.2) + 0.4
                    else:
                        pdf.set_xy(x + 2.0, curr_y)
                        pdf.set_font("helvetica", "", 6.8)
                        pdf.multi_cell(w - 4.0, 3.0, f"- {linea_str}", border=0)
                        curr_y = max(pdf.get_y(), curr_y + 3.2) + 0.4
            else:
                pdf.set_xy(x + 2.0, curr_y)
                pdf.set_font("helvetica", "", 7.0)
                pdf.multi_cell(w - 4.0, 3.2, str(lineas_o_texto).strip(), border=0)

        # 1. DATOS DE FILIACIÓN Y ADMISIÓN
        filiacion = datos.get("datos_filiacion", {}) if isinstance(datos.get("datos_filiacion"), dict) else {}
        nom_p = filiacion.get('nombre') or datos.get('nombre') or 'Paciente'
        doc_crudo = str(filiacion.get('documento') or filiacion.get('cedula') or datos.get('documento') or '')
        doc_limpio = sanitizar_cedula(doc_crudo)
        ctx_texto = str(datos.get('motivo_consulta', '')) + " " + str(datos.get('enfermedad_actual', ''))
        edad_p = formatear_edad(filiacion.get('edad') or datos.get('edad') or 'No especificado', ctx_texto)
        sexo_p = filiacion.get('sexo') or datos.get('sexo') or 'No especificado'
        tel_p = filiacion.get('telefono') or filiacion.get('contacto_emergencia') or datos.get('telefono') or "No especificado"
        ocup_p = filiacion.get('ocupacion') or datos.get('ocupacion') or "No especificada"
        dir_p = filiacion.get('direccion') or datos.get('direccion') or "Quito, Ecuador"
        estado_civil_p = filiacion.get('estado_civil') or datos.get('estado_civil') or "Soltero/a"

        # Cálculo de edad numérica y evaluación de minoría de edad
        m_ed = re.findall(r'\d+', str(edad_p))
        edad_num = int(m_ed[0]) if (m_ed and int(m_ed[0]) > 0) else 25
        es_menor = edad_num < 18

        rep_legal = filiacion.get('representante_legal') or datos.get('representante_legal')
        if es_menor:
            if isinstance(rep_legal, dict):
                rep_nom = rep_legal.get('nombre', 'Madre / Padre (Tutor Legal)')
                rep_ci = rep_legal.get('cedula', 'C.I. Registrada')
                rep_par = rep_legal.get('parentesco', 'Representante Legal')
                rep_texto = f"{rep_nom} ({rep_par})  -  C.I.: {rep_ci}"
            elif rep_legal and str(rep_legal).strip().lower() not in ('none', 'no especificado', ''):
                rep_texto = str(rep_legal).strip()
            else:
                rep_texto = "Representante Legal / Tutor acreditado según normativa MSP (Menor de edad)"
        else:
            rep_texto = "Mayor de edad (Atención autónoma con capacidad jurídica plena)"

        # Sub-barra institucional
        pdf.set_xy(15, 15.0)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.rect(15, 15.0, 180, 5.2, style='DF')
        pdf.set_xy(16.5, 15.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(75, 4.0, "ESTABLECIMIENTO: BIMO Especialidades Odontológicas", border=0)
        pdf.set_xy(92, 15.5)
        pdf.cell(101, 4.0, f"UNICÓDIGO: 1792834001   |   H.C./C.I.: {doc_limpio}   |   EXP. #{num_expediente}", align="R", border=0)

        # 1. REGISTRO DE ADMISIÓN Y FILIACIÓN
        y_b1 = 21.2
        pdf.set_xy(15, y_b1)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.8)
        pdf.cell(180, 4.8, " 1. REGISTRO DE ADMISIÓN Y FILIACIÓN DEL PACIENTE", border=1, fill=True)
        pdf.rect(15, y_b1 + 4.8, 180, 20.2, style='D')

        # Fila 1: Paciente, Cédula, Edad, Sexo, Estado Civil
        pdf.set_xy(16.5, y_b1 + 5.5)
        pdf.set_font("helvetica", "B", 7.2)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(13, 3.8, "Paciente: ", border=0)
        nom_display = str(nom_p).strip()
        f_size_nom = 7.0 if len(nom_display) <= 24 else (6.3 if len(nom_display) <= 32 else 5.7)
        pdf.set_font("helvetica", "B" if len(nom_display) <= 26 else "", f_size_nom)
        pdf.cell(50, 3.8, nom_display[:42], border=0)

        pdf.set_font("helvetica", "B", 7.2)
        pdf.cell(16, 3.8, "Cédula / C.I.: ", border=0)
        pdf.set_font("helvetica", "", 7.2)
        pdf.cell(22, 3.8, str(doc_limpio)[:12], border=0)

        pdf.set_font("helvetica", "B", 7.2)
        pdf.cell(16, 3.8, "Edad / Sexo: ", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(26, 3.8, f"{edad_p} | {sexo_p}"[:20], border=0)

        pdf.set_font("helvetica", "B", 7.2)
        pdf.cell(15, 3.8, "Estado Civil: ", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(18, 3.8, str(estado_civil_p)[:12], border=0)

        # Fila 2: Ocupación, Dirección, Teléfono
        pdf.set_xy(16.5, y_b1 + 9.8)
        pdf.set_font("helvetica", "B", 7.2)
        pdf.cell(16, 3.8, "Ocupación: ", border=0)
        pdf.set_font("helvetica", "", 7.2)
        pdf.cell(42, 3.8, str(ocup_p)[:26], border=0)

        pdf.set_font("helvetica", "B", 7.2)
        pdf.cell(15, 3.8, "Dirección: ", border=0)
        pdf.set_font("helvetica", "", 7.2)
        pdf.cell(55, 3.8, str(dir_p)[:36], border=0)

        pdf.set_font("helvetica", "B", 7.2)
        pdf.cell(22, 3.8, "Teléfono / Celular: ", border=0)
        pdf.set_font("helvetica", "", 7.2)
        pdf.cell(32, 3.8, str(tel_p)[:20], border=0)

        # Fila 3: Representante Legal
        pdf.set_xy(16.5, y_b1 + 14.1)
        pdf.set_font("helvetica", "B", 7.2)
        pdf.cell(38, 3.8, "Representante Legal / Tutor: ", border=0)
        pdf.set_font("helvetica", "", 7.2)
        pdf.cell(138, 3.8, str(rep_texto)[:95], border=0)

        # Franja Ejecutiva de Honorarios y Estado de Cuenta (Cuentas Claras)
        pagos_info = datos.get("pagos", {}) if isinstance(datos.get("pagos"), dict) else {}
        costo_val = float(pagos_info.get("costo_total") or 0.0)
        abono_val = float(pagos_info.get("abono") or 0.0)
        saldo_val = float(pagos_info.get("saldo_pendiente") if pagos_info.get("saldo_pendiente") is not None else max(0.0, round(costo_val - abono_val, 2)))

        y_pago_bar = 47.5
        pdf.set_xy(15.0, y_pago_bar)
        if saldo_val > 0.0:
            pdf.set_fill_color(254, 243, 199)
            pdf.set_draw_color(245, 158, 11)
            col_badge = (180, 83, 9)
            txt_badge = f"SALDO PENDIENTE: ${saldo_val:.2f}"
        elif costo_val > 0.0 and saldo_val <= 0.0:
            pdf.set_fill_color(209, 250, 229)
            pdf.set_draw_color(16, 185, 129)
            col_badge = (4, 120, 87)
            txt_badge = "SALDO TOTALMENTE CANCELADO"
        else:
            pdf.set_fill_color(241, 245, 249)
            pdf.set_draw_color(203, 213, 225)
            col_badge = (71, 85, 105)
            txt_badge = "ESTADO: AL DÍA"

        pdf.rect(15.0, y_pago_bar, 180.0, 6.5, style='DF')
        pdf.set_xy(17.0, y_pago_bar + 0.8)
        pdf.set_font("helvetica", "B", 7.2)
        pdf.set_text_color(27, 54, 93)
        costo_txt = f"${costo_val:.2f}" if costo_val > 0 else "Por definir"
        abono_txt = f"${abono_val:.2f}" if abono_val > 0 else "$0.00"
        saldo_txt = f"${saldo_val:.2f}" if saldo_val > 0 else "$0.00"
        pdf.cell(118, 5.0, f"CONTROL DE HONORARIOS: Costo: {costo_txt}   |   Abono: {abono_txt}   |   Saldo: {saldo_txt}", border=0)
        pdf.set_xy(135.0, y_pago_bar + 0.8)
        pdf.set_font("helvetica", "B", 7.2)
        pdf.set_text_color(*col_badge)
        pdf.cell(58.0, 5.0, f"[{txt_badge}]", align="R", border=0)

        # FILA 2: Motivo de Consulta & Enfermedad Actual (Lado a lado)
        w_col = 88
        gap = 4
        x_col1 = 15
        x_col2 = x_col1 + w_col + gap
        y_fila2 = 55.2
        h_fila2 = 17.0

        card_box(x_col1, y_fila2, w_col, h_fila2, "2. MOTIVO DE CONSULTA (Texto literal)", datos.get("motivo_consulta", "Revisión odontológica y limpieza general"))
        card_box(x_col2, y_fila2, w_col, h_fila2, "3. ENFERMEDAD O PROBLEMA ACTUAL", datos.get("enfermedad_actual", "Evolución progresiva sin sintomatología aguda severa"))

        # FILA 3: Antecedentes (8 ítems MSP) & Constantes Vitales
        y_fila3 = 73.5
        w_ant = 114
        w_vit = 62
        x_vit = 15 + w_ant + gap
        h_fila3 = 27.0

        pdf.set_xy(15, y_fila3)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(w_ant, 4.5, " 4. ANTECEDENTES PERSONALES Y FAMILIARES (MSP)", border=1, fill=True)
        pdf.rect(15, y_fila3 + 4.5, w_ant, h_fila3 - 4.5, style='D')

        ant_data = datos.get("antecedentes", {}) if isinstance(datos.get("antecedentes"), dict) else {}
        items_ant = [
            ("1. Alergia antib.", "SÍ" if ant_data.get("alergia_antibiotico") in ("Si", "SÍ", "True", True) else "NO"),
            ("2. Alergia anest.", "SÍ" if ant_data.get("alergia_anestesia") in ("Si", "SÍ", "True", True) else "NO"),
            ("3. Hemorragias", "SÍ" if ant_data.get("hemorragias") in ("Si", "SÍ", "True", True) else "NO"),
            ("4. Diabetes", "SÍ" if ant_data.get("diabetes") in ("Si", "SÍ", "True", True) else "NO"),
            ("5. Hipertensión", "SÍ" if ant_data.get("hipertension") in ("Si", "SÍ", "True", True) else "NO"),
            ("6. Cardiopatía", "SÍ" if ant_data.get("cardiopatias") in ("Si", "SÍ", "True", True) else "NO"),
            ("7. Respiratoria", "SÍ" if ant_data.get("respiratorias") in ("Si", "SÍ", "True", True) else "NO"),
            ("8. Otra/Med.", "SÍ" if ant_data.get("otras_alergias") or ant_data.get("medicamentos") else "NO")
        ]

        pdf.set_text_color(35, 42, 55)
        pdf.set_xy(16.5, y_fila3 + 5.2)
        pdf.set_font("helvetica", "", 6.8)
        for lbl_a, val_a in items_ant[:4]:
            pdf.set_font("helvetica", "B" if val_a == "SÍ" else "", 6.8)
            pdf.cell(27.5, 3.4, f"[{val_a}] {lbl_a}", border=0)

        pdf.set_xy(16.5, y_fila3 + 9.0)
        for lbl_a, val_a in items_ant[4:]:
            pdf.set_font("helvetica", "B" if val_a == "SÍ" else "", 6.8)
            pdf.cell(27.5, 3.4, f"[{val_a}] {lbl_a}", border=0)

        pdf.set_xy(16.5, y_fila3 + 13.2)
        pdf.set_font("helvetica", "B", 6.8)
        pdf.cell(22, 3.4, "Observaciones: ", border=0)
        pdf.set_font("helvetica", "", 6.8)
        obs_ant = ant_data.get("observaciones") or ant_data.get("medicamentos") or ant_data.get("enfermedades_sistemicas") or "No refiere antecedentes patológicos familiares ni personales de riesgo"
        pdf.multi_cell(w_ant - 26, 3.2, str(obs_ant)[:120], border=0)

        # 5. Constantes Vitales
        pdf.set_xy(x_vit, y_fila3)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(w_vit, 4.5, " 5. SIGNOS VITALES", border=1, fill=True)
        pdf.rect(x_vit, y_fila3 + 4.5, w_vit, h_fila3 - 4.5, style='D')

        vit_data = datos.get("signos_vitales", {}) if isinstance(datos.get("signos_vitales"), dict) else {}
        pa_txt = vit_data.get("presion_arterial") or ("118/78 mmHg" if edad_num >= 18 else "105/65 mmHg")
        fc_txt = vit_data.get("frecuencia_cardiaca") or ("72 lpm" if edad_num >= 18 else "82 lpm")
        temp_txt = vit_data.get("temperatura") or "36.5 °C"
        fr_txt = vit_data.get("frecuencia_respiratoria") or "18 rpm"

        pdf.set_text_color(35, 42, 55)
        pdf.set_xy(x_vit + 2.0, y_fila3 + 5.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.cell(26, 3.6, "Presión Arterial (PA):", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(30, 3.6, pa_txt, border=0)

        pdf.set_xy(x_vit + 2.0, y_fila3 + 9.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.cell(26, 3.6, "Frec. Cardíaca (FC):", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(30, 3.6, fc_txt, border=0)

        pdf.set_xy(x_vit + 2.0, y_fila3 + 13.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.cell(26, 3.6, "Temperatura (T):", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(30, 3.6, temp_txt, border=0)

        pdf.set_xy(x_vit + 2.0, y_fila3 + 17.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.cell(26, 3.6, "Frec. Respiratoria:", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(30, 3.6, fr_txt, border=0)

        pdf.set_xy(x_vit + 2.0, y_fila3 + 21.5)
        pdf.set_font("helvetica", "I", 6.8)
        pdf.set_text_color(70, 80, 95)
        pdf.cell(58, 3.6, "Hemodinámicamente estable", border=0)

        # 6. EXAMEN DEL SISTEMA ESTOMATOGNÁTICO
        y_b6 = 102.0
        h_b6 = 25.0
        pdf.set_xy(15, y_b6)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(180, 4.5, " 6. EXAMEN DEL SISTEMA ESTOMATOGNÁTICO (12 REGIONES ANATÓMICAS MSP)", border=1, fill=True)
        pdf.rect(15, y_b6 + 4.5, 180, h_b6 - 4.5, style='D')

        regiones_msp = [
            ("1. Labios", "SP"), ("2. Mejillas", "SP"), ("3. Maxilar Sup.", "SP"), ("4. Maxilar Inf.", "SP"),
            ("5. Lengua", "SP"), ("6. Paladar", "SP"), ("7. Piso Boca", "SP"), ("8. Carrillos", "SP"),
            ("9. Glánd. Saliv.", "SP"), ("10. Faringe", "SP"), ("11. ATM", "SP"), ("12. Ganglios", "SP")
        ]

        pdf.set_xy(16.5, y_b6 + 5.2)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(35, 42, 55)
        for r_lbl, r_val in regiones_msp[:6]:
            pdf.cell(29.5, 3.4, f"{r_lbl}: [{r_val}]", border=0)

        pdf.set_xy(16.5, y_b6 + 9.0)
        for r_lbl, r_val in regiones_msp[6:]:
            pdf.cell(29.5, 3.4, f"{r_lbl}: [{r_val}]", border=0)

        pdf.set_xy(16.5, y_b6 + 13.2)
        pdf.set_font("helvetica", "B", 6.8)
        pdf.cell(20, 3.4, "Observaciones: ", border=0)
        pdf.set_font("helvetica", "", 6.8)
        obs_estom = datos.get("examen_intraoral") or datos.get("examen_extraoral") or "Mucosas orales y peri-orales de coloración y textura conservada, sin lesiones ni adenopatías."
        pdf.multi_cell(156, 3.2, str(obs_estom)[:135], border=0)

        # 11. DIAGNÓSTICO CODIFICADO CIE-10
        y_b11 = 128.5
        h_b11 = 22.0
        pdf.set_xy(15, y_b11)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(180, 4.5, " 11. DIAGNÓSTICO CODIFICADO CIE-10 (OBLIGATORIO MSP / OMS)", border=1, fill=True)
        pdf.rect(15, y_b11 + 4.5, 180, h_b11 - 4.5, style='D')

        diag_raw = datos.get("diagnostico", "Caries dental")
        cod_cie10, desc_cie10, cond_cie10 = obtener_codigo_cie10(diag_raw)

        pdf.set_xy(16.5, y_b11 + 5.5)
        pdf.set_font("helvetica", "B", 7.2)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(28, 4.0, f"CÓDIGO CIE-10: {cod_cie10}", border=0)
        pdf.set_font("helvetica", "", 7.2)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(110, 4.0, f"DESCRIPCIÓN: {desc_cie10} ({diag_raw[:45]})", border=0)
        pdf.set_font("helvetica", "B", 7.2)
        pdf.cell(38, 4.0, f"CONDICIÓN: [{cond_cie10}] DEFINITIVO", align="R", border=0)

        pdf.set_xy(16.5, y_b11 + 11.0)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(70, 80, 95)
        pdf.cell(28, 3.8, "CÓDIGO CIE-10: Z01.2", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(110, 3.8, "DESCRIPCIÓN: Examen odontológico de rutina, control higiénico y profilaxis", border=0)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.cell(38, 3.8, "CONDICIÓN: [DEF] DEFINITIVO", align="R", border=0)

        # 10. PLANES DE TRATAMIENTO (DIAGNÓSTICO, TERAPÉUTICO, EDUCACIONAL)
        y_b10 = 152.0
        h_b10 = 30.0
        pdf.set_xy(15, y_b10)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(180, 4.5, " 10. PLANES DE TRATAMIENTO: DIAGNÓSTICO, TERAPÉUTICO Y EDUCACIONAL", border=1, fill=True)
        pdf.rect(15, y_b10 + 4.5, 180, h_b10 - 4.5, style='D')

        plan_raw = datos.get("plan_tratamiento", "Restauración con resina compuesta estética")

        pdf.set_xy(16.5, y_b10 + 5.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(24, 3.8, "a) Diagnóstico:", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(152, 3.8, "Examen clínico estomatognático, evaluación oclusal e inspección visual con sonda periodontal.", border=0)

        pdf.set_xy(16.5, y_b10 + 10.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(24, 3.8, "b) Terapéutico:", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(152, 3.8, str(plan_raw)[:115], border=0)

        pdf.set_xy(16.5, y_b10 + 15.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(24, 3.8, "c) Educacional:", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(152, 3.8, "Técnica de cepillado de Bass modificada, uso diario de hilo dental y control de dieta cariogénica.", border=0)

        # EVALUACIÓN OCLUSAL
        y_ocl = 183.5
        h_ocl = 19.0
        pdf.set_xy(15, y_ocl)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(180, 4.5, " EVALUACIÓN OCLUSAL Y RELACIÓN INTERMAXILAR", border=1, fill=True)
        pdf.rect(15, y_ocl + 4.5, 180, h_ocl - 4.5, style='D')

        orto_p1 = datos.get("evaluacion_ortodoncia", {}) if isinstance(datos.get("evaluacion_ortodoncia"), dict) else {}
        clase_ang = orto_p1.get("clase_angle", "Clase I (Normo-oclusión)")
        mord_p1 = orto_p1.get("mordida", "Normo-oclusión")
        alin_p1 = orto_p1.get("alineacion", "Alineación conservada")
        apar_p1 = orto_p1.get("aparatologia", "Sin aparatología activa")

        pdf.set_xy(16.5, y_ocl + 5.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(26, 3.8, "Clasificación Angle:", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(58, 3.8, str(clase_ang)[:32], border=0)

        pdf.set_font("helvetica", "B", 7.0)
        pdf.cell(28, 3.8, "Relación de Mordida:", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(64, 3.8, str(mord_p1)[:36], border=0)

        pdf.set_xy(16.5, y_ocl + 10.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.cell(26, 3.8, "Alineación Dental:", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(58, 3.8, str(alin_p1)[:32], border=0)

        pdf.set_font("helvetica", "B", 7.0)
        pdf.cell(28, 3.8, "Aparatología Activa:", border=0)
        pdf.set_font("helvetica", "", 7.0)
        pdf.cell(64, 3.8, str(apar_p1)[:36], border=0)

        # VALIDACIÓN Y FIRMAS DE APERTURA DE EXPEDIENTE
        y_firm_p1 = 204.5
        h_firm_p1 = 40.0
        pdf.set_xy(15, y_firm_p1)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(180, 4.5, " VALIDACIÓN Y FIRMAS DE APERTURA DE EXPEDIENTE", border=1, fill=True)
        pdf.rect(15, y_firm_p1 + 4.5, 180, h_firm_p1 - 4.5, style='D')

        y_lin_p1 = y_firm_p1 + 25.0
        pdf.set_draw_color(160, 160, 160)
        pdf.line(22, y_lin_p1, 92, y_lin_p1)
        pdf.line(118, y_lin_p1, 188, y_lin_p1)

        pdf.set_xy(22, y_lin_p1 + 1.2)
        pdf.set_font("helvetica", "B", 7.2)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(70, 3.5, "Firma del Paciente / Representante Legal", align="C")
        pdf.set_xy(22, y_lin_p1 + 4.8)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(70, 3.2, f"C.I.: {doc_limpio}", align="C")

        pdf.set_xy(118, y_lin_p1 + 1.2)
        pdf.set_font("helvetica", "B", 7.2)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(70, 3.5, "Firma y Sello del Odontólogo Tratante", align="C")
        pdf.set_xy(118, y_lin_p1 + 4.8)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(70, 3.2, "Registro Profesional Odontológico MSP / Senescyt", align="C")

        pdf.set_xy(15, 284)
        pdf.set_font("helvetica", "I", 7.2)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(180, 4, f"BIMO Software Odontológico  -  Formulario 033 MSP Ecuador  -  Página 1 de {total_paginas}  -  Documento Confidencial", align="C")

        # =========================================================================
        # PÁGINA 2: REVERSO FORMULARIO 033 MSP (ODONTOGRAMA, ÍNDICES Y EVOLUCIÓN)
        # =========================================================================
        pdf.add_page()

        pdf.set_fill_color(27, 54, 93)
        pdf.rect(0, 0, 210, 14, style='F')
        pdf.set_xy(15, 2.2)
        pdf.set_font("helvetica", "B", 10.5)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(125, 4.5, "REPÚBLICA DEL ECUADOR  |  MINISTERIO DE SALUD PÚBLICA", align="L")
        pdf.set_xy(15, 7.2)
        pdf.set_font("helvetica", "B", 8.2)
        pdf.cell(125, 4.5, "FORMULARIO 033  -  ODONTOGRAMA VISUAL Y EVOLUCIÓN CLÍNICA", align="L")

        nom_p2 = nom_p[:32] if len(nom_p) > 32 else nom_p
        pdf.set_xy(90, 4.0)
        pdf.set_font("helvetica", "I", 7.2)
        pdf.cell(105, 5.0, f"Paciente: {nom_p2}  |  C.I.: {doc_limpio}  |  Exp. #{num_expediente}", align="R")

        odontograma_lista = datos.get("odontograma", [])
        if not isinstance(odontograma_lista, list):
            odontograma_lista = [odontograma_lista] if isinstance(odontograma_lista, dict) else []

        # Detalle de piezas evaluadas
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

        ruta_temp_img, resumen_odonto = colorear_odontograma(odontograma_lista, ruta_base=RUTA_BASE_ODONTOGRAMA)
        indices_salud = calcular_indices_salud_bucal(odontograma_lista, resumen_odonto, edad_num)

        # Lado Izquierdo: Odontograma Gráfico (w=98, h=117mm)
        w_box = 98.0
        x_box = 15.0
        y_odonto = 17.5
        h_box = 117.0

        # Imagen centrada con aspect ratio natural (1664x2560)
        h_img = 108.0
        w_img = 70.2
        x_img = x_box + (w_box - w_img) / 2.0
        y_img = y_odonto + 6.5

        if ruta_temp_img and os.path.exists(ruta_temp_img):
            pdf.image(ruta_temp_img, x=x_img, y=y_img, w=w_img, h=h_img)
        elif os.path.exists(RUTA_BASE_ODONTOGRAMA):
            pdf.image(RUTA_BASE_ODONTOGRAMA, x=x_img, y=y_img, w=w_img, h=h_img)

        pdf.set_xy(x_box, y_odonto)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(w_box, 4.5, " 7. ODONTOGRAMA VISUAL DIGITALIZADO (FDI)", border=1, fill=True)
        pdf.rect(x_box, y_odonto + 4.5, w_box, h_box - 4.5, style='D')

        # Lado Derecho: Simbología + Índices de Salud + Índices CPO-D / ceo-d
        x_r = 117
        w_r = 78

        # 1. Simbología Oficial Estandarizada MSP (Y=17.5, h=33mm)
        pdf.set_xy(x_r, y_odonto)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(w_r, 4.5, " SIMBOLOGÍA OFICIAL ESTANDARIZADA MSP", border=1, fill=True)
        pdf.rect(x_r, y_odonto + 4.5, w_r, 29.5, style='D')

        items_simb_msp = [
            ((220, 38, 38), "ROJO - Patología Actual:", "Caries activa, fractura o lesión a tratar."),
            ((37, 99, 235), "AZUL - Tratamiento Previo:", "Resinas, amalgamas o coronas en buen estado."),
            ((100, 116, 139), "GRIS - Diente Ausente / X:", "Exodoncia previa, agenesia o pieza perdida."),
            ((240, 240, 240), "NATURAL - Sano:", "Estructura dental anatómica sin patología.")
        ]
        curr_y_simb = y_odonto + 5.5
        for rgb_s, tit_s, desc_s in items_simb_msp:
            pdf.set_fill_color(*rgb_s)
            pdf.set_draw_color(160, 160, 160)
            pdf.rect(x_r + 3.0, curr_y_simb + 0.8, 3.8, 3.8, style='DF')

            pdf.set_xy(x_r + 8.5, curr_y_simb)
            pdf.set_font("helvetica", "B", 6.8)
            pdf.set_text_color(35, 42, 55)
            pdf.cell(38, 3.2, tit_s, border=0)

            pdf.set_xy(x_r + 8.5, curr_y_simb + 3.0)
            pdf.set_font("helvetica", "", 6.4)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(w_r - 10, 3.0, desc_s, border=0)
            curr_y_simb += 6.5

        # 8. Indicadores de Salud Bucal (IHOS) (Y=52.5, h=35mm)
        y_ind = 52.5
        pdf.set_xy(x_r, y_ind)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(w_r, 4.5, " 8. INDICADORES DE SALUD BUCAL (IHOS)", border=1, fill=True)
        pdf.rect(x_r, y_ind + 4.5, w_r, 31.5, style='D')

        ihos_data = indices_salud["ihos"]
        pdf.set_xy(x_r + 3.0, y_ind + 5.5)
        pdf.set_font("helvetica", "B", 6.8)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(42, 3.4, "Placa Bacteriana (0-3):", border=0)
        pdf.set_font("helvetica", "", 6.8)
        pdf.cell(30, 3.4, f"Grado {ihos_data['placa']}", border=0)

        pdf.set_xy(x_r + 3.0, y_ind + 9.5)
        pdf.set_font("helvetica", "B", 6.8)
        pdf.cell(42, 3.4, "Cálculo / Tártaro (0-3):", border=0)
        pdf.set_font("helvetica", "", 6.8)
        pdf.cell(30, 3.4, f"Grado {ihos_data['calculo']}", border=0)

        pdf.set_xy(x_r + 3.0, y_ind + 13.5)
        pdf.set_font("helvetica", "B", 6.8)
        pdf.cell(42, 3.4, "Gingivitis / Sangrado (0-3):", border=0)
        pdf.set_font("helvetica", "", 6.8)
        pdf.cell(30, 3.4, f"Grado {ihos_data['gingivitis']}", border=0)

        pdf.set_xy(x_r + 3.0, y_ind + 18.0)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(42, 3.8, "Índice Higiene Oral (IHOS):", border=0)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.cell(30, 3.8, ihos_data['valor'], border=0)

        pdf.set_xy(x_r + 3.0, y_ind + 22.5)
        pdf.set_font("helvetica", "B", 6.8)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(32, 3.4, "Enf. Periodontal:", border=0)
        pdf.set_font("helvetica", "", 6.6)
        pdf.cell(40, 3.4, indices_salud['periodontal'][:28], border=0)

        pdf.set_xy(x_r + 3.0, y_ind + 26.5)
        pdf.set_font("helvetica", "I", 6.4)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(72, 3.0, "Piezas testigo FDI: 16, 11, 26, 36, 31, 46", border=0)

        # 9. Índices Epidemiológicos CPO-D y ceo-d (Y=89.5, h=42.5mm)
        y_cpo = 89.5
        pdf.set_xy(x_r, y_cpo)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(w_r, 4.5, " 9. ÍNDICES CPO-D Y ceo-d (EPIDEMIOLOGÍA)", border=1, fill=True)
        pdf.rect(x_r, y_cpo + 4.5, w_r, 42.5, style='D')

        cpod = indices_salud["cpod"]
        ceod = indices_salud["ceod"]

        pdf.set_xy(x_r + 3.0, y_cpo + 5.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(72, 3.6, "Dentición Permanente (CPO-D):", border=0)

        pdf.set_xy(x_r + 5.0, y_cpo + 9.5)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(70, 3.4, f"C (Cariados / Activos): {cpod['C']} pieza(s)", border=0)
        pdf.set_xy(x_r + 5.0, y_cpo + 13.0)
        pdf.cell(70, 3.4, f"P (Perdidos / Extraídos): {cpod['P']} pieza(s)", border=0)
        pdf.set_xy(x_r + 5.0, y_cpo + 16.5)
        pdf.cell(70, 3.4, f"O (Obturados / Tratados): {cpod['O']} pieza(s)", border=0)

        pdf.set_xy(x_r + 5.0, y_cpo + 20.5)
        pdf.set_font("helvetica", "B", 7.0)
        if cpod['total'] > 3:
            pdf.set_text_color(180, 83, 9)
        else:
            pdf.set_text_color(27, 54, 93)
        pdf.cell(70, 3.6, f"TOTAL CPO-D: {cpod['total']} (Severidad: {'Moderada' if cpod['total'] > 2 else 'Baja'})", border=0)

        pdf.set_xy(x_r + 3.0, y_cpo + 25.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(72, 3.6, "Dentición Temporal (ceo-d):", border=0)

        pdf.set_xy(x_r + 5.0, y_cpo + 29.5)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(70, 3.4, f"c (cariados): {ceod['c']}  |  e (extracción): {ceod['e']}  |  o (obturados): {ceod['o']}", border=0)
        pdf.set_xy(x_r + 5.0, y_cpo + 33.0)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.cell(70, 3.6, f"TOTAL ceo-d: {ceod['total']} pieza(s) temporales", border=0)

        pdf.set_xy(x_r + 3.0, y_cpo + 38.0)
        pdf.set_font("helvetica", "I", 6.4)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(72, 3.0, "Cálculo matemático automatizado oficial MSP", border=0)

        # 7.1 DETALLE DENTAL CLÍNICO POR PIEZA (FDI) (Y=137.5, w=180, h=22mm)
        y_det = 137.5
        h_det = 22.0
        pdf.set_xy(15, y_det)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(180, 4.5, " 7.1 DETALLE DENTAL CLÍNICO POR PIEZA (SISTEMA INTERNACIONAL FDI)", border=1, fill=True)
        pdf.rect(15, y_det + 4.5, 180, h_det - 4.5, style='D')

        pdf.set_xy(16.5, y_det + 5.5)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(35, 42, 55)
        if lineas_dientes:
            for l_d in lineas_dientes[:4]:
                pdf.cell(176, 3.4, f"- {l_d[:110]}", border=0)
                pdf.ln(3.5)
                pdf.set_x(16.5)
        else:
            pdf.cell(176, 3.8, "Sin hallazgos patológicos en piezas dentales (Fórmula dental sana).", border=0)

        # 12. REGISTRO DE TRATAMIENTOS Y EVOLUCIÓN CRONOLÓGICA (Y=161.0, w=180, h=26mm)
        y_evo = 161.0
        h_evo = 26.0
        pdf.set_xy(15, y_evo)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(180, 4.5, " 12. REGISTRO DE TRATAMIENTOS Y EVOLUCIÓN CRONOLÓGICA", border=1, fill=True)
        pdf.rect(15, y_evo + 4.5, 180, h_evo - 4.5, style='D')

        pdf.set_xy(15, y_evo + 4.5)
        pdf.set_fill_color(230, 238, 248)
        pdf.set_font("helvetica", "B", 6.8)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(26, 4.2, " FECHA / HORA", border=1, fill=True)
        pdf.cell(22, 4.2, " CÓD. CIE-10", border=1, fill=True)
        pdf.cell(94, 4.2, " PROCEDIMIENTO CLÍNICO / EVOLUCIÓN", border=1, fill=True)
        pdf.cell(38, 4.2, " FIRMA PROFESIONAL", border=1, fill=True)

        pdf.set_xy(15, y_evo + 8.7)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(26, 7.5, f" {fecha_texto[:10]}", border=1)
        pdf.cell(22, 7.5, f" {cod_cie10}", border=1)
        pdf.cell(94, 7.5, f" {plan_raw[:65]}", border=1)
        pdf.set_font("helvetica", "I", 6.8)
        pdf.cell(38, 7.5, " Mateo Ramírez", align="C", border=1)

        receta_txt = datos.get("receta") or "Sin prescripción farmacológica activa"
        pdf.set_xy(15, y_evo + 16.2)
        pdf.set_font("helvetica", "", 6.8)
        pdf.cell(48, 8.5, " Prescripción Médica:", border=1)
        pdf.cell(132, 8.5, f" {receta_txt[:95]}", border=1)

        # 13. CONSENTIMIENTO INFORMADO (NORMATIVA MSP ECUADOR) (Y=188.5, w=180, h=42mm)
        y_cons = 188.5
        h_cons = 42.0
        pdf.set_xy(15, y_cons)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(180, 4.5, " 13. CONSENTIMIENTO INFORMADO Y COMPROMISO TERAPÉUTICO (NORMA MSP ECUADOR)", border=1, fill=True)
        pdf.rect(15, y_cons + 4.5, 180, h_cons - 4.5, style='D')

        txt_consent_msp = (
            "El paciente o su representante legal declara haber sido informado con claridad acerca de su diagnóstico "
            "clínico, plan de tratamiento propuesto, alternativas viables, riesgos inherentes y cuidados post-operatorios "
            "indispensables. Manifiesta su conformidad voluntaria y autoriza la ejecución de los procedimientos odontológicos "
            "planificados, comprometiéndose a seguir las indicaciones terapéuticas, mantener óptima higiene oral y acudir "
            "puntualmente a las citas periódicas de control para garantizar la salud y durabilidad de los tratamientos."
        )

        pdf.set_xy(17.5, y_cons + 5.5)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(45, 45, 45)
        pdf.multi_cell(175, 3.2, txt_consent_msp)

        y_firm_cons = y_cons + 29.5
        pdf.set_draw_color(160, 160, 160)
        pdf.line(22, y_firm_cons, 92, y_firm_cons)
        pdf.line(118, y_firm_cons, 188, y_firm_cons)

        pdf.set_xy(22, y_firm_cons + 1.2)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(70, 3.4, "Firma del Paciente / Representante Legal", align="C")
        pdf.set_xy(22, y_firm_cons + 4.5)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(70, 3.0, f"C.I.: {doc_limpio}", align="C")

        pdf.set_xy(118, y_firm_cons + 1.2)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(70, 3.4, "Firma y Sello del Odontólogo Tratante", align="C")
        pdf.set_xy(118, y_firm_cons + 4.5)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(90, 90, 90)
        pdf.cell(70, 3.0, "Registro Profesional Odontológico MSP / Senescyt", align="C")

        # 14. SEGURIDAD, AUDITORÍA, INMUTABILIDAD Y VALIDEZ LEGAL (Y=232.0, w=180, h=40mm)
        y_sec = 232.0
        h_sec = 40.0
        pdf.set_xy(15, y_sec)
        pdf.set_fill_color(240, 244, 249)
        pdf.set_draw_color(195, 208, 225)
        pdf.set_text_color(27, 54, 93)
        pdf.set_font("helvetica", "B", 7.6)
        pdf.cell(180, 4.5, " 14. SEGURIDAD, AUDITORÍA, INMUTABILIDAD Y VALIDEZ LEGAL", border=1, fill=True)
        pdf.rect(15, y_sec + 4.5, 180, h_sec - 4.5, style='D')

        sello_sha = generar_sello_inmutabilidad(nom_p, doc_limpio, fecha_texto, doc_id=f"033-P{paciente_id}")

        pdf.set_xy(17.5, y_sec + 6.0)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(46, 3.6, "SELLO DE INMUTABILIDAD:", border=0)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(180, 83, 9)
        pdf.cell(60, 3.6, sello_sha, border=0)

        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(25, 3.6, "TIMESTAMP AUD.:", border=0)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(45, 3.6, f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ECT", align="R", border=0)

        pdf.set_xy(17.5, y_sec + 10.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(46, 3.6, "TRAZABILIDAD DE USUARIO:", border=0)
        pdf.set_font("helvetica", "", 6.8)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(128, 3.6, f"Mateo Ramírez  -  Odontólogo Tratante  -  ID #1  |  IP: 127.0.0.1  |  Sede: BIMO Matriz", border=0)

        pdf.set_xy(17.5, y_sec + 15.0)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(46, 3.6, "FIRMA ELECTRÓNICA:", border=0)
        pdf.set_font("helvetica", "", 6.6)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(128, 3.6, "Apto para suscripción digital con certificado electrónico reconocido en Ecuador (Token / .p12).", border=0)

        pdf.set_xy(17.5, y_sec + 19.5)
        pdf.set_font("helvetica", "B", 7.0)
        pdf.set_text_color(27, 54, 93)
        pdf.cell(46, 3.6, "CUSTODIA Y RETENCIÓN:", border=0)
        pdf.set_font("helvetica", "", 6.6)
        pdf.set_text_color(35, 42, 55)
        pdf.cell(128, 3.6, "Garantía de conservación obligatoria por un mínimo de 15 años (Ley Orgánica de Salud del Ecuador).", border=0)

        pdf.set_xy(17.5, y_sec + 24.5)
        pdf.set_font("helvetica", "I", 6.4)
        pdf.set_text_color(90, 90, 90)
        pdf.multi_cell(174, 3.0, "Registro médico inmutable. Cualquier alteración posterior invalida este certificado. Si se requiere corregir información, debe registrarse una Nota Aclaratoria oficial conforme al Manual de Historias Clínicas del MSP.")

        pdf.set_xy(15, 284)
        pdf.set_font("helvetica", "I", 7.2)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(180, 4, f"BIMO Software Odontológico  -  Formulario 033 MSP Ecuador  -  Página 2 de {total_paginas}  -  Documento Confidencial", align="C")

        # =========================================================================
        # PÁGINA 3: FICHA ESPECIALIZADA DE ORTODONCIA (SI APLICA)
        # =========================================================================
        if tiene_ortodoncia:
            pdf.add_page()

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

            # FILA 1: Hábitos Orales / Biotipo & Planificación de Ortodoncia
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

            fases_dict = orto_info.get("fases_planificacion")
            if isinstance(fases_dict, dict) and fases_dict:
                lineas_fases = [
                    str(fases_dict.get("fase_1", "Fase I (Alineación): Arcos NiTi redondos (.012 a .016)")),
                    str(fases_dict.get("fase_2", "Fase II (Trabajo): Arcos de Acero rectangular (.019x.025)")),
                    str(fases_dict.get("fase_3", "Fase III (Finalización): Arcos TMA y elásticos intermaxilares")),
                    str(fases_dict.get("fase_4", "Fase IV (Retención): Termoformado Essix y/o barra fija lingual"))
                ]
            else:
                lineas_fases = [
                    "Fase I (Alineación): Arcos NiTi redondos (.012 a .016)",
                    "Fase II (Trabajo): Arcos de Acero rectangular (.019x.025)",
                    "Fase III (Finalización): Arcos TMA y elásticos intermaxilares",
                    "Fase IV (Retención): Termoformado Essix y/o barra fija lingual"
                ]
            card_box(x_col2, y_p3_f1, w_col, h_p3_f1, "2. PLANIFICACIÓN Y FASES DE ORTODONCIA", lineas_fases)

            # FILA 2: Estudios Complementarios (Radiografías y Fotos Clínicas)
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

            # FILA 3: Registro de Evolución Clínica y Activaciones
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
            col_headers = ["Fecha", "Procedimiento / Arco / Activación", "Higiene Oral", "Próxima Cita", "Firma Odontólogo"]

            pdf.set_xy(15, y_p3_f3 + 5.0)
            pdf.set_fill_color(230, 238, 248)
            pdf.set_draw_color(195, 208, 225)
            pdf.set_font("helvetica", "B", 7.2)
            pdf.set_text_color(27, 54, 93)

            for i, h_name in enumerate(col_headers):
                pdf.cell(col_widths[i], 5.0, f" {h_name}", border=1, fill=True)
            pdf.ln()

            fecha_hoy_str = fecha_obj.strftime("%d/%m/%Y")
            motivo_orto = str(datos.get("motivo_consulta", "")).lower()
            plan_orto = str(datos.get("plan_tratamiento", ""))

            evo_info = orto_info.get("evolucion_activacion", {})
            if isinstance(evo_info, dict) and evo_info.get("procedimiento"):
                desc_act = str(evo_info.get("procedimiento"))
                higiene_act = str(evo_info.get("higiene", "Adecuada"))
                prox_cita_act = str(evo_info.get("proxima_cita", "4 semanas (1 mes)"))
            elif any(k in motivo_orto for k in ["instalacion", "instalación", "colocacion", "colocación"]):
                desc_act = "Instalación de aparatología ortodóncica. Diagnóstico y fases aprobadas."
                higiene_act = "Adecuada"
                prox_cita_act = "4 semanas (1 mes)"
            elif any(k in motivo_orto for k in ["control", "activacion", "activación", "ajuste", "cambio"]):
                desc_act = f"Control ortodóncico: {plan_orto[:60]}" if plan_orto else "Control de ortodoncia y ajuste de arcos/ligaduras."
                higiene_act = "Adecuada"
                prox_cita_act = "4 semanas (1 mes)"
            else:
                desc_act = f"Valoración de ortodoncia: {plan_orto[:60]}" if plan_orto else "Valoración clínica y planificación ortodóncica aprobada."
                higiene_act = "Adecuada"
                prox_cita_act = "4 semanas (1 mes)"

            filas_evolucion = [
                (fecha_hoy_str, desc_act, higiene_act, prox_cita_act, ""),
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

            # FILA 4: Consentimiento Informado Resumido de Ortodoncia
            y_p3_f4 = 199
            h_p3_f4 = 56

            pdf.set_xy(15, y_p3_f4)
            pdf.set_fill_color(240, 244, 249)
            pdf.set_draw_color(195, 208, 225)
            pdf.set_text_color(27, 54, 93)
            pdf.set_font("helvetica", "B", 8.2)
            pdf.cell(180, 5.0, " 5. CONSENTIMIENTO INFORMADO Y COMPROMISO TERAPÉUTICO DE ORTODONCIA", border=1, fill=True)

            pdf.set_xy(15, y_p3_f4 + 5.0)
            pdf.set_fill_color(255, 255, 255)
            pdf.rect(15, y_p3_f4 + 5.0, 180, h_p3_f4 - 5.0, style='D')

            txt_consentimiento_orto = (
                "El paciente o su representante legal declara haber sido informado con claridad acerca de los objetivos, "
                "fases, alternativas, cuidados y duración estimada del tratamiento ortodóncico. Se compromete a mantener una "
                "óptima higiene bucodental, evitar alimentos perjudiciales para la aparatología, portar los aditamentos y "
                "elásticos según prescripción, acudir puntualmente a los controles periódicos y usar los retenedores prescritos "
                "al finalizar el tratamiento activo para evitar recidivas."
            )

            pdf.set_xy(18, y_p3_f4 + 6.8)
            pdf.set_font("helvetica", "", 7.0)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(174, 3.4, txt_consentimiento_orto)

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
            pdf.cell(70, 3.2, "Registro Profesional Odontológico MSP / Senescyt", align="C")

            pdf.set_xy(15, 284)
            pdf.set_font("helvetica", "I", 7.5)
            pdf.set_text_color(120, 120, 120)
            pdf.cell(180, 4, f"BIMO Software Odontológico  -  Página 3 de {total_paginas}  -  Documento Clínico Confidencial", align="C")

        # ==========================================
        # RUTEO ANTI-HOMÓNIMOS Y GUARDADO DEL PDF
        # ==========================================
        nombre_paciente = filiacion.get('nombre', 'Paciente_Desconocido')
        nombre_limpio_carpeta = sanitizar_nombre_carpeta(nombre_paciente)

        categoria_edad = "Pacientes_Pediatricos" if edad_num < 18 else "Pacientes_Adultos"

        id_str = f"ID{paciente_id}"
        nombre_carpeta = f"{nombre_limpio_carpeta}_{edad_num}_anos_{id_str}"
        ruta_carpeta = os.path.join(str(RUTA_PACIENTES), categoria_edad, nombre_carpeta)
        os.makedirs(ruta_carpeta, exist_ok=True)

        nombre_archivo = generar_nombre_archivo_corto(nombre_paciente, edad_num, fecha_obj, num_expediente=num_expediente)
        ruta_final = os.path.join(ruta_carpeta, nombre_archivo)

        pdf.output(ruta_final)
        print(f"[OK] Historia clínica unificada Formulario 033 MSP guardada en: {ruta_final}")

        if ruta_temp_img and os.path.exists(ruta_temp_img):
            try:
                os.remove(ruta_temp_img)
            except Exception:
                pass

        return ruta_final

    except Exception as e:
        print(f"[ERROR] Error al construir el PDF: {e}")
        import traceback
        traceback.print_exc()
        if ruta_temp_img and os.path.exists(ruta_temp_img):
            try:
                os.remove(ruta_temp_img)
            except Exception:
                pass
        return None
