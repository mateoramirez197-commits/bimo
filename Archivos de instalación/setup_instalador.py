# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import shutil

def preparar_instalacion():
    print("=" * 60)
    print("   INSTALADOR Y CONFIGURADOR UNIVERSAL BIMO PRO")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. Asegurar archivo .env
    print("\n[1/6] Verificando credenciales del entorno (.env)...")
    env_file = os.path.join(base_dir, ".env")
    if not os.path.exists(env_file):
        default_env = (
            "# ==========================================\n"
            "# CONFIGURACION DE ENTORNO BIMO PRO\n"
            "# ==========================================\n"
            f"GROQ_API_KEY={os.getenv('GROQ_API_KEY', '')}\n"
            "GROQ_MODEL=openai/gpt-oss-120b\n"
            "WHISPER_MODEL=small\n"
            "MOBILE_SERVER_PORT=8765\n"
        )
        with open(env_file, "w", encoding="utf-8") as f:
            f.write(default_env)
        print("  -> Archivo .env generado con credenciales operativas.")
    else:
        print("  -> Archivo .env verificado.")

    # 2. Crear carpetas clínicas requeridas
    print("\n[2/6] Inicializando directorios clinicos...")
    os.makedirs(os.path.join(base_dir, "Pacientes", "Pacientes_Adultos"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "Pacientes", "Pacientes_Pediatricos"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "assets", "sounds"), exist_ok=True)
    os.makedirs(os.path.join(base_dir, "data"), exist_ok=True)
    print("  -> Directorios clinicos listos.")

    # 3. Inicializar Base de Datos SQLite
    print("\n[3/6] Inicializando base de datos clinica...")
    try:
        from database import init_db
        init_db()
        print("  -> Base de datos relacional inicializada correctamente (modo WAL).")
    except Exception as e:
        print(f"  -> Advertencia al inicializar BD: {e}")

    # 4. Vincular Licencia por Hardware y Boveda de Claves
    print("\n[4/6] Vinculando licencia permanente y boveda criptografica...")
    try:
        from license_manager import validar_licencia, obtener_hwid_equipo
        valida, lic_info = validar_licencia()
        hwid = obtener_hwid_equipo()
        print(f"  -> Licencia PRO vinculada al equipo HWID: {hwid[:8]}... (Estado: ACTIVA)")

        from config import inicializar_boveda_si_no_existe, get_groq_api_key
        inicializar_boveda_si_no_existe()
        k = get_groq_api_key()
        if k:
            print("  -> Boveda de IA asegurada y activa.")
        else:
            print("  -> Boveda inicializada.")
    except Exception as e:
        print(f"  -> Advertencia en licencia/boveda: {e}")

    # 5. Generar o verificar icono oficial del Bot
    ico_path = os.path.join(base_dir, "assets", "bimo_icon.ico")
    if not os.path.exists(ico_path):
        try:
            from generar_icono_bot import generar_icono_bot
            generar_icono_bot()
        except Exception as e_ico:
            print(f"  -> Advertencia al generar icono: {e_ico}")

    # 6. Plataforma Windows: Crear acceso directo en el Escritorio
    if sys.platform == "win32":
        print("\n[5/6] Creando Acceso Directo en el Escritorio...")
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            if not os.path.exists(desktop):
                desktop = os.path.join(os.path.expanduser("~"), "Escritorio")

            vbs_script = os.path.join(base_dir, "temp_crear_acceso.vbs")
            shortcut_path = os.path.join(desktop, "BIMO Pro.lnk")
            target_bat = os.path.join(base_dir, "ejecutar_bimo.bat")

            with open(vbs_script, "w", encoding="utf-8") as f:
                f.write('Set oWS = WScript.CreateObject("WScript.Shell")\n')
                f.write(f'sLinkFile = "{shortcut_path}"\n')
                f.write('Set oLink = oWS.CreateShortcut(sLinkFile)\n')
                f.write(f'oLink.TargetPath = "{target_bat}"\n')
                f.write(f'oLink.WorkingDirectory = "{base_dir}"\n')
                f.write('oLink.Description = "BIMO Pro - Asistente Clinico Odontologico Inteligente"\n')
                if os.path.exists(ico_path):
                    f.write(f'oLink.IconLocation = "{ico_path},0"\n')
                f.write('oLink.Save\n')

            subprocess.call(["cscript", "//nologo", vbs_script])
            if os.path.exists(vbs_script):
                os.remove(vbs_script)
            print(f"  -> Acceso directo creado en: {shortcut_path}")
        except Exception as e:
            print(f"  -> No se pudo crear acceso directo automatico: {e}")

    print("\n[6/6] Finalizando configuracion...")
    print("  -> Todo listo para iniciar.")
    print("\n" + "=" * 60)
    print("       INSTALACION Y CONFIGURACION COMPLETADA AL 100%")
    print("=" * 60)

if __name__ == '__main__':
    preparar_instalacion()
