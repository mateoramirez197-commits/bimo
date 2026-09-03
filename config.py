import os
import json
import base64
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet
from license_manager import obtener_hwid_equipo

# Directorio raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent

# Archivos del sistema
RUTA_BASE_ODONTOGRAMA = BASE_DIR / "base_odontograma.png"
RUTA_DB = BASE_DIR / "bimo.db"
RUTA_PACIENTES = BASE_DIR / "Pacientes"
RUTA_VAULT = BASE_DIR / "bimo.vault"
RUTA_CLINICA_CONF = BASE_DIR / "clinica.json"

# ==========================================
# PALETA Y MOTOR DE TEMAS BIMO (INSPIRADOS EN REFERENCIAS VISUALES)
# ==========================================
TEMAS_BIMO = {
    "Skeuomorphism Desk (Light)": {
        "mode": "light",
        "bg_dark": "#E6E0D4",
        "card_dark": "#FDFBF7",
        "card_inner": "#FFFFFF",
        "sidebar": "#2B2B2B",
        "border": "#D3CFC6",
        "text_primary": "#222222",
        "text_muted": "#7A756D",
        "input_bg": "#F2EFEB",
        "input_border": "#C4BDB1",
        "card_hover": "#F4F1EA",
        "aqua": "#D32F2F",
        "azul_acero": "#1976D2",
        "azul_pastel": "#4CAF50",
        "amarillo": "#FBC02D",
        "fucsia": "#C2185B",
        "logo_colors": ["#D32F2F", "#1976D2", "#4CAF50", "#FBC02D"],
        "corner_radius": 4,
        "corner_btn": 6,
    },
    "Skeuomorphism Stereo (Dark)": {
        "mode": "dark",
        "bg_dark": "#1A1C1E",
        "card_dark": "#232629",
        "card_inner": "#1E2023",
        "sidebar": "#121315",
        "border": "#3B4045",
        "text_primary": "#E8EAED",
        "text_muted": "#80868B",
        "input_bg": "#0F1112",
        "input_border": "#292C30",
        "card_hover": "#292C30",
        "aqua": "#00E676",
        "azul_acero": "#2979FF",
        "azul_pastel": "#FF1744",
        "amarillo": "#FFEA00",
        "fucsia": "#D500F9",
        "logo_colors": ["#00E676", "#2979FF", "#FF1744", "#FFEA00"],
        "corner_radius": 8,
        "corner_btn": 4,
    },
    "Bimo Classic": {
        "mode": "dark",
        "bg_dark": "#0B0F19",
        "card_dark": "#141C2E",
        "sidebar": "#0E1524",
        "border": "#1E293B",
        "text_primary": "#F8FAFC",
        "text_muted": "#94A3B8",
        "input_bg": "#1A2337",
        "input_border": "#27354F",
        "card_hover": "#1E293B",
        "aqua": "#00F5D4",
        "azul_acero": "#2563EB",
        "azul_pastel": "#70D6FF",
        "amarillo": "#FFBE0B",
        "fucsia": "#FF006E",
        "logo_colors": ["#00F5D4", "#70D6FF", "#FF006E", "#FFBE0B"],
        "corner_radius": 16,
        "corner_btn": 12,
    },
    "Starloy Cyber Neon": {
        # Foto 1: Midnight dark, tarjetas nítidas con acentos violeta neon y ambar
        "mode": "dark",
        "bg_dark": "#090A12",
        "card_dark": "#121426",
        "sidebar": "#0D0F1D",
        "border": "#1E2240",
        "text_primary": "#F8FAFC",
        "text_muted": "#8B95B5",
        "input_bg": "#181B30",
        "input_border": "#2A3056",
        "card_hover": "#1B1E38",
        "aqua": "#7928CA",
        "azul_acero": "#0070F3",
        "azul_pastel": "#50E3C2",
        "amarillo": "#F5A623",
        "fucsia": "#FF0080",
        "logo_colors": ["#50E3C2", "#0070F3", "#7928CA", "#F5A623"],
        "corner_radius": 16,
        "corner_btn": 12,
    },
    "Soft Pastel Luxury": {
        # Foto 2: Dashboard claro ultra pulido, tarjetas blancas y acentos magenta/menta
        "mode": "light",
        "bg_dark": "#EEF2FB",
        "card_dark": "#FFFFFF",
        "sidebar": "#FFFFFF",
        "border": "#E2E8F0",
        "text_primary": "#1E293B",
        "text_muted": "#64748B",
        "input_bg": "#F8FAFC",
        "input_border": "#CBD5E1",
        "card_hover": "#F1F5F9",
        "aqua": "#10B981",
        "azul_acero": "#C026D3",
        "azul_pastel": "#E879F9",
        "amarillo": "#F59E0B",
        "fucsia": "#EC4899",
        "logo_colors": ["#C026D3", "#3B82F6", "#EC4899", "#10B981"],
        "corner_radius": 16,
        "corner_btn": 12,
    },
    "Cyberpunk Ultra Violet": {
        # Foto 3: Purpura profundo, tarjetas violeta oscuro y neon fucsia/cian
        "mode": "dark",
        "bg_dark": "#12072B",
        "card_dark": "#1A0E38",
        "sidebar": "#160A33",
        "border": "#33186B",
        "text_primary": "#F8FAFC",
        "text_muted": "#A78BFA",
        "input_bg": "#221347",
        "input_border": "#432185",
        "card_hover": "#281754",
        "aqua": "#00F5D4",
        "azul_acero": "#A855F7",
        "azul_pastel": "#C084FC",
        "amarillo": "#FDE047",
        "fucsia": "#FF007F",
        "logo_colors": ["#00F5D4", "#C084FC", "#FF007F", "#FDE047"],
        "corner_radius": 16,
        "corner_btn": 12,
    },
    "Obsidian Amber": {
        # Foto 4: Negro carbon mate, acentos ambar dorado y champan de lujo medico
        "mode": "dark",
        "bg_dark": "#0F1012",
        "card_dark": "#17181C",
        "sidebar": "#131417",
        "border": "#2C2822",
        "text_primary": "#FDF8F0",
        "text_muted": "#A8A29E",
        "input_bg": "#1F2026",
        "input_border": "#3D382E",
        "card_hover": "#23242A",
        "aqua": "#F59E0B",
        "azul_acero": "#D97706",
        "azul_pastel": "#FBBF24",
        "amarillo": "#FDE68A",
        "fucsia": "#EA580C",
        "logo_colors": ["#F59E0B", "#FBBF24", "#D97706", "#FDE68A"],
        "corner_radius": 16,
        "corner_btn": 12,
    },
    "Nordic Glow": {
        # Foto 5: Azul noche nordico, tarjetas navy y gradientes cian electrico/menta
        "mode": "dark",
        "bg_dark": "#0E121E",
        "card_dark": "#161B2E",
        "sidebar": "#121626",
        "border": "#1E2742",
        "text_primary": "#F8FAFC",
        "text_muted": "#94A3B8",
        "input_bg": "#1D233B",
        "input_border": "#2B3556",
        "card_hover": "#202740",
        "aqua": "#00F2FE",
        "azul_acero": "#3B82F6",
        "azul_pastel": "#38BDF8",
        "amarillo": "#34D399",
        "fucsia": "#F43F5E",
        "logo_colors": ["#00F2FE", "#38BDF8", "#3B82F6", "#34D399"],
        "corner_radius": 16,
        "corner_btn": 12,
    },
    "Frutiger Aero": {
        "mode": "dark",
        "bg_dark": "#04243D",
        "card_dark": "#0A3F63",
        "sidebar": "#031B30",
        "border": "#1B6D9B",
        "text_primary": "#FFFFFF",
        "text_muted": "#BAE6FD",
        "input_bg": "#062A47",
        "input_border": "#257DAE",
        "card_hover": "#0C4A6E",
        "aqua": "#00F0FF",
        "azul_acero": "#0284C7",
        "azul_pastel": "#38BDF8",
        "amarillo": "#FDE047",
        "fucsia": "#2DD4BF",
        "logo_colors": ["#00F0FF", "#38BDF8", "#0284C7", "#FDE047"],
        "corner_radius": 16,
        "corner_btn": 12,
    },
    "Soft 3D Encarta": {
        "mode": "dark",
        "bg_dark": "#080C14",
        "card_dark": "#121A2B",
        "sidebar": "#0D1322",
        "border": "#1E2A40",
        "text_primary": "#FFFFFF",
        "text_muted": "#94A3B8",
        "input_bg": "#162035",
        "input_border": "#283956",
        "card_hover": "#1A253C",
        "card_inner": "#1C2942",
        "aqua": "#00F5D4",
        "azul_acero": "#7C3AED",
        "azul_pastel": "#A78BFA",
        "amarillo": "#FBBF24",
        "fucsia": "#F43F5E",
        "logo_colors": ["#00F5D4", "#7C3AED", "#A78BFA", "#38BDF8"],
        "corner_radius": 26,
        "corner_btn": 22,
    },
    "Soft Neumorphism Light": {
        "mode": "light",
        "bg_dark": "#EEF2F6",
        "card_dark": "#FFFFFF",
        "sidebar": "#7C3AED",
        "border": "#E2E8F0",
        "shadow": "#CBD5E1",
        "text_primary": "#0F172A",
        "text_muted": "#64748B",
        "input_bg": "#F8FAFC",
        "input_border": "#CBD5E1",
        "card_hover": "#F1F5F9",
        "card_inner": "#F8FAFC",
        "aqua": "#00F5D4",
        "azul_acero": "#7C3AED",
        "azul_pastel": "#8B5CF6",
        "amarillo": "#F59E0B",
        "fucsia": "#EC4899",
        "logo_colors": ["#7C3AED", "#EC4899", "#8B5CF6", "#00F5D4"],
        "corner_radius": 30,
        "corner_btn": 25,
    }
}

