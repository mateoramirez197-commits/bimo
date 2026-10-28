import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"

# Con pythonw (acceso directo sin consola) no hay stdout/stderr: guardar la salida en
# bimo_inicio.log para diagnosticar arranques fallidos (se conserva el anterior en .1).
if sys.stdout is None or sys.stderr is None:
    try:
        _base_log = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
        _ruta_log = os.path.join(_base_log, "bimo_inicio.log")
        if os.path.exists(_ruta_log):
            os.replace(_ruta_log, _ruta_log + ".1")
        _archivo_log = open(_ruta_log, "w", encoding="utf-8", errors="replace", buffering=1)
        sys.stdout = sys.stdout or _archivo_log
        sys.stderr = sys.stderr or _archivo_log
        import faulthandler
        faulthandler.enable(_archivo_log)
    except Exception:
        pass

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

def resetear_acceso_local_gui(non_interactive_pwd=None, non_interactive_pin=None):
    """
    Modo local de recuperación de acceso (--reset-acceso, L-F):
    Ventana GUI tkinter autónoma (sin consola) para restablecer la contraseña
    y/o PIN del médico con acceso físico a la máquina.
    """
    from auth import hash_password
    from config import cargar_datos_clinica, guardar_datos_clinica
    from database import get_connection, init_db

    init_db()

    # Modo no interactivo para pruebas automatizadas
    if non_interactive_pwd is not None or non_interactive_pin is not None:
        try:
            if non_interactive_pwd:
                pwd_hash = hash_password(non_interactive_pwd)
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM usuarios WHERE rol = 'medico' AND activo = 1 ORDER BY id ASC LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        cursor.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (pwd_hash, row["id"]))
                    else:
                        cursor.execute("""
                            INSERT INTO usuarios (nombre, email, password_hash, rol, activo)
                            VALUES ('Médico BIMO', 'doctor@bimo.local', ?, 'medico', 1)
                        """, (pwd_hash,))
                    conn.commit()
            if non_interactive_pin:
                conf = cargar_datos_clinica()
                conf["pin_rapido"] = str(non_interactive_pin).strip()
                guardar_datos_clinica(conf)
            print("[RESET ACCESO OK] Credenciales restablecidas en modo de prueba.")
            return True
        except Exception as e:
            print(f"[RESET ACCESO ERROR]: {e}")
            return False

    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.title("BIMO Pro - Recuperación de Acceso Local")
    root.geometry("460x420")
    root.resizable(False, False)
    root.configure(bg="#0B0F19")

    # Centrar ventana
    root.update_idletasks()
    w = 460
    h = 420
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    title_font = ("Helvetica", 14, "bold")
    sub_font = ("Helvetica", 9)
    label_font = ("Helvetica", 10, "bold")
    entry_font = ("Helvetica", 11)

    tk.Label(root, text="BIMO Pro - Recuperar Acceso", font=title_font, fg="#00F5D4", bg="#0B0F19").pack(pady=(20, 4))
    tk.Label(
        root,
        text="Requiere acceso físico local. Establezca las nuevas credenciales\npara el usuario médico principal de esta computadora.",
        font=sub_font, fg="#94A3B8", bg="#0B0F19", justify="center"
    ).pack(pady=(0, 15))

    frame = tk.Frame(root, bg="#0B0F19", padx=25)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="Nueva Contraseña (mínimo 6 caracteres):", font=label_font, fg="#E2E8F0", bg="#0B0F19", anchor="w").pack(fill="x", pady=(5, 2))
    entry_pwd = tk.Entry(frame, font=entry_font, show="*", bg="#161F30", fg="#FFFFFF", insertbackground="#00F5D4", relief="flat")
    entry_pwd.pack(fill="x", ipady=4, pady=(0, 10))

    tk.Label(frame, text="Confirmar Contraseña:", font=label_font, fg="#E2E8F0", bg="#0B0F19", anchor="w").pack(fill="x", pady=(5, 2))
    entry_pwd_conf = tk.Entry(frame, font=entry_font, show="*", bg="#161F30", fg="#FFFFFF", insertbackground="#00F5D4", relief="flat")
    entry_pwd_conf.pack(fill="x", ipady=4, pady=(0, 10))

    tk.Label(frame, text="Nuevo PIN Rápido (4 a 6 dígitos, opcional):", font=label_font, fg="#E2E8F0", bg="#0B0F19", anchor="w").pack(fill="x", pady=(5, 2))
    entry_pin = tk.Entry(frame, font=entry_font, bg="#161F30", fg="#FFFFFF", insertbackground="#00F5D4", relief="flat")
    entry_pin.pack(fill="x", ipady=4, pady=(0, 15))

    def on_guardar():
        pwd = entry_pwd.get().strip()
        pwd_c = entry_pwd_conf.get().strip()
        pin = entry_pin.get().strip()

        if not pwd and not pin:
            messagebox.showwarning("Atención", "Debe ingresar una nueva contraseña o un nuevo PIN.", parent=root)
            return

        if pwd:
            if len(pwd) < 6:
                messagebox.showerror("Error", "La contraseña debe tener al menos 6 caracteres.", parent=root)
                return
            if pwd != pwd_c:
                messagebox.showerror("Error", "Las contraseñas ingresadas no coinciden.", parent=root)
                return

        if pin:
            if not pin.isdigit() or not (4 <= len(pin) <= 6):
                messagebox.showerror("Error", "El PIN debe tener entre 4 y 6 dígitos numéricos.", parent=root)
                return

        try:
            if pwd:
                pwd_hash = hash_password(pwd)
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM usuarios WHERE rol = 'medico' AND activo = 1 ORDER BY id ASC LIMIT 1")
                    row = cursor.fetchone()
                    if row:
                        cursor.execute("UPDATE usuarios SET password_hash = ? WHERE id = ?", (pwd_hash, row["id"]))
                    else:
                        cursor.execute("""
                            INSERT INTO usuarios (nombre, email, password_hash, rol, activo)
                            VALUES ('Médico BIMO', 'doctor@bimo.local', ?, 'medico', 1)
                        """, (pwd_hash,))
                    conn.commit()

            if pin:
                conf = cargar_datos_clinica()
                conf["pin_rapido"] = pin
                guardar_datos_clinica(conf)

            messagebox.showinfo(
                "Acceso Restablecido",
                "¡Credenciales actualizadas exitosamente!\n\nAhora puede iniciar sesión en BIMO Pro con su nueva clave y PIN.",
                parent=root
            )
            root.destroy()
            sys.exit(0)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo restablecer el acceso: {e}", parent=root)

    btn_frame = tk.Frame(frame, bg="#0B0F19")
    btn_frame.pack(fill="x", pady=10)

    btn_cancel = tk.Button(
        btn_frame, text="Cancelar", bg="#334155", fg="#FFFFFF", relief="flat", font=label_font,
        cursor="hand2", padx=15, pady=6, command=root.destroy
    )
    btn_cancel.pack(side="left", padx=(0, 10))

    btn_save = tk.Button(
        btn_frame, text="Restablecer Acceso", bg="#00F5D4", fg="#0B0F19", relief="flat", font=label_font,
        cursor="hand2", padx=15, pady=6, command=on_guardar
    )
    btn_save.pack(side="right")

    root.mainloop()

