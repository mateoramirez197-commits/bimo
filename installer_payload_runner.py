# -*- coding: utf-8 -*-
"""
Instalador Automático Universal BIMO Pro (Setup_BIMO_Pro.exe)
Desempaqueta la aplicación compilada, inicializa la base de datos,
auto-activa la licencia HWID del equipo y crea accesos directos.
"""
import os
import sys
import zipfile
import shutil
import subprocess
import winreg
import ctypes
from pathlib import Path

def obtener_ruta_instalacion_default():
    local_app_data = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(local_app_data, "Programs", "BIMO_Pro")

def extraer_payload(zip_path, destino_dir):
    os.makedirs(destino_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        zf.extractall(destino_dir)

def crear_acceso_directo(destino_dir, exe_path, ico_path):
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop):
            desktop = os.path.join(os.path.expanduser("~"), "Escritorio")
        
        shortcut_path = os.path.join(desktop, "BIMO Pro.lnk")
        vbs_script = os.path.join(destino_dir, "crear_shortcut.vbs")
        
        with open(vbs_script, "w", encoding="utf-8") as f:
            f.write('Set oWS = WScript.CreateObject("WScript.Shell")\n')
            f.write(f'sLinkFile = "{shortcut_path}"\n')
            f.write('Set oLink = oWS.CreateShortcut(sLinkFile)\n')
            f.write(f'oLink.TargetPath = "{exe_path}"\n')
            f.write(f'oLink.WorkingDirectory = "{destino_dir}"\n')
            f.write('oLink.Description = "BIMO Pro - Asistente Clinico Odontologico Inteligente"\n')
            if os.path.exists(ico_path):
                f.write(f'oLink.IconLocation = "{ico_path},0"\n')
            f.write('oLink.Save\n')
        
        subprocess.call(["cscript", "//nologo", vbs_script])
        if os.path.exists(vbs_script):
            os.remove(vbs_script)
        print(f"[SETUP] Acceso directo generado en: {shortcut_path}")
    except Exception as e:
        print(f"[SETUP WARN] No se pudo crear acceso directo en el Escritorio: {e}")

def main():
    print("=" * 65)
    print("      INSTALADOR OFICIAL BIMO PRO - SETUP UNIVERSAL")
    print("=" * 65)
    print("\nIniciando instalacion y configuracion en este equipo...")
    
    # 1. Localizar payload zip embebido
    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    payload_zip = os.path.join(base_dir, "bimo_payload.zip")
    
    if not os.path.exists(payload_zip):
        # Modo desarrollo: buscar en dist
        alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "bimo_payload.zip")
        if os.path.exists(alt):
            payload_zip = alt
        else:
            print("[ERROR FATAL] No se encontro el archivo bimo_payload.zip.")
            input("\nPresione Enter para salir...")
            sys.exit(1)

    destino_dir = obtener_ruta_instalacion_default()
    print(f"\n[1/4] Instalando archivos del sistema en:\n      {destino_dir}")
    
    try:
        extraer_payload(payload_zip, destino_dir)
        print("      -> Archivos binarios extraidos correctamente.")
    except Exception as e:
        print(f"[ERROR] Error al extraer archivos: {e}")
        input("\nPresione Enter para salir...")
        sys.exit(1)

    # 2. Inicializar carpetas de datos
    print("\n[2/4] Configurando expedientes clinicos y directorios...")
    os.makedirs(os.path.join(destino_dir, "Pacientes", "Pacientes_Adultos"), exist_ok=True)
    os.makedirs(os.path.join(destino_dir, "Pacientes", "Pacientes_Pediatricos"), exist_ok=True)
    os.makedirs(os.path.join(destino_dir, "data"), exist_ok=True)
    print("      -> Directorios de pacientes inicializados.")

    # 3. Crear accesos directos
    exe_path = os.path.join(destino_dir, "BIMO_Pro.exe")
    ico_path = os.path.join(destino_dir, "assets", "bimo_icon.ico")
    print("\n[3/4] Creando acceso directo en el Escritorio...")
    crear_acceso_directo(destino_dir, exe_path, ico_path)

    # 4. Autorizar licencia localmente en el nuevo equipo
    print("\n[4/4] Vinculando licencia permanente de hardware a esta PC...")
    try:
        # Ejecutar BIMO_Pro.exe en modo silencioso de inicialización para registrar HWID y DB
        cmd_init = [exe_path, "--setup-init"]
        subprocess.run(cmd_init, cwd=destino_dir, timeout=15)
        print("      -> Licencia vinculada al hardware y base de datos inicializada.")
    except Exception as e:
        print(f"      -> Advertencia al vincular licencia: {e}")

    print("\n" + "=" * 65)
    print("       INSTALACION DE BIMO PRO COMPLETADA AL 100%")
    print("=" * 65)
    print(f"\nPuedes abrir la aplicacion desde el icono 'BIMO Pro' en tu Escritorio.")
    
    resp = input("\n¿Deseas iniciar BIMO Pro ahora mismo? (S/N): ").strip().upper()
    if resp == "S":
        print("Iniciando BIMO Pro...")
        subprocess.Popen([exe_path], cwd=destino_dir)

if __name__ == '__main__':
    main()
