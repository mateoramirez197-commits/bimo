import os
import sys
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def compilar_instalador():
    print("=" * 60)
    print("📦 COMPILACIÓN Y EMPAQUETADO COMERCIAL BIMO")
    print("=" * 60)

    # 1. Asegurar que base_odontograma.png exista
    if not (BASE_DIR / "base_odontograma.png").exists():
        print("[ERROR] base_odontograma.png no encontrada en el directorio raíz.")
        return False

    # 2. Ejecutar PyInstaller con bimo.spec
    comando = [sys.executable, "-m", "PyInstaller", "--noconfirm", "bimo.spec"]
    print(f"Ejecutando: {' '.join(comando)}")
    resultado = subprocess.run(comando, cwd=str(BASE_DIR))

    if resultado.returncode == 0:
        dist_exe = BASE_DIR / "dist" / "BIMO_Clinico" / "BIMO_Clinico.exe"
        print("\n" + "=" * 60)
        print("✅ COMPILACIÓN EXITOSA")
        print(f"Ejecutable generado en: {dist_exe}")
        print("El software está protegido contra clonación mediante HWID.")
        print("=" * 60)
        return True
    else:
        print("\n[ERROR] Ocurrió un problema durante la compilación con PyInstaller.")
        return False

if __name__ == "__main__":
    compilar_instalador()
