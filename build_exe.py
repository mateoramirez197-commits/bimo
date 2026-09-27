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
        f"{os.path.join(base_dir, 'web_ui')};web_ui",
        f"{os.path.join(base_dir, 'assets')};assets",
        f"{ctk_path};customtkinter"
    ]

    for archivo_extra in ["cert.pem", "key.pem", "clinica.json", "credentials.json", ".env", "vocabulario_aprendido.json", "base_odontograma.png", "mascaras_odontograma.npz"]:
        p = os.path.join(base_dir, archivo_extra)
        if os.path.exists(p):
            add_data.append(f"{p};.")

    ico_path = os.path.join(base_dir, "assets", "bimo_icon.ico")

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
        
        dist_bimo = os.path.join(base_dir, "dist", "BIMO_Pro")
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

        # Sincronizar base de datos con todos los pacientes y consultas históricas
        db_src = os.path.join(base_dir, "bimo.db")
        db_dst = os.path.join(dist_bimo, "bimo.db")
        if os.path.exists(db_src):
            shutil.copy2(db_src, db_dst)
            print("[OK] bimo.db con historial de pacientes copiado a dist/BIMO_Pro/")

        # Sincronizar expedientes y PDFs de pacientes
        pac_src = os.path.join(base_dir, "Pacientes")
        pac_dst = os.path.join(dist_bimo, "Pacientes")
        if os.path.exists(pac_src):
            if not os.path.exists(pac_dst):
                shutil.copytree(pac_src, pac_dst)
            else:
                for root, dirs, files in os.walk(pac_src):
                    rel = os.path.relpath(root, pac_src)
                    dest_sub = os.path.join(pac_dst, rel)
                    os.makedirs(dest_sub, exist_ok=True)
                    for f in files:
                        s_file = os.path.join(root, f)
                        d_file = os.path.join(dest_sub, f)
                        if not os.path.exists(d_file):
                            shutil.copy2(s_file, d_file)
            print("[OK] Pacientes/ (expedientes clínicos y PDFs) sincronizado en dist/BIMO_Pro/Pacientes")

        # Copiar archivos raíz del sistema directamente a dist/BIMO_Pro
        for f_extra in [".env", "clinica.json", "base_odontograma.png", "mascaras_odontograma.npz", "credentials.json", "vocabulario_aprendido.json", "cert.pem", "key.pem"]:
            src_f = os.path.join(base_dir, f_extra)
            dst_f = os.path.join(dist_bimo, f_extra)
            if os.path.exists(src_f):
                shutil.copy2(src_f, dst_f)

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
