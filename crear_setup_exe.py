# -*- coding: utf-8 -*-
"""
Constructor del Instalador Ejecutable Universal (Setup_BIMO_Pro.exe)
Empaqueta la distribución compilada dist/BIMO_Pro dentro de un instalador ejecutable único.
"""
import os
import sys
import shutil
import zipfile
import subprocess

def crear_setup():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dist_app_dir = os.path.join(base_dir, "dist", "BIMO_Pro")
    
    print("=" * 65)
    print("      CONSTRUCTOR DEL INSTALADOR SETUP_BIMO_PRO.EXE")
    print("=" * 65)
    
    # 1. Asegurar que la app base este compilada
    if not os.path.exists(dist_app_dir) or not os.path.exists(os.path.join(dist_app_dir, "BIMO_Pro.exe")):
        print("\n[PASO 1/3] Compilando BIMO Pro con PyInstaller (build_exe.py)...")
        subprocess.check_call([sys.executable, os.path.join(base_dir, "build_exe.py")])
    else:
        print("\n[PASO 1/3] Distribución binaria dist/BIMO_Pro/ detectada.")

    # Asegurar que Uninstall.exe esté dentro de dist/BIMO_Pro
    uninstall_src = os.path.join(base_dir, "dist", "Uninstall.exe")
    uninstall_dst = os.path.join(dist_app_dir, "Uninstall.exe")
    if os.path.exists(uninstall_src) and not os.path.exists(uninstall_dst):
        shutil.copy2(uninstall_src, uninstall_dst)
        print("      -> Uninstall.exe integrado en la distribución.")
    elif os.path.exists(uninstall_src) and os.path.exists(uninstall_dst):
        shutil.copy2(uninstall_src, uninstall_dst)
        print("      -> Uninstall.exe actualizado en la distribución.")

    # 2. Empaquetar dist/BIMO_Pro en un ZIP comprimido
    print("\n[PASO 2/3] Empaquetando distribución en payload comprimido (bimo_payload.zip)...")
    payload_zip = os.path.join(base_dir, "dist", "bimo_payload.zip")
    if os.path.exists(payload_zip):
        os.remove(payload_zip)

    with zipfile.ZipFile(payload_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(dist_app_dir):
            for file in files:
                if file in ("bimo.lic", "bimo_modern_error.log"):
                    continue
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, dist_app_dir)
                zf.write(abs_path, rel_path)
    
    zip_size_mb = os.path.getsize(payload_zip) / (1024 * 1024)
    print(f"      -> Payload generado con éxito: {zip_size_mb:.1f} MB.")

    # 3. Compilar instalador ejecutable autónomo con PyInstaller
    print("\n[PASO 3/3] Compilando instalador ejecutable final (Setup_BIMO_Pro.exe)...")
    ico_path = os.path.join(base_dir, "assets", "bimo_icon.ico")
    
    cmd_setup = [
        sys.executable, "-m", "PyInstaller",
        "--name=Setup_BIMO_Pro",
        "--onefile",
        "--noconsole",
        "--clean",
        "--noconfirm",
        "-y",
        f"--add-data={payload_zip};.",
        f"--add-data={os.path.join(base_dir, 'assets')};assets",
        os.path.join(base_dir, "installer_gui_wizard.py")
    ]
    if os.path.exists(ico_path):
        cmd_setup.insert(4, f"--icon={ico_path}")

    subprocess.check_call(cmd_setup, cwd=base_dir)

    setup_final = os.path.join(base_dir, "dist", "Setup_BIMO_Pro.exe")
    if os.path.exists(setup_final):
        setup_size_mb = os.path.getsize(setup_final) / (1024 * 1024)
        print("\n" + "=" * 65)
        print("   ¡SETUP_BIMO_PRO.EXE CONSTRUIDO EXITOSAMENTE!")
        print("=" * 65)
        print(f"Ruta: {setup_final}")
        print(f"Tamaño: {setup_size_mb:.1f} MB")
        print("Este archivo es el instalador que puedes llevarte a la otra computadora.")
    else:
        print("\n[ERROR] No se encontró el archivo generado Setup_BIMO_Pro.exe.")

if __name__ == '__main__':
    crear_setup()