def main():
    print("=" * 60)
    print("[BIMO] Asistente Clinico Inteligente (SaaS Odontologico)")
    import datetime as _dt
    print(f"[BIMO] Inicio: {_dt.datetime.now().isoformat(timespec='seconds')} | PID {os.getpid()} | {sys.executable}")
    print("=" * 60)

    # Soporte para ejecución del widget flotante anclado (--widget)
    if "--widget" in sys.argv or "widget_runner.py" in sys.argv:
        from widget_runner import main as widget_main
        widget_main()
        sys.exit(0)

    # Soporte para recuperación de acceso local (--reset-acceso) (L-F)
    if "--reset-acceso" in sys.argv or "--recuperar-acceso" in sys.argv:
        test_pwd = None
        test_pin = None
        if "--test-reset-pwd" in sys.argv:
            idx = sys.argv.index("--test-reset-pwd")
            if idx + 1 < len(sys.argv):
                test_pwd = sys.argv[idx + 1]
        if "--test-reset-pin" in sys.argv:
            idx = sys.argv.index("--test-reset-pin")
            if idx + 1 < len(sys.argv):
                test_pin = sys.argv[idx + 1]
        ok = resetear_acceso_local_gui(non_interactive_pwd=test_pwd, non_interactive_pin=test_pin)
        sys.exit(0 if ok is not False else 1)

    # Soporte para inicialización desde instalador (--setup-init) (L-D / L-E)
    if "--setup-init" in sys.argv:
        from config import DATA_DIR, inicializar_boveda_si_no_existe, guardar_datos_clinica, cargar_datos_clinica
        log_path = os.path.join(str(DATA_DIR), "bimo_install.log")
        try:
            with open(log_path, "a", encoding="utf-8") as lf:
                import datetime
                lf.write(f"[{datetime.datetime.now().isoformat()}] Inicio de configuracion --setup-init\n")

            init_db()
            from license_manager import activar_licencia_equipo
            activar_licencia_equipo("doctor@bimo.local")
            inicializar_boveda_si_no_existe()

            # Procesar credenciales del doctor si se pasó --doctor-file (L-E)
            if "--doctor-file" in sys.argv:
                idx = sys.argv.index("--doctor-file")
                if idx + 1 < len(sys.argv):
                    doc_path = sys.argv[idx + 1]
                    if os.path.exists(doc_path):
                        try:
                            import json
                            with open(doc_path, "r", encoding="utf-8") as df:
                                d_info = json.load(df)

                            d_nom = str(d_info.get("nombre", "")).strip() or "Dr. Odontólogo"
                            d_mail = str(d_info.get("email", "")).strip().lower() or "doctor@bimo.local"
                            d_pwd = str(d_info.get("password", "")).strip()
                            d_pin = str(d_info.get("pin", "")).strip()

                            d_api_key = str(d_info.get("api_key", "")).strip()
                            if d_pwd:
                                from auth import registrar_usuario
                                registrar_usuario(d_nom, d_mail, d_pwd, rol="medico")
                            if d_pin:
                                c_info = cargar_datos_clinica()
                                c_info["pin_rapido"] = d_pin
                                c_info["nombre_doctor"] = d_nom
                                c_info["correo_doctor"] = d_mail
                                c_info["onboarding_completado"] = True
                                guardar_datos_clinica(c_info)
                            if d_api_key:
                                from config import guardar_parametro_boveda
                                guardar_parametro_boveda("groq_api_key", d_api_key)
                        finally:
                            try:
                                with open(doc_path, "wb") as df:
                                    df.write(os.urandom(1024))
                                os.remove(doc_path)
                            except Exception:
                                pass

            # Procesar archivo de secretos si se pasó --secrets-file
            if "--secrets-file" in sys.argv:
                idx = sys.argv.index("--secrets-file")
                if idx + 1 < len(sys.argv):
                    sec_file = sys.argv[idx + 1]
                    if os.path.exists(sec_file):
                        try:
                            from config import guardar_parametro_boveda
                            with open(sec_file, "r", encoding="utf-8", errors="replace") as sf:
                                for sline in sf:
                                    sline = sline.strip()
                                    if sline and not sline.startswith("#") and "=" in sline:
                                        sk, sv = sline.split("=", 1)
                                        sk = sk.strip()
                                        sv = sv.strip().strip('"').strip("'")
                                        if sk:
                                            guardar_parametro_boveda(sk.lower(), sv)
                        except Exception as e_sec:
                            print(f"[WARN SECRETS FILE]: {e_sec}")

            with open(log_path, "a", encoding="utf-8") as lf:
                lf.write(f"[{datetime.datetime.now().isoformat()}] Setup-init completado con exito (codigo 0)\n")
            print("[SETUP INIT] Equipo autorizado con éxito, bóveda y base de datos inicializadas.")
            sys.exit(0)
        except Exception as e:
            try:
                with open(log_path, "a", encoding="utf-8") as lf:
                    lf.write(f"[{datetime.datetime.now().isoformat()}] Error en setup-init: {e}\n")
            except Exception:
                pass
            print(f"[SETUP INIT ERROR]: {e}")
            sys.exit(1)

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
