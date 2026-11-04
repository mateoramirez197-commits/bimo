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

    # 2. Preparar directorio de staging limpio y empaquetar en ZIP
    print("\n[PASO 2/3] Preparando staging y empaquetando distribución en payload comprimido (bimo_payload.zip)...")
    from verificar_payload import es_archivo_prohibido, verificar_zip_payload, calcular_sha256

    staging_dir = os.path.join(base_dir, "dist_staging")
    if os.path.exists(staging_dir):
        shutil.rmtree(staging_dir, ignore_errors=True)
    os.makedirs(staging_dir, exist_ok=True)

    # Copiar a staging aplicando la lista negra
    for root, dirs, files in os.walk(dist_app_dir):
        rel_root = os.path.relpath(root, dist_app_dir)
        if rel_root == ".":
            rel_root = ""
        for file in files:
            rel_file = os.path.join(rel_root, file) if rel_root else file
            prohibido, motivo = es_archivo_prohibido(rel_file)
            if prohibido:
                print(f"      [OMITIDO BLACKLIST]: {rel_file} ({motivo})")
                continue
            dest_file = os.path.join(staging_dir, rel_file)
            os.makedirs(os.path.dirname(dest_file), exist_ok=True)
            shutil.copy2(os.path.join(root, file), dest_file)

    payload_zip = os.path.join(base_dir, "dist", "bimo_payload.zip")
    if os.path.exists(payload_zip):
        os.remove(payload_zip)

    with zipfile.ZipFile(payload_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, dirs, files in os.walk(staging_dir):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, staging_dir)
                zf.write(abs_path, rel_path)

    # Limpiar staging
    try:
        shutil.rmtree(staging_dir, ignore_errors=True)
    except Exception:
        pass

    # Puerta de Auditoría Estricta: verificar_payload
    print("\n[AUDITORIA] Ejecutando puerta de auditoria sobre bimo_payload.zip...")
    es_valido, violaciones, stats = verificar_zip_payload(payload_zip)
    if not es_valido:
        print("[ERROR CRITICO DE SEGURIDAD] El payload contiene archivos prohibidos:")
        for v_arch, v_razon in violaciones:
            print(f"  [X] {v_arch}: {v_razon}")
        raise RuntimeError("Auditoría de seguridad del payload falló. Empaquetado cancelado.")

    print(f"      -> Payload auditado y verificado limpio (0 prohibidos).")
    print(f"      -> Total archivos: {stats.get('total_archivos')}, Tamaño: {stats.get('tamano_mb', 0):.1f} MB.")
    print(f"      -> SHA-256 payload: {stats.get('sha256')}")

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
        setup_sha = calcular_sha256(setup_final)
        print("\n" + "=" * 65)
        print("   ¡SETUP_BIMO_PRO.EXE CONSTRUIDO Y AUDITADO EXITOSAMENTE!")
        print("=" * 65)
        print(f"Ruta:    {setup_final}")
        print(f"Tamaño:  {setup_size_mb:.1f} MB ({os.path.getsize(setup_final)} bytes)")
        print(f"SHA-256: {setup_sha}")
        print("Este archivo es el instalador seguro para llevar en USB sin datos de pacientes.")
    else:
        print("\n[ERROR] No se encontró el archivo generado Setup_BIMO_Pro.exe.")

if __name__ == '__main__':
    crear_setup()
