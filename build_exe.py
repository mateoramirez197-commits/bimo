import os
import sys
import subprocess
import shutil

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def compilar_bimo_exe():
    print("=========================================================")
    print("[BIMO PRO] - GENERADOR COMERCIAL DE ARCHIVO EJECUTABLE (.EXE)")
    print("=========================================================")
    
    try:
        import PyInstaller
        print("[OK] PyInstaller detectado.")
    except ImportError:
        print("[INFO] Instalando PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    import customtkinter
    ctk_path = os.path.dirname(customtkinter.__file__)

    add_data = [
        f"{os.path.join(base_dir, 'assets', 'base_odontograma.png')};assets",
        f"{os.path.join(base_dir, 'assets', 'sounds')};assets/sounds",
        f"{ctk_path};customtkinter"
    ]

    for archivo_extra in ["cert.pem", "key.pem", "clinica.json", "credentials.json"]:
        p = os.path.join(base_dir, archivo_extra)
        if os.path.exists(p):
            add_data.append(f"{p};.")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=BIMO_Pro",
        "--noconsole",
        "--clean",
        "--onedir",
        "--collect-all=customtkinter",
        "--hidden-import=faster_whisper",
        "--hidden-import=groq",
        "--hidden-import=fpdf2",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageDraw",
        "--hidden-import=pyttsx3",
        "--hidden-import=edge_tts",
        "--hidden-import=sounddevice",
        "--hidden-import=soundfile",
        "--hidden-import=scipy",
        "--hidden-import=scipy.io.wavfile",
        "--hidden-import=google_auth_oauthlib",
        "--hidden-import=googleapiclient",
        "--hidden-import=openpyxl",
        "--hidden-import=qrcode",
    ]

    for d in add_data:
        cmd.extend(["--add-data", d])

    cmd.append(os.path.join(base_dir, "main.py"))

    print("\n[INFO] Ejecutando PyInstaller (esto puede tardar unos minutos)...")
    try:
        subprocess.check_call(cmd, cwd=base_dir)
        print("\n=======================================================")
        print("[EXITO] COMPILACION COMPLETADA CORRECTAMENTE")
        print("El ejecutable comercial se encuentra en:")
        print(os.path.join(base_dir, "dist", "BIMO_Pro", "BIMO_Pro.exe"))
        print("=======================================================")
    except Exception as e:
        print(f"\n[ERROR] Error durante la compilacion: {e}")

if __name__ == '__main__':
    compilar_bimo_exe()
