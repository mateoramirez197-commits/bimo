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
    
    incluir_env = "--incluir-env" in sys.argv
    if incluir_env:
        print("[ADVERTENCIA SEGURIDAD] Se ha especificado --incluir-env. El archivo .env con credenciales se empaquetara en la distribucion.")

    import customtkinter
    ctk_path = os.path.dirname(customtkinter.__file__)

    add_data = [
        f"{os.path.join(base_dir, 'web_ui')};web_ui",
        f"{os.path.join(base_dir, 'assets')};assets",
        f"{ctk_path};customtkinter"
    ]

    archivos_permitidos = [
        "credentials.json",
        "base_odontograma.png",
        "mascaras_odontograma.npz",
        "clinica.default.json",
    ]
    if os.path.exists(os.path.join(base_dir, "vocabulario_aprendido.default.json")):
        archivos_permitidos.append("vocabulario_aprendido.default.json")
    elif os.path.exists(os.path.join(base_dir, "vocabulario_aprendido.json")):
        archivos_permitidos.append("vocabulario_aprendido.json")

    if incluir_env and os.path.exists(os.path.join(base_dir, ".env")):
        archivos_permitidos.append(".env")

    for archivo_extra in archivos_permitidos:
        p = os.path.join(base_dir, archivo_extra)
        if os.path.exists(p):
            add_data.append(f"{p};.")

    ico_path = os.path.join(base_dir, "assets", "bimo_icon.ico")

    # Limpiar dist/BIMO_Pro antes de compilar para no arrastrar residuos de ejecuciones previas
    dist_bimo = os.path.join(base_dir, "dist", "BIMO_Pro")
    if os.path.exists(dist_bimo):
        print("[INFO] Limpiando carpeta dist/BIMO_Pro existente...")
        try:
            shutil.rmtree(dist_bimo, ignore_errors=True)
        except Exception as e_rm:
            print(f"[WARN] No se pudo limpiar dist/BIMO_Pro por completo: {e_rm}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=BIMO_Pro",
        "--noconsole",
        "--clean",
        "--noconfirm",
        "-y",
        "--onedir",
        f"--icon={ico_path}" if os.path.exists(ico_path) else "",
        "--collect-all=webview",
        "--collect-all=pythonnet",
        "--collect-all=customtkinter",
        "--collect-all=faster_whisper",
        "--collect-all=onnxruntime",
        "--collect-all=googleapiclient",
        "--collect-all=google_auth_oauthlib",
        "--collect-data=google",
        "--hidden-import=webview",
        "--hidden-import=webview.platforms.winforms",
        "--hidden-import=webview.platforms.edgechromium",
        "--hidden-import=webview.platforms.mshtml",
        "--hidden-import=clr",
        "--hidden-import=pythonnet",
        "--hidden-import=faster_whisper",
        "--hidden-import=ctranslate2",
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
        "--hidden-import=google.oauth2",
        "--hidden-import=httplib2",
        "--hidden-import=uritemplate",
        "--hidden-import=drive_backup",
        "--hidden-import=audio_feedback",
        "--hidden-import=calendar_sync",
        "--hidden-import=openpyxl",
        "--hidden-import=qrcode",
        "--hidden-import=cryptography",
        "--hidden-import=dotenv",
        "--hidden-import=pandas",
        "--hidden-import=requests",
        "--hidden-import=aiohttp",
        "--hidden-import=websockets",
    ]
    cmd = [c for c in cmd if c]

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
        
        uninstall_src = os.path.join(base_dir, "dist", "Uninstall.exe")
        uninstall_dst = os.path.join(dist_bimo, "Uninstall.exe")
        if os.path.exists(uninstall_src):
            shutil.copy2(uninstall_src, uninstall_dst)
            print("[OK] Uninstall.exe copiado exitosamente dentro de dist/BIMO_Pro/")

        web_ui_dst = os.path.join(dist_bimo, "web_ui")
        if os.path.exists(web_ui_dst):
            shutil.rmtree(web_ui_dst, ignore_errors=True)
        shutil.copytree(os.path.join(base_dir, "web_ui"), web_ui_dst)
        print("[OK] web_ui sincronizado directamente en dist/BIMO_Pro/web_ui")

        assets_dst = os.path.join(dist_bimo, "assets")
        if os.path.exists(assets_dst):
            shutil.rmtree(assets_dst, ignore_errors=True)
        shutil.copytree(os.path.join(base_dir, "assets"), assets_dst)
        print("[OK] assets sincronizado directamente en dist/BIMO_Pro/assets")

        # Copiar solo archivos plantilla permitidos directamente a dist/BIMO_Pro (P-A: sin bimo.db, sin Pacientes, sin .env, sin clinica.json)
        archivos_copia_dist = ["base_odontograma.png", "mascaras_odontograma.npz", "credentials.json", "clinica.default.json"]
        if os.path.exists(os.path.join(base_dir, "vocabulario_aprendido.default.json")):
            archivos_copia_dist.append("vocabulario_aprendido.default.json")
        elif os.path.exists(os.path.join(base_dir, "vocabulario_aprendido.json")):
            archivos_copia_dist.append("vocabulario_aprendido.json")

        if incluir_env and os.path.exists(os.path.join(base_dir, ".env")):
            archivos_copia_dist.append(".env")

        for f_extra in archivos_copia_dist:
            src_f = os.path.join(base_dir, f_extra)
            dst_f = os.path.join(dist_bimo, f_extra)
            if os.path.exists(src_f):
                shutil.copy2(src_f, dst_f)

        print("[OK] Archivos de plantilla y dependencias seguras copiados a dist/BIMO_Pro")

        # Garantizar que los modelos ONNX de VAD de faster_whisper estén en su ruta de assets
        try:
            import faster_whisper
            fw_assets_src = os.path.join(os.path.dirname(faster_whisper.__file__), "assets")
            fw_assets_dst = os.path.join(dist_bimo, "_internal", "faster_whisper", "assets")
            if os.path.exists(fw_assets_src):
                shutil.copytree(fw_assets_src, fw_assets_dst, dirs_exist_ok=True)
                print("[OK] Assets de Faster-Whisper (Silero VAD ONNX) sincronizados en _internal/faster_whisper/assets")
        except Exception as e_fw_copy:
            print(f"[WARN] No se pudieron copiar assets de faster_whisper: {e_fw_copy}")
    except Exception as e:
        print(f"\n[ERROR] Error durante la compilacion: {e}")

if __name__ == '__main__':
    compilar_bimo_exe()
