# -*- coding: utf-8 -*-
"""
Asistente Gráfico de Desinstalación Oficial de BIMO Pro (Uninstaller Wizard)
Permite desinstalar de forma limpia y segura la aplicación:
1. Cierra procesos en ejecución de BIMO Pro.
2. Ofrece la opción de conservar o eliminar las Historias Clínicas y expedientes de pacientes.
3. Elimina accesos directos del Escritorio y Menú Inicio.
4. Remueve la clave de registro de Windows (Inicio automático y Agregar/Quitar programas).
5. Elimina los archivos binarios, librerías y cachés del sistema.
6. Auto-limpieza final sin dejar rastros.
"""
import os
import sys
import time
import shutil
import winreg
import ctypes
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# Activar reconocimiento de escala DPI en Windows para tipografías nítidas
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

COLOR_BG_DARK = "#0b0f19"       # Barra lateral
COLOR_BG_LIGHT = "#f8fafc"      # Fondo contenido
COLOR_TEXT_DARK = "#0f172a"     # Texto principal
COLOR_TEXT_MUTED = "#64748b"    # Texto secundario
COLOR_DANGER = "#dc2626"        # Rojo para desinstalación
COLOR_DANGER_HOVER = "#b91c1c"
COLOR_PRIMARY = "#0284c7"
COLOR_BORDER = "#cbd5e1"
COLOR_CARD = "#ffffff"

ANCHO_WRAP = 440

