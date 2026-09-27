import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import threading
from database import init_db, purgar_datos_prueba
from startup_manager import esta_registrado_en_inicio, registrar_en_inicio_windows

def _tareas_fondo_inicio():
    """Ejecuta sincronización de calendario y verificación de updates en segundo plano sin demorar la GUI."""
    try:
        from calendar_sync import init_google_calendar
        init_google_calendar()
    except Exception as e_cal:
        print(f"[CALENDAR INIT BG WARN]: {e_cal}")
    try:
        from updater import iniciar_verificacion_actualizacion
        iniciar_verificacion_actualizacion()
        if not esta_registrado_en_inicio():
            registrar_en_inicio_windows()
    except Exception as e_up:
        print(f"[UPDATER BG WARN]: {e_up}")

def main():
    print("=" * 60)
    print("[BIMO] Asistente Clinico Inteligente (SaaS Odontologico)")
    print("=" * 60)

    # Soporte para ejecución del widget flotante anclado (--widget)
    if "--widget" in sys.argv or "widget_runner.py" in sys.argv:
        from widget_runner import main as widget_main
        widget_main()
        sys.exit(0)

    # Soporte para inicialización desde instalador (--setup-init)
    if "--setup-init" in sys.argv:
        from license_manager import activar_licencia_equipo
        from config import inicializar_boveda_si_no_existe
        activar_licencia_equipo("mateoramirez@bimo.local")
        inicializar_boveda_si_no_existe()
        print("[SETUP INIT] Equipo autorizado con éxito, bóveda y base de datos inicializadas.")
        sys.exit(0)

    # Soporte para reinicio de licencia en modo de prueba (--reset-lic o --test)
    if "--reset-lic" in sys.argv or "--test" in sys.argv:
        from license_manager import resetear_licencia
        resetear_licencia()
        print("[TEST MODE] Licencia reiniciada con éxito. Listo para nueva activación.")

    # 1. Inicializar base de datos SQLite relacional (modo WAL)
    init_db()

    # 2. Purgar cualquier dato de prueba previo (Cero Mock Data comercial)
    purgar_datos_prueba()

    # 3. Lanzar sincronización de calendario y updates en segundo plano
    threading.Thread(target=_tareas_fondo_inicio, daemon=True).start()

    # 4. Iniciar la aplicación y la interfaz de usuario
    if "--classic" in sys.argv:
        print("[MODO CLÁSICO] Iniciando CustomTkinter UI...")
        from ui.app import BimoApp
        app = BimoApp()
        app.mainloop()
    else:
        print("[MODO MODERNO] Iniciando BIMO Modern Desktop UI con WebView2...")
        try:
            from desktop_app import iniciar_desktop
            iniciar_desktop()
        except Exception as e:
            try:
                import traceback
                base_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
                with open(os.path.join(base_dir, "bimo_modern_error.log"), "w", encoding="utf-8") as f:
                    traceback.print_exc(file=f)
            except Exception:
                pass
            print(f"[ERROR FATAL AL INICIAR INTERFAZ MODERNA]: {e}")
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror(
                    "Error al Iniciar BIMO Pro",
                    f"Ocurrió un error al cargar la interfaz moderna de BIMO Pro:\n\n{e}\n\nSe ha generado un registro detallado en 'bimo_modern_error.log'."
                )
                root.destroy()
            except Exception:
                pass
            sys.exit(1)

if __name__ == "__main__":
    main()