# Tipografía Ejecutiva de Agencia
FONT_FAMILY = "Segoe UI"
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SUBTITLE = ("Segoe UI", 14, "bold")
FONT_HEADING = ("Segoe UI", 12, "bold")
FONT_BODY = ("Segoe UI", 11, "bold")
FONT_BODY_REGULAR = ("Segoe UI", 11)
FONT_CAPTION = ("Segoe UI", 9)

def obtener_tema_guardado() -> str:
    try:
        if os.path.exists(RUTA_CLINICA_CONF):
            with open(RUTA_CLINICA_CONF, "r", encoding="utf-8") as f:
                d = json.load(f)
                return d.get("tema_visual", "Skeuomorphism Stereo (Dark)")
    except Exception:
        pass
    return "Skeuomorphism Stereo (Dark)"

def obtener_tema_activo_dict() -> dict:
    """Retorna siempre el diccionario completo y actualizado del tema activo."""
    nombre = obtener_tema_guardado()
    return TEMAS_BIMO.get(nombre, TEMAS_BIMO["Skeuomorphism Stereo (Dark)"])

_tema_inicial = obtener_tema_guardado()
_t_init = TEMAS_BIMO.get(_tema_inicial, TEMAS_BIMO["Skeuomorphism Stereo (Dark)"])