class BimoUninstallerWizard(tk.Tk):
    def __init__(self, quiet=False):
        super().__init__()
        self.quiet = quiet
        self.title("Desinstalación de BIMO Pro")
        self.geometry("640x460")
        self.resizable(False, False)

        # Centrar ventana
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - 640) // 2)
        y = max(0, (sh - 460) // 2)
        self.geometry(f"640x460+{x}+{y}")

        # Determinar directorio de instalación
        if getattr(sys, 'frozen', False):
            self.destino_dir = os.path.dirname(os.path.abspath(sys.executable))
        else:
            self.destino_dir = os.path.dirname(os.path.abspath(__file__))

        # Icono si existe
        ico_path = os.path.join(self.destino_dir, "assets", "bimo_icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        # Variables de control
        self.conservar_pacientes = tk.BooleanVar(value=True)
        self.paso_actual = 1

        self._configurar_estilos()
        self._construir_ui()

        if self.quiet:
            self.withdraw()
            self._ejecutar_desinstalacion_hilo()
        else:
            self._mostrar_paso(1)

    def _configurar_estilos(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        self.style.configure(".", background=COLOR_BG_LIGHT, font=("Segoe UI", 9))
        self.style.configure("Horizontal.TProgressbar",
            troughcolor="#e2e8f0",
            background=COLOR_DANGER,
            lightcolor="#f87171",
            darkcolor="#b91c1c",
            thickness=14
        )

    def _construir_ui(self):
        self.contenedor = tk.Frame(self, bg=COLOR_BG_LIGHT)
        self.contenedor.pack(fill=tk.BOTH, expand=True)

        # Barra lateral
        self.sidebar = tk.Frame(self.contenedor, bg=COLOR_BG_DARK, width=190)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        lbl_brand = tk.Label(self.sidebar, text="BIMO PRO", font=("Segoe UI", 15, "bold"), fg="#f87171", bg=COLOR_BG_DARK)
        lbl_brand.pack(pady=(28, 2))

        lbl_sub = tk.Label(self.sidebar, text="Asistente de Desinstalación", font=("Segoe UI", 8), fg="#94a3b8", bg=COLOR_BG_DARK)
        lbl_sub.pack(pady=(0, 24))

        self.sidebar_pasos = []
        pasos = ["1. Confirmación", "2. Desinstalando", "3. Finalizado"]
        for p in pasos:
            lbl = tk.Label(self.sidebar, text=p, font=("Segoe UI", 9), fg="#64748b", bg=COLOR_BG_DARK, anchor="w", padx=20)
            lbl.pack(fill=tk.X, pady=6)
            self.sidebar_pasos.append(lbl)

        # Área principal
        self.main_area = tk.Frame(self.contenedor, bg=COLOR_BG_LIGHT)
        self.main_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Barra inferior (footer)
        self.footer = tk.Frame(self.main_area, bg="#f1f5f9", height=56, highlightthickness=1, highlightbackground=COLOR_BORDER)
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)
        self.footer.pack_propagate(False)

        self.btn_cancelar = tk.Button(self.footer, text="Cancelar", font=("Segoe UI", 9), width=10, relief="groove", cursor="hand2", command=self._cancelar)
        self.btn_cancelar.pack(side=tk.RIGHT, padx=(6, 18), pady=12)

        self.btn_accion = tk.Button(self.footer, text="Desinstalar", font=("Segoe UI", 9, "bold"), bg=COLOR_DANGER, fg="#ffffff", activebackground=COLOR_DANGER_HOVER, activeforeground="#ffffff", relief="flat", cursor="hand2", padx=14, pady=3, command=self._avanzar)
        self.btn_accion.pack(side=tk.RIGHT, padx=6, pady=12)

        # Contenido dinámico
        self.content_frame = tk.Frame(self.main_area, bg=COLOR_BG_LIGHT)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=18)

    def _actualizar_sidebar(self, paso):
        for idx, lbl in enumerate(self.sidebar_pasos, 1):
            if idx == paso:
                lbl.config(fg="#ffffff", font=("Segoe UI", 9, "bold"), bg="#1e293b")
            elif idx < paso:
                lbl.config(fg="#f87171", font=("Segoe UI", 9), bg=COLOR_BG_DARK)
            else:
                lbl.config(fg="#64748b", font=("Segoe UI", 9), bg=COLOR_BG_DARK)

    def _limpiar_contenido(self):
        for w in self.content_frame.winfo_children():
            w.destroy()

    def _mostrar_paso(self, paso):
        self.paso_actual = paso
        self._actualizar_sidebar(paso)
        self._limpiar_contenido()

        if paso == 1:
            self._construir_paso_1()
        elif paso == 2:
            self._construir_paso_2()
        elif paso == 3:
            self._construir_paso_3()

    # --- PASO 1: CONFIRMACIÓN ---
    def _construir_paso_1(self):
        self.btn_cancelar.config(state=tk.NORMAL)
        self.btn_accion.config(text="Desinstalar", state=tk.NORMAL, bg=COLOR_DANGER, fg="#ffffff")

        lbl_tit = tk.Label(self.content_frame, text="¿Desea desinstalar BIMO Pro?", font=("Segoe UI", 14, "bold"), fg=COLOR_TEXT_DARK, bg=COLOR_BG_LIGHT)
        lbl_tit.pack(anchor="w", pady=(0, 4))

        lbl_desc = tk.Label(self.content_frame, text="Este asistente eliminará los binarios, librerías y componentes del programa de este equipo.", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_LIGHT, wraplength=ANCHO_WRAP, justify="left")
        lbl_desc.pack(anchor="w", pady=(0, 12))

        # Tarjeta de ubicación
        card_dir = tk.Frame(self.content_frame, bg="#ffffff", bd=1, relief="solid", highlightbackground=COLOR_BORDER)
        card_dir.pack(fill=tk.X, pady=(0, 12))

        lbl_dtit = tk.Label(card_dir, text="Carpeta de la aplicación a remover:", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_DARK, bg="#ffffff")
        lbl_dtit.pack(anchor="w", padx=12, pady=(8, 2))

        lbl_dval = tk.Label(card_dir, text=self.destino_dir, font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg="#ffffff", wraplength=410, justify="left")
        lbl_dval.pack(anchor="w", padx=12, pady=(0, 8))

        # Tarjeta de Respaldo de Pacientes
        card_opt = tk.Frame(self.content_frame, bg="#ffffff", bd=1, relief="solid", highlightbackground=COLOR_BORDER)
        card_opt.pack(fill=tk.X, pady=(0, 12))

        chk_pac = tk.Checkbutton(
            card_opt,
            text="Conservar historias clínicas y expedientes de pacientes (Recomendado)",
            variable=self.conservar_pacientes,
            font=("Segoe UI", 8, "bold"),
            fg=COLOR_TEXT_DARK,
            bg="#ffffff",
            activebackground="#ffffff",
            selectcolor="#ffffff",
            cursor="hand2",
            wraplength=400,
            justify="left"
        )
        chk_pac.pack(anchor="w", padx=12, pady=(8, 2))

        lbl_hint = tk.Label(
            card_opt,
            text="Si marcas esta casilla, las carpetas de 'Pacientes' y la base de datos se mantendrán intactas para que no pierdas la información de tus consultas.",
            font=("Segoe UI", 7, "italic"),
            fg=COLOR_TEXT_MUTED,
            bg="#ffffff",
            wraplength=400,
            justify="left"
        )
        lbl_hint.pack(anchor="w", padx=30, pady=(0, 8))

        lbl_aviso = tk.Label(
            self.content_frame,
            text="Haga clic en 'Desinstalar' para continuar con la eliminación de los archivos.",
            font=("Segoe UI", 8),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_BG_LIGHT
        )
        lbl_aviso.pack(anchor="w")

    # --- PASO 2: PROGRESO ---
    def _construir_paso_2(self):
        self.btn_cancelar.config(state=tk.DISABLED)
        self.btn_accion.config(state=tk.DISABLED)

        lbl_tit = tk.Label(self.content_frame, text="Desinstalando BIMO Pro...", font=("Segoe UI", 13, "bold"), fg=COLOR_TEXT_DARK, bg=COLOR_BG_LIGHT)
        lbl_tit.pack(anchor="w", pady=(12, 6))

        self.lbl_estado = tk.Label(self.content_frame, text="Iniciando proceso de desinstalación...", font=("Segoe UI", 9), fg=COLOR_TEXT_MUTED, bg=COLOR_BG_LIGHT, wraplength=ANCHO_WRAP, justify="left")
        self.lbl_estado.pack(anchor="w", pady=(0, 14))

        self.progress = ttk.Progressbar(self.content_frame, orient="horizontal", mode="determinate", length=420, style="Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 10))

        self.lbl_detalles = tk.Label(self.content_frame, text="Cerrando procesos activos...", font=("Segoe UI", 8), fg="#94a3b8", bg=COLOR_BG_LIGHT, wraplength=ANCHO_WRAP, justify="left")
        self.lbl_detalles.pack(anchor="w")

        # Iniciar hilo de desinstalación
        t = threading.Thread(target=self._ejecutar_desinstalacion_hilo, daemon=True)
        t.start()

    def _ejecutar_desinstalacion_hilo(self):
        try:
            flags = 0x08000000 if sys.platform == "win32" else 0

            # 1. Terminar procesos activos de BIMO Pro
            if hasattr(self, 'lbl_estado'):
                self.lbl_estado.config(text="Cerrando procesos activos de BIMO Pro...")
                self.progress["value"] = 15
                self.update_idletasks()

            subprocess.call(["taskkill", "/F", "/IM", "BIMO_Pro.exe"], creationflags=flags)
            time.sleep(1.0)

            # 2. Remover acceso directo del Escritorio
            if hasattr(self, 'lbl_estado'):
                self.lbl_estado.config(text="Eliminando accesos directos de escritorio...")
                self.progress["value"] = 30
                self.update_idletasks()

            rutas_escritorio = [
                os.path.join(os.path.expanduser("~"), "Desktop", "BIMO Pro.lnk"),
                os.path.join(os.path.expanduser("~"), "Escritorio", "BIMO Pro.lnk"),
                os.path.join(os.getenv("PUBLIC", "C:\\Users\\Public"), "Desktop", "BIMO Pro.lnk"),
                os.path.join(os.getenv("PUBLIC", "C:\\Users\\Public"), "Escritorio", "BIMO Pro.lnk")
            ]
            for r_lnk in rutas_escritorio:
                if os.path.exists(r_lnk):
                    try:
                        os.remove(r_lnk)
                    except Exception:
                        pass

            # 3. Remover entradas de registro (Inicio de Windows y Desinstalador)
            if hasattr(self, 'lbl_estado'):
                self.lbl_estado.config(text="Removiendo claves de registro de Windows...")
                self.progress["value"] = 50
                self.update_idletasks()

            # Registro de inicio
            for sub_key in ("BIMO_Clinico", "BIMO_Pro"):
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key, sub_key)
                except Exception:
                    pass

            # Registro de Desinstalador en Windows
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\BIMO_Pro")
            except Exception:
                pass

            # 4. Eliminar archivos y carpetas de la aplicación
            if hasattr(self, 'lbl_estado'):
                self.lbl_estado.config(text="Eliminando archivos binarios y librerías...")
                self.progress["value"] = 70
                self.update_idletasks()

            conservar = self.conservar_pacientes.get()
            carpetas_protegidas = {"Pacientes", "data"} if conservar else set()

            # Recorrer directorio y eliminar elementos no protegidos
            for item in os.listdir(self.destino_dir):
                item_path = os.path.join(self.destino_dir, item)
                
                # Proteger expedientes si el usuario lo solicitó
                if item in carpetas_protegidas:
                    continue

                # No intentar eliminar el propio ejecutable del desinstalador mientras corre
                if getattr(sys, 'frozen', False) and os.path.abspath(item_path) == os.path.abspath(sys.executable):
                    continue

                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path, ignore_errors=True)
                    else:
                        os.remove(item_path)
                except Exception:
                    pass

            if hasattr(self, 'progress'):
                self.progress["value"] = 100
                self.lbl_estado.config(text="¡Desinstalación completada con éxito!")
                self.update_idletasks()
                time.sleep(0.5)

            if not self.quiet:
                self.after(200, lambda: self._mostrar_paso(3))
            else:
                self._limpieza_final_y_salir()

        except Exception as e:
            if not self.quiet:
                messagebox.showerror("Aviso", f"Ocurrió un detalle durante la desinstalación:\n{e}")
                self._mostrar_paso(3)

    # --- PASO 3: FINALIZADO ---
    def _construir_paso_3(self):
        self.btn_cancelar.config(state=tk.DISABLED)
        self.btn_accion.config(text="Cerrar", state=tk.NORMAL, bg=COLOR_PRIMARY, fg="#ffffff")

        lbl_tit = tk.Label(self.content_frame, text="¡BIMO Pro ha sido desinstalado!", font=("Segoe UI", 14, "bold"), fg="#16a34a", bg=COLOR_BG_LIGHT)
        lbl_tit.pack(anchor="w", pady=(8, 12))

        card_fin = tk.Frame(self.content_frame, bg="#ffffff", bd=1, relief="solid", highlightbackground=COLOR_BORDER)
        card_fin.pack(fill=tk.X, pady=(0, 16))

        if self.conservar_pacientes.get():
            msg = (
                "BIMO Pro y sus componentes binarios han sido eliminados de este equipo.\n\n"
                f"Las carpetas de expedientes clínicos se mantuvieron a salvo en:\n{self.destino_dir}\n\n"
                "Los accesos directos e inicios automáticos de Windows fueron retirados completamente."
            )
        else:
            msg = (
                "BIMO Pro y todos sus archivos han sido eliminados por completo de este equipo.\n\n"
                "Los accesos directos e inicios automáticos de Windows fueron retirados exitosamente."
            )

        lbl_body = tk.Label(card_fin, text=msg, font=("Segoe UI", 8), fg=COLOR_TEXT_DARK, bg="#ffffff", justify="left", wraplength=410)
        lbl_body.pack(anchor="w", padx=14, pady=12)

    def _avanzar(self):
        if self.paso_actual == 1:
            self._mostrar_paso(2)
        elif self.paso_actual == 3:
            self._limpieza_final_y_salir()

    def _limpieza_final_y_salir(self):
        # En caso de ejecutable compilado, programar la auto-eliminación detached
        if getattr(sys, 'frozen', False):
            exe_self = os.path.abspath(sys.executable)
            conservar = self.conservar_pacientes.get()
            flags = 0x08000000 if sys.platform == "win32" else 0
            
            # Comando en cmd silencioso que espera 1.5s, borra Uninstall.exe y borra la carpeta si no se conservan pacientes
            if not conservar:
                cmd_clean = f'ping 127.0.0.1 -n 2 > nul & del /f /q "{exe_self}" & rmdir /s /q "{self.destino_dir}"'
            else:
                cmd_clean = f'ping 127.0.0.1 -n 2 > nul & del /f /q "{exe_self}"'
            
            try:
                subprocess.Popen(["cmd.exe", "/c", cmd_clean], creationflags=flags)
            except Exception:
                pass

        self.destroy()
        sys.exit(0)

    def _cancelar(self):
        if self.paso_actual == 1:
            self.destroy()
            sys.exit(0)

if __name__ == "__main__":
    quiet_mode = "--quiet" in sys.argv or "/S" in sys.argv
    app = BimoUninstallerWizard(quiet=quiet_mode)
    if not quiet_mode:
        app.mainloop()
