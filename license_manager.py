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

def _resolver_ruta_licencia(for_write=False) -> Path:
    local_app = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    cand_local = Path(local_app) / "BIMO_Pro" / "bimo.lic"

    if not for_write:
        for c in [BASE_DIR / "bimo.lic", cand_local]:
            if c.exists():
                return c
        return BASE_DIR / "bimo.lic"
    else:
        try:
            BASE_DIR.mkdir(parents=True, exist_ok=True)
            test_f = BASE_DIR / f".lic_write_test_{os.getpid()}"
            with open(test_f, "w") as tf:
                tf.write("ok")
            test_f.unlink()
            return BASE_DIR / "bimo.lic"
        except Exception:
            cand_local.parent.mkdir(parents=True, exist_ok=True)
            return cand_local

def obtener_hwid_equipo() -> str:
    r"""
    Obtiene la huella física y criptográfica del equipo Windows (L-C):
    Usa MachineGuid del Registro de Windows (HKLM\SOFTWARE\Microsoft\Cryptography).
    Estable y desacoplado de interfaces de red / MACs móviles.
    """
    if os.environ.get("BIMO_DEV_BACKDOOR") == "1" and os.environ.get("BIMO_TEST_HWID"):
        return os.environ.get("BIMO_TEST_HWID").strip().upper()

    guid = "WIN-DEFAULT-GUID"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, 
            r"SOFTWARE\Microsoft\Cryptography", 
            0, 
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        )
        val, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        guid = str(val).strip()
    except Exception:
        pass

    return hashlib.sha256(guid.encode("utf-8")).hexdigest()[:32].upper()

def obtener_hwid_legado() -> str:
    r"""
    Huella criptográfica legada (MachineGuid + MAC uuid.getnode).
    Utilizada exclusivamente para migración transparente de bimo.vault y bimo.lic (L-C).
    """
    componentes = []
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, 
            r"SOFTWARE\Microsoft\Cryptography", 
            0, 
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        )
        val, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        componentes.append(str(val).strip())
    except Exception:
        componentes.append("WIN-DEFAULT-GUID")
    try:
        componentes.append(str(uuid.getnode()))
    except Exception:
        componentes.append("NODE-00")

    raw_fingerprint = ":".join(componentes)
    return hashlib.sha256(raw_fingerprint.encode("utf-8")).hexdigest()[:32].upper()

def activar_licencia_equipo(email_doctor: str) -> bool:
    email_limpio = str(email_doctor).strip().lower()
    if not email_limpio or "@" not in email_limpio:
        email_limpio = "doctor@bimo.local"

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

    ruta_dest = _resolver_ruta_licencia(for_write=True)
    try:
        with open(ruta_dest, "wb") as f:
            f.write(licencia_encriptada)
        print(f"[LICENCIA] Activación exitosa para {email_limpio} en equipo {hwid[:8]} en: {ruta_dest}")
        return True
    except Exception as e:
        print(f"[LICENCIA SAVE ERROR]: {e}")
        return False

def validar_licencia() -> tuple[bool, dict]:
    hwid_actual = obtener_hwid_equipo()
    ruta_lic = _resolver_ruta_licencia(for_write=False)
    if not os.path.exists(ruta_lic):
        try:
            print(f"[LICENCIA] Primera ejecución detectada. Vinculando licencia permanente a este equipo ({hwid_actual[:8]})...")
            activar_licencia_equipo("doctor@bimo.local")
            ruta_lic = _resolver_ruta_licencia(for_write=False)
        except Exception as e_init:
            print(f"[LICENCIA WARN] Auto-activación falló: {e_init}")
            return False, {"motivo": "LICENCIA_INEXISTENTE", "hwid": hwid_actual}

    if not os.path.exists(ruta_lic):
        return False, {"motivo": "LICENCIA_INEXISTENTE", "hwid": hwid_actual}

    try:
        with open(ruta_lic, "rb") as f:
            licencia_encriptada = f.read()

        payload = None
        # 1. Intentar descifrado con HWID actual (MachineGuid)
        try:
            fernet = Fernet(_generar_fernet_key(hwid_actual))
            datos_json = fernet.decrypt(licencia_encriptada)
            payload = json.loads(datos_json.decode("utf-8"))
        except Exception:
            # 2. Intentar descifrado con HWID legado (con MAC) para migración transparente (L-C)
            hwid_leg = obtener_hwid_legado()
            try:
                fernet_leg = Fernet(_generar_fernet_key(hwid_leg))
                datos_json = fernet_leg.decrypt(licencia_encriptada)
                payload = json.loads(datos_json.decode("utf-8"))
                # Migración: re-cifrar con HWID actual
                payload["hwid"] = hwid_actual
                payload["signature"] = hashlib.sha256(f"{payload.get('email','')}::{hwid_actual}::{_SECRET_SALT.decode()}".encode()).hexdigest()
                activar_licencia_equipo(payload.get("email", "doctor@bimo.local"))
                print(f"[LICENCIA MIGRATION] Licencia migrada exitosamente desde HWID legado a MachineGuid.")
            except Exception:
                payload = None

        # Si no descifra o el HWID no coincide (equipo nuevo / archivo copiado ajeno) -> Auto-reactivación resiliente (L-B)
        necesita_reactivar = False
        if payload is None:
            necesita_reactivar = True
        elif payload.get("hwid") != hwid_actual:
            necesita_reactivar = True
        else:
            email = payload.get("email", "")
            firma_esperada = hashlib.sha256(f"{email}::{hwid_actual}::{_SECRET_SALT.decode()}".encode()).hexdigest()
            if payload.get("signature") != firma_esperada:
                necesita_reactivar = True

        if necesita_reactivar:
            # Renombrar licencia ajena/corrupta a bimo.lic.ajeno-<timestamp> y auto-reactivar para este equipo
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            bak_lic = f"{ruta_lic}.ajeno-{ts}"
            try:
                os.rename(ruta_lic, bak_lic)
                print(f"[LICENCIA RESILIENTE] Licencia previa de otra máquina respaldada como: {bak_lic}")
            except Exception as e_ren:
                print(f"[LICENCIA RESILIENTE WARN] No se pudo renombrar licencia previa: {e_ren}")

            activar_licencia_equipo("doctor@bimo.local")
            return True, {"reactivada": True, "hwid": hwid_actual, "email": "doctor@bimo.local"}

        return True, payload
    except Exception as e:
        print(f"[LICENCIA ERROR] Error al validar licencia: {e}")
        try:
            activar_licencia_equipo("doctor@bimo.local")
            return True, {"reactivada": True, "hwid": hwid_actual, "email": "doctor@bimo.local"}
        except Exception:
            return False, {"motivo": "ERROR_DESCIFRADO", "hwid": hwid_actual}

def resetear_licencia():
    """
    Elimina el archivo bimo.lic para permitir pruebas reiteradas en desarrollo.
    """
    ruta_lic = _resolver_ruta_licencia(for_write=False)
    if os.path.exists(ruta_lic):
        try:
            os.remove(ruta_lic)
            print("[TEST MODE] bimo.lic eliminado para permitir una nueva activación de prueba.")
            return True
        except Exception:
            return False
    return True
