import os
import winreg
import uuid
import hashlib
import json
import base64
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet

import sys

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

RUTA_LICENCIA = BASE_DIR / "bimo.lic"

_SECRET_SALT = b"BIMO_SAAS_CLINICAL_SECURE_SALT_2026_V1"

def _generar_fernet_key(hwid: str) -> bytes:
    key_bytes = hashlib.pbkdf2_hmac("sha256", hwid.encode(), _SECRET_SALT, 50_000)
    return base64.urlsafe_b64encode(key_bytes)

def obtener_hwid_equipo() -> str:
    r"""
    Obtiene la huella física y criptográfica inmutable del equipo Windows:
    1. MachineGuid del Registro de Windows (HKLM\SOFTWARE\Microsoft\Cryptography)
    2. MAC Address del hardware de red principal (uuid.getnode)
    """
    componentes = []
    
    # 1. Windows MachineGuid
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, 
            r"SOFTWARE\Microsoft\Cryptography", 
            0, 
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        )
        machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        componentes.append(str(machine_guid).strip())
    except Exception:
        componentes.append("WIN-DEFAULT-GUID")

    # 2. MAC Node
    try:
        node_id = str(uuid.getnode())
        componentes.append(node_id)
    except Exception:
        componentes.append("NODE-00")

    raw_fingerprint = ":".join(componentes)
    hwid = hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()[:32].upper()
    return hwid

def activar_licencia_equipo(email_doctor: str) -> bool:
    email_limpio = str(email_doctor).strip().lower()
    if not email_limpio or "@" not in email_limpio:
        return False

    hwid = obtener_hwid_equipo()
    fernet_key = _generar_fernet_key(hwid)
    fernet = Fernet(fernet_key)

    payload = {
        "email": email_limpio,
        "hwid": hwid,
        "fecha_activacion": datetime.now().isoformat(),
        "tipo_licencia": "PRO_CLINICAL_SAAS",
        "signature": hashlib.sha256(f"{email_limpio}::{hwid}::{_SECRET_SALT.decode()}".encode()).hexdigest()
    }

    datos_json = json.dumps(payload).encode("utf-8")
    licencia_encriptada = fernet.encrypt(datos_json)

    with open(RUTA_LICENCIA, "wb") as f:
        f.write(licencia_encriptada)

    print(f"[LICENCIA] Activación exitosa para {email_limpio} en equipo {hwid[:8]}...")
    return True

def validar_licencia() -> tuple[bool, dict]:
    hwid_actual = obtener_hwid_equipo()
    if not os.path.exists(RUTA_LICENCIA):
        # Auto-activación inicial por hardware en la primera ejecución
        try:
            print(f"[LICENCIA] Primera ejecución detectada. Vinculando licencia permanente a este equipo ({hwid_actual[:8]})...")
            activar_licencia_equipo("mateoramirez@bimo.local")
        except Exception as e_init:
            print(f"[LICENCIA WARN] Auto-activación falló: {e_init}")
            return False, {"motivo": "LICENCIA_INEXISTENTE", "hwid": hwid_actual}

    try:
        fernet_key = _generar_fernet_key(hwid_actual)
        fernet = Fernet(fernet_key)

        with open(RUTA_LICENCIA, "rb") as f:
            licencia_encriptada = f.read()

        datos_json = fernet.decrypt(licencia_encriptada)
        payload = json.loads(datos_json.decode("utf-8"))

        if payload.get("hwid") != hwid_actual:
            print(f"[SEGURIDAD] ALERTA CRÍTICA: Intento de ejecución no autorizada. El hardware ({hwid_actual[:8]}) no coincide con la licencia.")
            return False, {"motivo": "HWID_NO_COINCIDE", "hwid": hwid_actual, "email": payload.get("email")}

        email = payload.get("email", "")
        firma_esperada = hashlib.sha256(f"{email}::{hwid_actual}::{_SECRET_SALT.decode()}".encode()).hexdigest()
        if payload.get("signature") != firma_esperada:
            print("[SEGURIDAD] ALERTA CRÍTICA: Firma criptográfica alterada o inválida.")
            return False, {"motivo": "FIRMA_INVALIDA", "hwid": hwid_actual}

        return True, payload
    except Exception as e:
        print(f"[SEGURIDAD] Acceso denegado: Fallo de descifrado de licencia por hardware incompatible ({e}).")
        return False, {"motivo": "ERROR_DESCIFRADO", "hwid": hwid_actual}

def resetear_licencia():
    """
    Elimina el archivo bimo.lic para permitir pruebas reiteradas en desarrollo.
    """
    if os.path.exists(RUTA_LICENCIA):
        try:
            os.remove(RUTA_LICENCIA)
            print("[TEST MODE] bimo.lic eliminado para permitir una nueva activación de prueba.")
            return True
        except Exception:
            return False
    return True
