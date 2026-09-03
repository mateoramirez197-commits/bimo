# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import shutil

def preparar_instalacion():
    print("=" * 60)
    print("   INSTALADOR Y CONFIGURADOR UNIVERSAL BIMO PRO (PC Y MAC)")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Crear carpetas clínicas requeridas
    print("\n[1/4] Inicializando directorios clinicos...")
    os.makedirs(os.path.join(base_dir, "Pacientes", "Pacientes_Adultos"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "Pacientes", "Pacientes_Pediatricos"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "assets", "sounds"), exist_ok=True)
    print("  -> Directorios clinicos y carpetas de expedientes listos.")

    # 2. Verificar dependencias de Python
    print("\n[2/4] Verificando e instalando librerias de IA y audio...")
    req_file = os.path.join(base_dir, "requirements.txt")
    if os.path.exists(req_file):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
            print("  -> Dependencias de requirements.txt verificadas con exito.")
        except Exception as e:
            print(f"  -> Advertencia al instalar requirements: {e}")

    # 3. Plataforma Windows: Crear acceso directo en el Escritorio
    if sys.platform == "win32":
        print("\n[3/4] Creando Acceso Directo en el Escritorio de Windows...")
        try:
            desktop = os.path.join(os.path.expanduser("~nothing").text if False else os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop):
                desktop = os.path.join(os.path.expanduser("~"), "Escritorio")

            vbs_script = os.path.join(base_dir, "temp_crear_acceso.vbs")
            shortcut_path = os.path.join(desktop, "BIMO Pro.lnk")
            target_bat = os.path.join(base_dir, "ejecutar_bimo.bat")

            with open(target_bat, "w", encoding="utf-8") as f:
                f.write("@echo off\n")
                f.write(f'cd /d "{base_dir}"\n')
                f.write(f'start "" "{sys.executable}" main.py\n')

            with open(vbs_script, "w", encoding="utf-8") as f:
                f.write('Set oWS = WScript.CreateObject("WScript.Shell")\n')
                f.write(f'sLinkFile = "{shortcut_path}"\n')
                f.write('Set oLink = oWS.CreateShortcut(sLinkFile)\n')
                f.write(f'oLink.TargetPath = "{target_bat}"\n')
                f.write(f'oLink.WorkingDirectory = "{base_dir}"\n')
                f.write('oLink.Description = "BIMO Pro - Asistente Odontologico Inteligente"\n')
                f.write('oLink.Save\n')

            subprocess.call(["cscript", "//nologo", vbs_script])
            if os.path.exists(vbs_script):
                os.remove(vbs_script)
            print(f"  -> Acceso directo creado exitosamente en: {shortcut_path}")
        except Exception as e:
            print(f"  -> No se pudo crear acceso directo automatico: {e}")

    # 4. Plataforma macOS: Crear lanzador .command ejecutable
    print("\n[4/4] Configurando lanzador multiplataforma para macOS...")
    mac_script = os.path.join(base_dir, "BIMO_Pro_Mac.command")
    with open(mac_script, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write("# Lanzador nativo de BIMO Pro para macOS\n")
        f.write("cd \"$(dirname \"$0\")\"\n")
        f.write("python3 main.py\n")
    try:
        os.chmod(mac_script, 0o755)
        print("  -> Lanzador BIMO_Pro_Mac.command configurado con permisos de ejecucion.")
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("       INSTALACIO Y CONFIGURACIO COMPLETADA AL 100%")
    print("=" * 60)

if __name__ == '__main__':
    preparar_instalacion()
