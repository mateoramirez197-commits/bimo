import sys
from database import init_db, purgar_datos_prueba
from calendar_sync import init_google_calendar
from startup_manager import esta_registrado_en_inicio, registrar_en_inicio_windows
from ui.app import BimoApp

# Configurar salida UTF-8 en consola
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def main():
    print("=" * 60)
    print("🏥 BIMO - Asistente Clínico Inteligente (SaaS Odontológico)")
    print("=" * 60)

    # Soporte para reinicio de licencia en modo de prueba (--reset-lic o --test)
    if "--reset-lic" in sys.argv or "--test" in sys.argv:
        from license_manager import resetear_licencia
        resetear_licencia()
        print("[TEST MODE] Licencia reiniciada con éxito. Listo para nueva activación.")

    # 1. Inicializar base de datos SQLite relacional (modo WAL)
    init_db()

    # 2. Purgar cualquier dato de prueba previo (Cero Mock Data comercial)
    purgar_datos_prueba()

    # 3. Inicializar sincronización con Google Calendar
    init_google_calendar()

    # 4. Asegurar auto-arranque silencioso y verificación de actualizaciones remotas
    try:
        from updater import iniciar_verificacion_actualizacion
        iniciar_verificacion_actualizacion()
        if not esta_registrado_en_inicio():
            registrar_en_inicio_windows()
    except Exception:
        pass

    # 5. Iniciar la aplicación y la interfaz de usuario
    if "--classic" in sys.argv:
        print("[MODO CLÁSICO] Iniciando CustomTkinter UI...")
        app = BimoApp()
        app.mainloop()
    else:
        print("[MODO MODERNO] Iniciando BIMO Modern Desktop UI con WebView2...")
        try:
            from desktop_app import iniciar_desktop
            iniciar_desktop()
        except Exception as e:
            print(f"[MODERNO FALLÓ]: {e}. Iniciando modo clásico de respaldo...")
            app = BimoApp()
            app.mainloop()

if __name__ == "__main__":
    main()
