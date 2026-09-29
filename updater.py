import os
import sys
import threading
import urllib.request
from pathlib import Path

VERSION_ACTUAL = "2.4.0"
URL_VERSION_REMOTA = "https://raw.githubusercontent.com/BimoSaaS/updates/main/version.txt"
URL_PAQUETE_REMOTO = "https://raw.githubusercontent.com/BimoSaaS/updates/main/bimo_update.zip"

import re
import tempfile

def _parse_version(v_str: str) -> tuple:
    try:
        nums = [int(p) for p in re.findall(r'\d+', str(v_str))]
        return tuple(nums) if nums else (0,)
    except Exception:
        return (0,)

def _chequear_actualizacion():
    try:
        req = urllib.request.Request(URL_VERSION_REMOTA, headers={'User-Agent': 'BIMO-Updater/2.4'})
        with urllib.request.urlopen(req, timeout=5) as response:
            version_remota = response.read().decode('utf-8').strip()

        if version_remota and _parse_version(version_remota) > _parse_version(VERSION_ACTUAL):
            print(f"[UPDATER] Nueva versión detectada: v{version_remota} (Actual: v{VERSION_ACTUAL})")
            # Descargar a directorio temporal seguro del sistema sin aplicar automáticamente
            ruta_zip = os.path.join(tempfile.gettempdir(), f"bimo_update_{version_remota}.zip")
            urllib.request.urlretrieve(URL_PAQUETE_REMOTO, ruta_zip)
            print(f"[UPDATER] Paquete de actualización descargado en segundo plano en {ruta_zip} listo para revisión.")
    except Exception:
        # Modo silencioso para no interrumpir el arranque clínico si no hay conexión
        pass

def iniciar_verificacion_actualizacion():
    """Inicia la consulta silenciosa en un hilo secundario al encender BIMO."""
    threading.Thread(target=_chequear_actualizacion, daemon=True).start()

if __name__ == "__main__":
    print(f"BIMO Updater v{VERSION_ACTUAL} - Verificando repositorio remoto...")
    _chequear_actualizacion()