COLOR_BG_DARK = _t_init["bg_dark"]
COLOR_CARD_DARK = _t_init["card_dark"]
COLOR_SIDEBAR = _t_init["sidebar"]
COLOR_BORDER = _t_init["border"]
COLOR_TEXT_PRIMARY = _t_init["text_primary"]
COLOR_TEXT_MUTED = _t_init["text_muted"]
COLOR_CARD_HOVER = _t_init["card_hover"]
COLOR_AQUA = _t_init["aqua"]
COLOR_AZUL_ACERO = _t_init["azul_acero"]
COLOR_AZUL_PASTEL = _t_init["azul_pastel"]
COLOR_AMARILLO = _t_init["amarillo"]
COLOR_FUCSIA = _t_init["fucsia"]
CORNER_RADIUS_CARD = _t_init["corner_radius"]
CORNER_RADIUS_BTN = _t_init["corner_btn"]
APPEARANCE_MODE = _t_init["mode"]

def guardar_tema_visual(nombre_tema: str):
    try:
        d = {}
        if os.path.exists(RUTA_CLINICA_CONF):
            with open(RUTA_CLINICA_CONF, "r", encoding="utf-8") as f:
                d = json.load(f)
        d["tema_visual"] = nombre_tema
        with open(RUTA_CLINICA_CONF, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def aplicar_tema_config(nombre_tema: str) -> dict:
    global COLOR_BG_DARK, COLOR_CARD_DARK, COLOR_SIDEBAR, COLOR_BORDER
    global COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED, COLOR_CARD_HOVER
    global COLOR_AQUA, COLOR_AZUL_ACERO, COLOR_AZUL_PASTEL, COLOR_AMARILLO, COLOR_FUCSIA
    global CORNER_RADIUS_CARD, CORNER_RADIUS_BTN, APPEARANCE_MODE

    if nombre_tema not in TEMAS_BIMO:
        nombre_tema = "Bimo Classic"
    t = TEMAS_BIMO[nombre_tema]
    COLOR_BG_DARK = t["bg_dark"]
    COLOR_CARD_DARK = t["card_dark"]
    COLOR_SIDEBAR = t["sidebar"]
    COLOR_BORDER = t["border"]
    COLOR_TEXT_PRIMARY = t["text_primary"]
    COLOR_TEXT_MUTED = t["text_muted"]
    COLOR_CARD_HOVER = t["card_hover"]
    COLOR_AQUA = t["aqua"]
    COLOR_AZUL_ACERO = t["azul_acero"]
    COLOR_AZUL_PASTEL = t["azul_pastel"]
    COLOR_AMARILLO = t["amarillo"]
    COLOR_FUCSIA = t["fucsia"]
    CORNER_RADIUS_CARD = t["corner_radius"]
    CORNER_RADIUS_BTN = t["corner_btn"]
    APPEARANCE_MODE = t["mode"]

    guardar_tema_visual(nombre_tema)
    return t

# ==========================================
# BÓVEDA ENCRIPTADA PARA PARÁMETROS TÉCNICOS (GROQ / WHISPER)
# ==========================================
# Impide que la API Key o los modelos queden expuestos en texto plano
_VAULT_SALT = b"BIMO_VAULT_ENCRYPTED_PARAM_SALT_2026"

def _get_vault_fernet() -> Fernet:
    hwid = obtener_hwid_equipo()
    key = base64.urlsafe_b64encode(hashlib.pbkdf2_hmac("sha256", hwid.encode(), _VAULT_SALT, 30_000))
    return Fernet(key)

def inicializar_boveda_si_no_existe():
    if not os.path.exists(RUTA_VAULT):
        fernet = _get_vault_fernet()
        params_default = {
            "groq_api_key": os.getenv("GROQ_API_KEY", ""),
            "groq_model": "llama-3.3-70b-versatile",
            "whisper_model": "small"
        }
        enc_data = fernet.encrypt(json.dumps(params_default).encode("utf-8"))
        with open(RUTA_VAULT, "wb") as f:
            f.write(enc_data)

def obtener_parametro_boveda(clave: str, default=""):
    try:
        inicializar_boveda_si_no_existe()
        fernet = _get_vault_fernet()
        with open(RUTA_VAULT, "rb") as f:
            data = fernet.decrypt(f.read())
        params = json.loads(data.decode("utf-8"))
        return params.get(clave, default)
    except Exception:
        return default

# Variables de acceso transparente al motor IA (ocultas para el usuario)
def get_groq_api_key() -> str:
    return os.getenv("GROQ_API_KEY") or obtener_parametro_boveda("groq_api_key")

def get_groq_model() -> str:
    return os.getenv("GROQ_MODEL") or obtener_parametro_boveda("groq_model", "openai/gpt-oss-120b")

def get_whisper_model() -> str:
    return os.getenv("WHISPER_MODEL") or obtener_parametro_boveda("whisper_model", "small")

# Configuración Servidor Móvil
MOBILE_SERVER_PORT = int(os.getenv("MOBILE_SERVER_PORT", "8765"))

# ==========================================
# DATOS DEL CONSULTORIO Y MÉDICO (EDITABLES EN UI)
# ==========================================
def cargar_datos_clinica() -> dict:
    if os.path.exists(RUTA_CLINICA_CONF):
        try:
            with open(RUTA_CLINICA_CONF, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "nombre_clinica": "BIMO Dental Clinic",
        "nombre_doctor": "Dr. Mateo",
        "registro_profesional": "RP-ODONT-2026",
        "telefono_contacto": "+57 300 123 4567",
        "modo_bajo_rendimiento": False,
        "onboarding_completado": False,
        "pin_rapido": "1234"
    }

def guardar_datos_clinica(datos: dict):
    with open(RUTA_CLINICA_CONF, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2)

# ==========================================
# COMPATIBILIDAD MULTIPLATAFORMA NATIVA (WINDOWS .EXE / MACOS .APP)
# ==========================================
def abrir_archivo_o_carpeta_nativo(ruta: str | Path):
    """
    Abre archivos o carpetas usando los comandos nativos de cada sistema operativo:
    - Windows: os.startfile
    - macOS: subprocess open
    - Linux: subprocess xdg-open
    """
    import platform
    import subprocess
    ruta_str = str(ruta)
    sistema = platform.system()
    try:
        if sistema == "Windows":
            os.startfile(ruta_str)
        elif sistema == "Darwin":  # macOS
            subprocess.run(["open", ruta_str], check=False)
        else:  # Linux / Unix
            subprocess.run(["xdg-open", ruta_str], check=False)
    except Exception as e:
        print(f"[CROSS-PLATFORM] Error abriendo {ruta_str}: {e}")

# ==========================================
# GESTIÓN DE MODO BAJO RENDIMIENTO (LOW-END PC)
# ==========================================
def es_modo_bajo_rendimiento() -> bool:
    d = cargar_datos_clinica()
    return bool(d.get("modo_bajo_rendimiento", False))

def set_modo_bajo_rendimiento(activo: bool):
    d = cargar_datos_clinica()
    d["modo_bajo_rendimiento"] = bool(activo)
    guardar_datos_clinica(d)

# ==========================================
# GESTIÓN DE ONBOARDING Y LOGIN INTELIGENTE CON PIN
# ==========================================
def es_onboarding_completado() -> bool:
    d = cargar_datos_clinica()
    return bool(d.get("onboarding_completado", False))

def set_onboarding_completado(completado: bool = True):
    d = cargar_datos_clinica()
    d["onboarding_completado"] = bool(completado)
    guardar_datos_clinica(d)

def obtener_pin_doctor() -> str:
    d = cargar_datos_clinica()
    return str(d.get("pin_rapido", "1234")).strip()

def guardar_pin_doctor(pin: str):
    d = cargar_datos_clinica()
    d["pin_rapido"] = str(pin).strip()
    guardar_datos_clinica(d)

def obtener_ultimo_usuario_recordado() -> dict | None:
    d = cargar_datos_clinica()
    return d.get("ultimo_usuario_recordado")

def guardar_ultimo_usuario_recordado(usuario: dict | None):
    d = cargar_datos_clinica()
    d["ultimo_usuario_recordado"] = usuario
    guardar_datos_clinica(d)

# ==========================================
# LOCALIZACIÓN CANÓNICA EN ESPAÑOL DE FECHAS
# ==========================================
DIAS_SEMANA_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

def formatear_fecha_es(dt=None) -> str:
    """Devuelve la fecha en español: 'Miércoles, 02 de Septiembre de 2026'."""
    import datetime
    if dt is None:
        dt = datetime.datetime.now()
    elif isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
        dt = datetime.datetime.combine(dt, datetime.time.min)
    
    dia_nom = DIAS_SEMANA_ES[dt.weekday()]
    mes_nom = MESES_ES[dt.month - 1]
    return f"{dia_nom}, {dt.day:02d} de {mes_nom} de {dt.year}"

def formatear_fecha_corta_es(dt=None) -> str:
    """Devuelve fecha corta en español: 'Mié 02 Sep'."""
    import datetime
    if dt is None:
        dt = datetime.datetime.now()
    elif isinstance(dt, datetime.date) and not isinstance(dt, datetime.datetime):
        dt = datetime.datetime.combine(dt, datetime.time.min)

    dia_corto = DIAS_SEMANA_ES[dt.weekday()][:3]
    mes_corto = MESES_ES[dt.month - 1][:3]
    return f"{dia_corto} {dt.day:02d} {mes_corto}"
