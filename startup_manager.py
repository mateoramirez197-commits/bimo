import sys
import winreg
from pathlib import Path

REG_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "BIMO_Clinico"

def esta_registrado_en_inicio() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return bool(val)
    except Exception:
        return False

def registrar_en_inicio_windows(ruta_ejecutable: str = None) -> bool:
    """
    Registra el software Bimo para que inicie automáticamente y de forma silenciosa
    al encender el PC del consultorio.
    """
    if not ruta_ejecutable:
        ruta_ejecutable = sys.executable if getattr(sys, 'frozen', False) else str(Path(__file__).resolve().parent / "main.py")

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{ruta_ejecutable}"')
        winreg.CloseKey(key)
        print(f"[STARTUP] BIMO registrado con éxito en inicio de Windows: {ruta_ejecutable}")
        return True
    except Exception as e:
        print(f"[STARTUP] Error al registrar en inicio: {e}")
        return False

def remover_de_inicio_windows() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY_PATH, 0, winreg.KEY_SET_VALUE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        print("[STARTUP] BIMO removido del inicio de Windows.")
        return True
    except Exception as e:
        return False
