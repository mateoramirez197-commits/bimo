# -*- coding: utf-8 -*-
"""
Asistente Gráfico de Instalación Oficial de BIMO Pro (Setup Wizard)
Interfaz gráfica paso a paso estilo Windows ("Siguiente, Siguiente, Siguiente"):
1. Bienvenida institucional y resumen funcional
2. Acuerdos y Compromisos de Usuario Clínico (Aceptación obligatoria aquí)
3. Selección de Directorio de Instalación y Accesos Directos
4. Progreso de instalación en tiempo real
5. Finalización con opción de inicio inmediato
"""
import os
import sys
import time
import json
import zipfile
import threading
import subprocess
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

# Activar reconocimiento de escala DPI en Windows para tipografías vectoriales nítidas
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

COLOR_BG_DARK = "#0b0f19"       # Barra lateral
COLOR_BG_LIGHT = "#f8fafc"      # Área de contenido
COLOR_TEXT_DARK = "#0f172a"     # Texto principal
COLOR_TEXT_MUTED = "#64748b"    # Texto secundario
COLOR_PRIMARY = "#0284c7"       # Azul / Cian
COLOR_ACCENT = "#00f5d4"        # Neón cian
COLOR_BORDER = "#cbd5e1"        # Bordes suaves
COLOR_CARD = "#ffffff"          # Tarjetas blancas

ANCHO_WRAP = 480               # Ancho de ajuste de texto consistente en todas las vistas

def obtener_ruta_instalacion_default():
    local_app_data = os.getenv("LOCALAPPDATA", os.path.expanduser("~"))
    return os.path.join(local_app_data, "Programs", "BIMO_Pro")

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
            f.write('oLink.Description = "BIMO Pro - Copiloto Odontologico y Clinico Inteligente"\n')
            if os.path.exists(ico_path):
                f.write(f'oLink.IconLocation = "{ico_path},0"\n')
            f.write('oLink.Save\n')
        
        flags = 0x08000000 if sys.platform == "win32" else 0
        subprocess.call(["wscript", "//nologo", vbs_script], creationflags=flags)
        if os.path.exists(vbs_script):
            os.remove(vbs_script)
        return True
    except Exception as e:
        print(f"[SHORTCUT WARN] {e}")
        return False

def registrar_desinstalador_windows(destino_dir, exe_path, ico_path):
    """Registra BIMO Pro oficialmente en la sección de Desinstalación de Windows (Configuración > Aplicaciones)."""
    try:
        import winreg
        uninstall_exe = os.path.join(destino_dir, "Uninstall.exe")
        
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\BIMO_Pro"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, "BIMO Pro - Copiloto Clínico Odontológico")
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, "2.0 Pro")
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, "BIMO Dental AI")
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, destino_dir)
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_exe}"')
            winreg.SetValueEx(key, "QuietUninstallString", 0, winreg.REG_SZ, f'"{uninstall_exe}" --quiet')
            if os.path.exists(ico_path):
                winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, ico_path)
            winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, 750000)
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
        return True
    except Exception as e:
        print(f"[REG UNINSTALL WARN] {e}")
        return False

class BimoSetupWizard(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Instalación de BIMO Pro Clínico")
        self.geometry("750x560")
        self.resizable(False, False)

        # Centrar ventana en pantalla de forma precisa
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = max(0, (sw - 750) // 2)
        y = max(0, (sh - 560) // 2)
        self.geometry(f"750x560+{x}+{y}")

        # Configurar icono si existe
        self.base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        ico_path = os.path.join(self.base_dir, "assets", "bimo_icon.ico")
        if not os.path.exists(ico_path):
            ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "bimo_icon.ico")
        if os.path.exists(ico_path):
            try:
                self.iconbitmap(ico_path)
            except Exception:
                pass

        # Variables de estado
        self.paso_actual = 1
        self.acepta_terminos = tk.BooleanVar(value=False)
        self.ruta_destino = tk.StringVar(value=obtener_ruta_instalacion_default())
        self.crear_shortcut = tk.BooleanVar(value=True)
        self.ejecutar_al_finalizar = tk.BooleanVar(value=True)

        # Variables de credenciales del doctor (L-E)
        self.doc_nombre = tk.StringVar(value="Dr. Odontólogo")
        self.doc_email = tk.StringVar(value="doctor@bimo.local")
        self.doc_password = tk.StringVar(value="")
        self.doc_password_conf = tk.StringVar(value="")
        self.doc_pin = tk.StringVar(value="")
        self.groq_api_key = tk.StringVar(value="")

        self.payload_zip = self._localizar_payload()

        # Construir estructura UI
        self._configurar_estilos()
        self._construir_ui()
        self._mostrar_paso(1)

    def _localizar_payload(self):
        # 1. En _MEIPASS (PyInstaller)
        p1 = os.path.join(self.base_dir, "bimo_payload.zip")
        if os.path.exists(p1):
            return p1
        # 2. En carpeta dist (desarrollo)
        p2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "bimo_payload.zip")
        if os.path.exists(p2):
            return p2
        return ""

    def _configurar_estilos(self):
        self.style = ttk.Style(self)
        self.style.theme_use("clam")

        self.style.configure(".", background=COLOR_BG_LIGHT, font=("Segoe UI", 9))
        self.style.configure("Sidebar.TFrame", background=COLOR_BG_DARK)
        self.style.configure("Content.TFrame", background=COLOR_BG_LIGHT)
        self.style.configure("Footer.TFrame", background="#f1f5f9")

        # Botones modernos
        self.style.configure("Nav.TButton", font=("Segoe UI", 9, "bold"), padding=6)
        self.style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), padding=6, background="#0284c7", foreground="#ffffff")
        self.style.map("Primary.TButton",
            background=[("active", "#0369a1"), ("disabled", "#cbd5e1")],
            foreground=[("disabled", "#94a3b8")]
        )

        # Barra de progreso
        self.style.configure("Horizontal.TProgressbar",
            troughcolor="#e2e8f0",
            background="#0284c7",
            lightcolor="#38bdf8",
            darkcolor="#0369a1",
            thickness=16
        )

    def _construir_ui(self):
        # Marco Principal Contenedor
        self.contenedor = tk.Frame(self, bg=COLOR_BG_LIGHT)
        self.contenedor.pack(fill=tk.BOTH, expand=True)

        # 1. Barra Lateral Izquierda (Sidebar Tecnológica)
        self.sidebar = tk.Frame(self.contenedor, bg=COLOR_BG_DARK, width=210)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self.sidebar.pack_propagate(False)

        # Encabezado Sidebar
        lbl_brand = tk.Label(self.sidebar, text="BIMO PRO", font=("Segoe UI", 16, "bold"), fg=COLOR_ACCENT, bg=COLOR_BG_DARK)
        lbl_brand.pack(pady=(28, 2))

        lbl_sub = tk.Label(self.sidebar, text="Copiloto Clínico IA", font=("Segoe UI", 8), fg="#94a3b8", bg=COLOR_BG_DARK)
        lbl_sub.pack(pady=(0, 26))

        # Pasos en sidebar
        self.sidebar_pasos = []
        pasos_nombres = [
            "1. Bienvenida",
            "2. Acuerdos y Licencia",
            "3. Carpeta de Destino",
            "4. Acceso del Doctor",
            "5. Instalación",
            "6. Finalizar"
        ]
        for idx, nom in enumerate(pasos_nombres, 1):
            lbl = tk.Label(self.sidebar, text=nom, font=("Segoe UI", 9), fg="#64748b", bg=COLOR_BG_DARK, anchor="w", padx=22)
            lbl.pack(fill=tk.X, pady=6)
            self.sidebar_pasos.append(lbl)

        # Versión en parte inferior de sidebar
        lbl_ver = tk.Label(self.sidebar, text="Versión 2.0 Pro\nBuild 2026.09 Estable", font=("Segoe UI", 7), fg="#475569", bg=COLOR_BG_DARK, justify="center")
        lbl_ver.pack(side=tk.BOTTOM, pady=16)

        # 2. Marco Derecho (Contenido + Barra Inferior)
        self.main_area = tk.Frame(self.contenedor, bg=COLOR_BG_LIGHT)
        self.main_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Barra de Navegación Inferior (Footer)
        self.footer = tk.Frame(self.main_area, bg="#f1f5f9", height=58, highlightthickness=1, highlightbackground=COLOR_BORDER)
        self.footer.pack(side=tk.BOTTOM, fill=tk.X)
        self.footer.pack_propagate(False)

        self.btn_cancelar = tk.Button(self.footer, text="Cancelar", font=("Segoe UI", 9), width=10, relief="groove", cursor="hand2", command=self._cancelar)
        self.btn_cancelar.pack(side=tk.RIGHT, padx=(6, 20), pady=13)

        self.btn_siguiente = tk.Button(self.footer, text="Siguiente >", font=("Segoe UI", 9, "bold"), bg="#0284c7", fg="#ffffff", activebackground="#0369a1", activeforeground="#ffffff", width=13, relief="flat", cursor="hand2", command=self._siguiente)
        self.btn_siguiente.pack(side=tk.RIGHT, padx=6, pady=13)

        self.btn_atras = tk.Button(self.footer, text="< Atrás", font=("Segoe UI", 9), width=10, relief="groove", cursor="hand2", command=self._atras)
        self.btn_atras.pack(side=tk.RIGHT, padx=6, pady=13)

        # Área de Pasos Dinámicos
        self.content_frame = tk.Frame(self.main_area, bg=COLOR_BG_LIGHT)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=26, pady=18)

    def _actualizar_sidebar(self, paso):
        for idx, lbl in enumerate(self.sidebar_pasos, 1):
            if idx == paso:
                lbl.config(fg="#ffffff", font=("Segoe UI", 9, "bold"), bg="#1e293b")
            elif idx < paso:
                lbl.config(fg=COLOR_ACCENT, font=("Segoe UI", 9), bg=COLOR_BG_DARK)
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
        elif paso == 4:
            self._construir_paso_4_doctor()
        elif paso == 5:
            self._construir_paso_5()
        elif paso == 6:
            self._construir_paso_6()

    # --- PASO 1: BIENVENIDA ---
    def _construir_paso_1(self):
        self.btn_atras.config(state=tk.DISABLED)
        self.btn_siguiente.config(text="Siguiente >", state=tk.NORMAL)
        self.btn_cancelar.config(state=tk.NORMAL)

        lbl_tit = tk.Label(
            self.content_frame,
            text="Bienvenido al Asistente de Instalación\nde BIMO Pro",
            font=("Segoe UI", 15, "bold"),
            fg=COLOR_TEXT_DARK,
            bg=COLOR_BG_LIGHT,
            justify="left"
        )
        lbl_tit.pack(anchor="w", pady=(0, 6))

        lbl_desc = tk.Label(
            self.content_frame,
            text="Copiloto de Inteligencia Artificial para Consultorios Odontológicos y Médicos",
            font=("Segoe UI", 9, "italic"),
            fg=COLOR_PRIMARY,
            bg=COLOR_BG_LIGHT,
            justify="left",
            wraplength=ANCHO_WRAP
        )
        lbl_desc.pack(anchor="w", pady=(0, 14))

        # Tarjeta de características destacadas
        card_feat = tk.Frame(self.content_frame, bg="#ffffff", bd=1, relief="solid", highlightbackground=COLOR_BORDER)
        card_feat.pack(fill=tk.X, pady=(0, 14))

        features = [
            ("Transcripción Acústica en Tiempo Real:", "Captura el dictado clínico continuo y la interacción médico-paciente."),
            ("Estructuración Clínica CIE-10 y Odontograma:", "Organiza diagnósticos, piezas dentales, síntomas y recetas automáticamente."),
            ("Historias Clínicas Oficiales en PDF:", "Genera el Formulario 033 MSP homologado y listo para archivo."),
            ("Gestión Inteligente de Citas y WhatsApp:", "Sincronización con Google Calendar y recordatorios anti-ausentismo."),
            ("Soberanía y Privacidad Local:", "Expedientes almacenados 100% en este equipo con base SQLite WAL.")
        ]

        for titulo, detalle in features:
            f_row = tk.Frame(card_feat, bg="#ffffff")
            f_row.pack(fill=tk.X, padx=12, pady=5)

            lbl_bullet = tk.Label(f_row, text="•", font=("Segoe UI", 12, "bold"), fg=COLOR_PRIMARY, bg="#ffffff")
            lbl_bullet.pack(side=tk.LEFT, anchor="n", padx=(0, 6))

            f_txt = tk.Frame(f_row, bg="#ffffff")
            f_txt.pack(side=tk.LEFT, fill=tk.X, expand=True)

            lbl_t = tk.Label(f_txt, text=titulo, font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_DARK, bg="#ffffff", anchor="w")
            lbl_t.pack(anchor="w")

            lbl_d = tk.Label(f_txt, text=detalle, font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg="#ffffff", justify="left", wraplength=420, anchor="w")
            lbl_d.pack(anchor="w")

        lbl_footer = tk.Label(
            self.content_frame,
            text="Haga clic en 'Siguiente' para revisar los acuerdos de licencia y continuar con la instalación.",
            font=("Segoe UI", 8),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_BG_LIGHT,
            justify="left",
            wraplength=ANCHO_WRAP
        )
        lbl_footer.pack(anchor="w")

    # --- PASO 2: ACUERDOS Y COMPROMISOS (ACEPTACIÓN OBLIGATORIA) ---
    def _construir_paso_2(self):
        self.btn_atras.config(state=tk.NORMAL)
        self.btn_cancelar.config(state=tk.NORMAL)

        lbl_tit = tk.Label(
            self.content_frame,
            text="Acuerdo de Licencia y Compromisos Clínicos",
            font=("Segoe UI", 13, "bold"),
            fg=COLOR_TEXT_DARK,
            bg=COLOR_BG_LIGHT
        )
        lbl_tit.pack(anchor="w", pady=(0, 4))

        lbl_desc = tk.Label(
            self.content_frame,
            text="Por favor, revise atentamente los acuerdos antes de instalar el software en este equipo:",
            font=("Segoe UI", 8),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_BG_LIGHT,
            wraplength=ANCHO_WRAP,
            justify="left"
        )
        lbl_desc.pack(anchor="w", pady=(0, 8))

        # Marco de Aceptación (Empacado al FONDO primero para garantizar visibilidad 100%)
        card_terminos = tk.Frame(self.content_frame, bg="#ffffff", bd=1, relief="solid", highlightbackground=COLOR_BORDER)
        card_terminos.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0))

        lbl_hint = tk.Label(
            card_terminos,
            text="Para continuar con la instalación, debe marcar la siguiente casilla de aceptación:",
            font=("Segoe UI", 8, "italic"),
            fg=COLOR_TEXT_MUTED,
            bg="#ffffff",
            wraplength=440,
            justify="left"
        )
        lbl_hint.pack(anchor="w", padx=14, pady=(8, 3))

        chk = tk.Checkbutton(
            card_terminos,
            text="He leído y acepto los acuerdos de responsabilidad clínica y la licencia de uso",
            variable=self.acepta_terminos,
            font=("Segoe UI", 9, "bold"),
            fg="#0f172a",
            bg="#ffffff",
            activebackground="#ffffff",
            selectcolor="#ffffff",
            cursor="hand2",
            wraplength=440,
            justify="left",
            command=self._on_check_terminos
        )
        chk.pack(anchor="w", padx=14, pady=(0, 8))

        # Cuadro de texto con scroll (Empacado al TOP para ocupar el espacio restante)
        txt_frame = tk.Frame(self.content_frame, bg=COLOR_BORDER)
        txt_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, pady=(0, 2))

        scrollbar = tk.Scrollbar(txt_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        txt = tk.Text(
            txt_frame,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set,
            font=("Segoe UI", 8),
            bg="#ffffff",
            fg="#1e293b",
            relief="flat",
            padx=12,
            pady=10,
            height=10
        )
        txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=txt.yview)

        texto_acuerdos = (
            "ACUERDOS, CONDICIONES Y COMPROMISOS DE USO CLÍNICO — BIMO PRO\n"
            "Software de Asistencia y Gestión Odontológica Inteligente\n"
            "----------------------------------------------------------------------------------------------------\n\n"
            "1. PRIVACIDAD Y SOBERANÍA LOCAL DE DATOS:\n"
            "Los expedientes clínicos, historias clínicas, diagnósticos, recetas, odontogramas y datos "
            "personales de los pacientes se almacenan de manera 100% local en este computador, bajo una "
            "base de datos relacional SQLite configurada en modo WAL (Write-Ahead Logging).\n"
            "El procesamiento de inteligencia artificial se realiza mediante transmisión cifrada punto a punto "
            "(TLS 1.3/SSL). Ningún dato clínico se comparte con terceras partes ni se utiliza para fines "
            "comerciales, analíticos o publicitarios.\n\n"
            "2. DELIMITACIÓN DE RESPONSABILIDAD MÉDICO-LEGAL (COPILOTO CLÍNICO):\n"
            "BIMO Pro opera como una herramienta tecnológica de transcripción acústica inteligente y soporte "
            "a la documentación de consultorio.\n"
            "El software NO constituye un facultativo médico independiente ni sustituye bajo ninguna circunstancia "
            "el criterio profesional, pericia, examen físico ni la anamnesis efectuada por el profesional de la salud.\n"
            "La validación y aprobación final de diagnósticos clínicos, códigos CIE-10, prescripciones farmacológicas, "
            "dosis e indicaciones de tratamiento recaen de manera exclusiva bajo la responsabilidad médica y legal "
            "del profesional tratante.\n\n"
            "3. LICENCIA DE USO Y PROTECCIÓN POR HARDWARE (HWID LOCK):\n"
            "El presente software se licencia de forma exclusiva para el equipo de cómputo autorizado donde se "
            "completa este proceso de instalación.\n"
            "La activación queda vinculada mediante mecanismos criptográficos al identificador de hardware único (HWID) "
            "de esta computadora.\n"
            "Queda terminantemente prohibida la copia, redistribución, clonación, ingeniería inversa o ejecución no "
            "autorizada en computadores ajenos a la licencia original.\n\n"
            "4. ACEPTACIÓN EXPRESA:\n"
            "Al marcar la casilla inferior de aceptación e instalar BIMO Pro, usted certifica haber leído, "
            "comprendido y aceptado en su totalidad las cláusulas y compromisos anteriormente detallados."
        )
        txt.insert(tk.END, texto_acuerdos)
        txt.config(state=tk.DISABLED)

        self._on_check_terminos()

    def _on_check_terminos(self):
        if self.acepta_terminos.get():
            self.btn_siguiente.config(state=tk.NORMAL)
        else:
            self.btn_siguiente.config(state=tk.DISABLED)

    # --- PASO 3: RUTA DE INSTALACIÓN Y OPCIONES ---
    def _construir_paso_3(self):
        self.btn_atras.config(state=tk.NORMAL)
        self.btn_siguiente.config(text="Siguiente >", state=tk.NORMAL)
        self.btn_cancelar.config(state=tk.NORMAL)

        lbl_tit = tk.Label(
            self.content_frame,
            text="Seleccionar Carpeta de Instalación",
            font=("Segoe UI", 13, "bold"),
            fg=COLOR_TEXT_DARK,
            bg=COLOR_BG_LIGHT
        )
        lbl_tit.pack(anchor="w", pady=(0, 4))

        lbl_desc = tk.Label(
            self.content_frame,
            text="El asistente instalará los archivos binarios de BIMO Pro en la siguiente carpeta. Para seleccionar otra ubicación, haga clic en Examinar:",
            font=("Segoe UI", 8),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_BG_LIGHT,
            wraplength=ANCHO_WRAP,
            justify="left"
        )
        lbl_desc.pack(anchor="w", pady=(0, 14))

        # Selector de carpeta
        frame_dir = tk.Frame(self.content_frame, bg=COLOR_BG_LIGHT)
        frame_dir.pack(fill=tk.X, pady=(0, 16))

        ent_dir = tk.Entry(frame_dir, textvariable=self.ruta_destino, font=("Segoe UI", 9), relief="solid", bd=1)
        ent_dir.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 8))

        btn_examinar = tk.Button(frame_dir, text="Examinar...", font=("Segoe UI", 8), relief="groove", cursor="hand2", command=self._examinar_carpeta)
        btn_examinar.pack(side=tk.RIGHT, ipady=2, ipadx=6)

        # Opciones de acceso directo
        lbl_opc = tk.Label(
            self.content_frame,
            text="Opciones adicionales de escritorio:",
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_TEXT_DARK,
            bg=COLOR_BG_LIGHT
        )
        lbl_opc.pack(anchor="w", pady=(0, 6))

        card_opc = tk.Frame(self.content_frame, bg="#ffffff", bd=1, relief="solid", highlightbackground=COLOR_BORDER)
        card_opc.pack(fill=tk.X, pady=(0, 14))

        chk_short = tk.Checkbutton(
            card_opc,
            text="Crear un acceso directo en el Escritorio con el Icono Oficial de BIMO Bot",
            variable=self.crear_shortcut,
            font=("Segoe UI", 8, "bold"),
            fg=COLOR_TEXT_DARK,
            bg="#ffffff",
            activebackground="#ffffff",
            selectcolor="#ffffff",
            cursor="hand2",
            wraplength=440,
            justify="left"
        )
        chk_short.pack(anchor="w", padx=12, pady=10)

        # Espacio requerido
        card_espacio = tk.Frame(self.content_frame, bg="#ffffff", bd=1, relief="solid", highlightbackground=COLOR_BORDER)
        card_espacio.pack(fill=tk.X)

        lbl_espacio = tk.Label(
            card_espacio,
            text="Espacio requerido en disco: ~720 MB\nEspacio disponible: Suficiente para completar la instalación.",
            font=("Segoe UI", 8),
            fg=COLOR_TEXT_MUTED,
            bg="#ffffff",
            justify="left"
        )
        lbl_espacio.pack(anchor="w", padx=12, pady=8)

    def _examinar_carpeta(self):
        sel = filedialog.askdirectory(initialdir=self.ruta_destino.get(), title="Seleccionar Carpeta de Instalación")
        if sel:
            self.ruta_destino.set(os.path.normpath(sel))

    # --- PASO 4: ACCESO DEL DOCTOR Y SEGURIDAD (L-E) ---
    def _construir_paso_4_doctor(self):
        self.btn_atras.config(state=tk.NORMAL)
        self.btn_siguiente.config(text="Siguiente >", state=tk.NORMAL)
        self.btn_cancelar.config(state=tk.NORMAL)

        lbl_tit = tk.Label(
            self.content_frame,
            text="Crear Acceso del Profesional Médico",
            font=("Segoe UI", 13, "bold"),
            fg=COLOR_TEXT_DARK,
            bg=COLOR_BG_LIGHT
        )
        lbl_tit.pack(anchor="w", pady=(0, 4))

        lbl_desc = tk.Label(
            self.content_frame,
            text="Configure sus credenciales maestras de acceso clínico. Se almacenarán localmente bajo hash PBKDF2 sin claves por defecto públicas:",
            font=("Segoe UI", 8),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_BG_LIGHT,
            wraplength=ANCHO_WRAP,
            justify="left"
        )
        lbl_desc.pack(anchor="w", pady=(0, 10))

        card_form = tk.Frame(self.content_frame, bg="#ffffff", bd=1, relief="solid", highlightbackground=COLOR_BORDER)
        card_form.pack(fill=tk.X, pady=(0, 10))

        # Nombre
        f1 = tk.Frame(card_form, bg="#ffffff")
        f1.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(f1, text="Nombre Completo:", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_DARK, bg="#ffffff", width=18, anchor="w").pack(side=tk.LEFT)
        ent_nom = tk.Entry(f1, textvariable=self.doc_nombre, font=("Segoe UI", 9), relief="solid", bd=1)
        ent_nom.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)

        # Correo / Usuario
        f2 = tk.Frame(card_form, bg="#ffffff")
        f2.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(f2, text="Correo / Usuario:", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_DARK, bg="#ffffff", width=18, anchor="w").pack(side=tk.LEFT)
        ent_mail = tk.Entry(f2, textvariable=self.doc_email, font=("Segoe UI", 9), relief="solid", bd=1)
        ent_mail.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)

        # Contraseña
        f3 = tk.Frame(card_form, bg="#ffffff")
        f3.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(f3, text="Contraseña (8+ car.):", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_DARK, bg="#ffffff", width=18, anchor="w").pack(side=tk.LEFT)
        ent_pwd = tk.Entry(f3, textvariable=self.doc_password, font=("Segoe UI", 9), relief="solid", bd=1, show="*")
        ent_pwd.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)

        # Confirmar Contraseña
        f4 = tk.Frame(card_form, bg="#ffffff")
        f4.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(f4, text="Confirmar Clave:", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_DARK, bg="#ffffff", width=18, anchor="w").pack(side=tk.LEFT)
        ent_pwd_c = tk.Entry(f4, textvariable=self.doc_password_conf, font=("Segoe UI", 9), relief="solid", bd=1, show="*")
        ent_pwd_c.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)

        # PIN Rápido
        f5 = tk.Frame(card_form, bg="#ffffff")
        f5.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(f5, text="PIN Rápido (4-6 díg.):", font=("Segoe UI", 8, "bold"), fg=COLOR_TEXT_DARK, bg="#ffffff", width=18, anchor="w").pack(side=tk.LEFT)
        ent_pin = tk.Entry(f5, textvariable=self.doc_pin, font=("Segoe UI", 9), relief="solid", bd=1, show="*")
        ent_pin.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)

        # Clave Groq Opcional
        f6 = tk.Frame(card_form, bg="#ffffff")
        f6.pack(fill=tk.X, padx=14, pady=4)
        tk.Label(f6, text="Clave API Groq (Opc.):", font=("Segoe UI", 8), fg=COLOR_TEXT_MUTED, bg="#ffffff", width=18, anchor="w").pack(side=tk.LEFT)
        ent_groq = tk.Entry(f6, textvariable=self.groq_api_key, font=("Segoe UI", 9), relief="solid", bd=1, show="*")
        ent_groq.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=2)

        lbl_info = tk.Label(
            self.content_frame,
            text="* El PIN permite iniciar sesión ágilmente en el consultorio. Si no configura un PIN numérico, el ingreso será por correo y contraseña.",
            font=("Segoe UI", 8, "italic"),
            fg="#64748b",
            bg=COLOR_BG_LIGHT,
            wraplength=ANCHO_WRAP,
            justify="left"
        )
        lbl_info.pack(anchor="w")

    # --- PASO 5: PROGRESO DE INSTALACIÓN ---
    def _construir_paso_5(self):
        self.btn_atras.config(state=tk.DISABLED)
        self.btn_siguiente.config(state=tk.DISABLED)
        self.btn_cancelar.config(state=tk.DISABLED)

        lbl_tit = tk.Label(
            self.content_frame,
            text="Instalando BIMO Pro Clínico...",
            font=("Segoe UI", 13, "bold"),
            fg=COLOR_TEXT_DARK,
            bg=COLOR_BG_LIGHT
        )
        lbl_tit.pack(anchor="w", pady=(12, 6))

        self.lbl_estado = tk.Label(
            self.content_frame,
            text="Iniciando desempaquetado de archivos binarios...",
            font=("Segoe UI", 9),
            fg=COLOR_TEXT_MUTED,
            bg=COLOR_BG_LIGHT,
            wraplength=ANCHO_WRAP,
            justify="left"
        )
        self.lbl_estado.pack(anchor="w", pady=(0, 16))

        # Barra de progreso
        self.progress = ttk.Progressbar(self.content_frame, orient="horizontal", mode="determinate", length=450, style="Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 10))

        self.lbl_detalles = tk.Label(
            self.content_frame,
            text="Preparando entorno de ejecución...",
            font=("Segoe UI", 8),
            fg="#94a3b8",
            bg=COLOR_BG_LIGHT,
            wraplength=ANCHO_WRAP,
            justify="left"
        )
        self.lbl_detalles.pack(anchor="w")

        # Iniciar hilo de extracción
        t = threading.Thread(target=self._ejecutar_instalacion_hilo, daemon=True)
        t.start()

    def _ejecutar_instalacion_hilo(self):
        try:
            destino = os.path.normpath(self.ruta_destino.get())
            os.makedirs(destino, exist_ok=True)

            # 1. Extraer payload zip
            if not self.payload_zip or not os.path.exists(self.payload_zip):
                raise FileNotFoundError("No se encontró el archivo de paquete bimo_payload.zip.")

            dest_db = os.path.join(destino, "bimo.db")
            es_actualizacion = os.path.exists(dest_db)

            # Si es actualización, crear respaldo previo con sqlite3.backup()
            if es_actualizacion:
                self.lbl_estado.config(text="Creando respaldo previo de la base de datos existente...")
                resp_dir = os.path.join(destino, "Respaldos_Locales")
                os.makedirs(resp_dir, exist_ok=True)
                ts_bk = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                bk_dest = os.path.join(resp_dir, f"bimo_pre_update_{ts_bk}.db")
                try:
                    import sqlite3
                    with sqlite3.connect(dest_db) as src, sqlite3.connect(bk_dest) as dst:
                        src.backup(dst)
                except Exception as e_bk:
                    print(f"[WARN BACKUP PRE-UPDATE]: {e_bk}")

            self.lbl_estado.config(text="Desempaquetando archivos binarios del sistema...")
            PROTECTED_FILES = {
                "bimo.db", "bimo.db-wal", "bimo.db-shm", "bimo.vault",
                "clinica.json", "vocabulario_aprendido.json", "token.json", "bimo.lic"
            }
            with zipfile.ZipFile(self.payload_zip, 'r') as zf:
                miembros = zf.infolist()
                total = len(miembros)
                for idx, miembro in enumerate(miembros):
                    m_norm = os.path.normpath(miembro.filename)
                    # Protección: nunca sobrescribir archivos clínicos existentes
                    if os.path.basename(m_norm) in PROTECTED_FILES and os.path.exists(os.path.join(destino, m_norm)):
                        continue
                    if (m_norm.startswith("Pacientes\\") or m_norm.startswith("Pacientes/")) and os.path.exists(os.path.join(destino, m_norm)):
                        continue
                    zf.extract(miembro, destino)
                    if idx % 15 == 0 or idx == total - 1:
                        pct = int((idx / total) * 70)
                        self.progress["value"] = pct
                        self.lbl_detalles.config(text=f"Extrayendo: {miembro.filename[:45]}")
                        self.update_idletasks()

            # 2. Inicializar carpetas de datos
            self.lbl_estado.config(text="Configurando carpetas de expedientes clínicos...")
            self.progress["value"] = 75
            pac_dest = os.path.join(destino, "Pacientes")
            os.makedirs(os.path.join(pac_dest, "Pacientes_Adultos"), exist_ok=True)
            os.makedirs(os.path.join(pac_dest, "Pacientes_Pediatricos"), exist_ok=True)
            os.makedirs(os.path.join(destino, "assets", "sounds"), exist_ok=True)
            os.makedirs(os.path.join(destino, "data"), exist_ok=True)
            os.makedirs(os.path.join(destino, "Respaldos_Locales"), exist_ok=True)

            # Si clinica.json no existe pero vino clinica.default.json, copiarlo
            clinica_dest = os.path.join(destino, "clinica.json")
            clinica_def = os.path.join(destino, "clinica.default.json")
            if not os.path.exists(clinica_dest) and os.path.exists(clinica_def):
                import shutil
                shutil.copy2(clinica_def, clinica_dest)

            # 3. Registrar aceptación legal en clinica.json
            self.lbl_estado.config(text="Registrando aceptación de acuerdos clínicos...")
            self.progress["value"] = 80
            clinica_data = {}
            if os.path.exists(clinica_dest):
                try:
                    with open(clinica_dest, "r", encoding="utf-8") as f:
                        clinica_data = json.load(f)
                except Exception:
                    clinica_data = {}
            clinica_data["terminos_aceptados"] = True
            clinica_data["fecha_aceptacion_terminos"] = datetime.datetime.now().isoformat()
            clinica_data["version_terminos"] = "1.0"
            try:
                with open(clinica_dest, "w", encoding="utf-8") as f:
                    json.dump(clinica_data, f, ensure_ascii=False, indent=2)
            except Exception as e_cl:
                print(f"[WARN clinica.json] {e_cl}")

            # 4. Vincular licencia HWID local y configurar base de datos / credenciales
            self.lbl_estado.config(text="Inicializando base de datos y autorizando hardware...")
            self.progress["value"] = 85
            exe_path = os.path.join(destino, "BIMO_Pro.exe")
            flags = 0x08000000 if sys.platform == "win32" else 0

            cmd_init = []
            if os.path.exists(exe_path):
                cmd_init = [exe_path, "--setup-init"]
            elif os.path.exists(os.path.join(destino, "main.py")):
                cmd_init = [sys.executable, os.path.join(destino, "main.py"), "--setup-init"]

            doc_temp_path = None
            if not es_actualizacion and self.doc_password.get().strip():
                doc_info = {
                    "nombre": self.doc_nombre.get().strip() or "Dr. Odontólogo",
                    "email": self.doc_email.get().strip().lower() or "doctor@bimo.local",
                    "password": self.doc_password.get().strip(),
                    "pin": self.doc_pin.get().strip(),
                    "api_key": self.groq_api_key.get().strip()
                }
                import tempfile
                fd, doc_temp_path = tempfile.mkstemp(prefix="bimo_doc_", suffix=".json")
                with os.fdopen(fd, "w", encoding="utf-8") as tf:
                    json.dump(doc_info, tf)
                cmd_init.extend(["--doctor-file", doc_temp_path])

            # Buscar bimo_secrets.env junto al instalador o en directorio actual
            installer_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            cand_sec = os.path.join(installer_dir, "bimo_secrets.env")
            if not os.path.exists(cand_sec):
                cand_sec = os.path.join(os.getcwd(), "bimo_secrets.env")
            if os.path.exists(cand_sec):
                cmd_init.extend(["--secrets-file", cand_sec])

            if cmd_init:
                try:
                    proc = subprocess.run(cmd_init, cwd=destino, timeout=120, creationflags=flags)
                    if proc.returncode != 0:
                        raise RuntimeError(f"--setup-init devolvió código {proc.returncode}. Revise bimo_install.log.")
                finally:
                    if doc_temp_path and os.path.exists(doc_temp_path):
                        try:
                            with open(doc_temp_path, "wb") as f_del:
                                f_del.write(os.urandom(1024))
                            os.remove(doc_temp_path)
                        except Exception:
                            pass

            self.update_idletasks()
            time.sleep(0.3)

            # 5. Registrar desinstalador oficial en Windows (Agregar o Quitar Programas)
            self.lbl_estado.config(text="Registrando desinstalador en Windows...")
            self.progress["value"] = 93
            ico_path = os.path.join(destino, "assets", "bimo_icon.ico")
            registrar_desinstalador_windows(destino, exe_path, ico_path)

            self.update_idletasks()
            time.sleep(0.2)

            # 6. Crear acceso directo con icono oficial
            if self.crear_shortcut.get():
                self.lbl_estado.config(text="Creando acceso directo en el Escritorio con icono oficial...")
                crear_acceso_directo(destino, exe_path, ico_path)

            self.progress["value"] = 100
            self.lbl_estado.config(text="¡Instalación completada exitosamente!")
            self.lbl_detalles.config(text="Todos los componentes fueron verificados.")
            self.update_idletasks()
            time.sleep(0.5)

            # Pasar automáticamente al paso 6 (Finalizar)
            self.after(200, lambda: self._mostrar_paso(6))

        except Exception as e:
            messagebox.showerror("Error en la Instalación", f"Ocurrió un problema durante la instalación:\n{e}")
            self.btn_cancelar.config(state=tk.NORMAL)

    # --- PASO 6: FINALIZAR ---
    def _construir_paso_6(self):
        self.btn_atras.config(state=tk.DISABLED)
        self.btn_cancelar.config(state=tk.DISABLED)
        self.btn_siguiente.config(text="Finalizar", state=tk.NORMAL)

        lbl_tit = tk.Label(
            self.content_frame,
            text="¡Completada la Instalación de BIMO Pro!",
            font=("Segoe UI", 14, "bold"),
            fg="#16a34a",
            bg=COLOR_BG_LIGHT
        )
        lbl_tit.pack(anchor="w", pady=(8, 12))

        destino = self.ruta_destino.get()

        card_fin = tk.Frame(self.content_frame, bg="#ffffff", bd=1, relief="solid", highlightbackground=COLOR_BORDER)
        card_fin.pack(fill=tk.X, pady=(0, 16))

        msg = (
            "BIMO Pro ha sido instalado y configurado correctamente en su computadora.\n\n"
            f"Carpeta de la aplicación:\n{destino}\n\n"
            "Los acuerdos de responsabilidad médica y la licencia por hardware han quedado registrados permanentemente.\n\n"
            "Al iniciar BIMO Pro, ingresará directamente a la interfaz clínica de atención con sus credenciales seguras."
        )
        lbl_body = tk.Label(
            card_fin,
            text=msg,
            font=("Segoe UI", 8),
            fg=COLOR_TEXT_DARK,
            bg="#ffffff",
            justify="left",
            wraplength=440
        )
        lbl_body.pack(anchor="w", padx=14, pady=12)

        chk_run = tk.Checkbutton(
            self.content_frame,
            text="Ejecutar BIMO Pro ahora mismo al salir del instalador",
            variable=self.ejecutar_al_finalizar,
            font=("Segoe UI", 9, "bold"),
            fg=COLOR_TEXT_DARK,
            bg=COLOR_BG_LIGHT,
            activebackground=COLOR_BG_LIGHT,
            selectcolor="#ffffff",
            cursor="hand2",
            wraplength=ANCHO_WRAP,
            justify="left"
        )
        chk_run.pack(anchor="w")

    def _siguiente(self):
        if self.paso_actual == 2 and not self.acepta_terminos.get():
            messagebox.showwarning("Atención", "Debe aceptar los acuerdos y compromisos para continuar con la instalación.")
            return

        if self.paso_actual == 3:
            dest = os.path.normpath(self.ruta_destino.get().strip())
            dest_lower = dest.lower()
            if "program files" in dest_lower or "windows" in dest_lower:
                if not messagebox.askyesno(
                    "Advertencia de Ubicación",
                    "Ha seleccionado una carpeta del sistema (Program Files o Windows).\n\n"
                    "Instalar en esta ubicación puede causar problemas de permisos de escritura para la base de datos local y expedientes clínicos.\n\n"
                    "¿Desea continuar con esta ubicación a pesar de la advertencia?",
                    parent=self
                ):
                    return

            dest_db = os.path.join(dest, "bimo.db")
            if os.path.exists(dest_db):
                # Actualización detectada: saltar paso 4 y pasar a instalación
                self._mostrar_paso(5)
            else:
                self._mostrar_paso(4)
            return

        if self.paso_actual == 4:
            nom = self.doc_nombre.get().strip()
            mail = self.doc_email.get().strip()
            pwd = self.doc_password.get().strip()
            pwd_c = self.doc_password_conf.get().strip()
            pin = self.doc_pin.get().strip()

            if not nom:
                messagebox.showwarning("Atención", "Por favor ingrese el nombre del profesional.", parent=self)
                return
            if not mail or "@" not in mail:
                messagebox.showwarning("Atención", "Por favor ingrese un correo electrónico válido.", parent=self)
                return
            if len(pwd) < 8:
                messagebox.showwarning("Atención", "La contraseña de acceso debe tener al menos 8 caracteres.", parent=self)
                return
            if pwd != pwd_c:
                messagebox.showwarning("Atención", "Las contraseñas ingresadas no coinciden.", parent=self)
                return
            if pin and (not pin.isdigit() or not (4 <= len(pin) <= 6)):
                messagebox.showwarning("Atención", "El PIN debe ser numérico y contener entre 4 y 6 dígitos.", parent=self)
                return

            self._mostrar_paso(5)
            return

        if self.paso_actual < 6:
            self._mostrar_paso(self.paso_actual + 1)
        else:
            # Finalizar
            if self.ejecutar_al_finalizar.get():
                exe_path = os.path.join(self.ruta_destino.get(), "BIMO_Pro.exe")
                if os.path.exists(exe_path):
                    flags = 0x08000000 if sys.platform == "win32" else 0
                    subprocess.Popen([exe_path], cwd=self.ruta_destino.get(), creationflags=flags)
            self.destroy()

    def _atras(self):
        if self.paso_actual == 5:
            # En instalación, atrás deshabilitado
            return
        elif self.paso_actual == 4:
            self._mostrar_paso(3)
        elif self.paso_actual > 1:
            self._mostrar_paso(self.paso_actual - 1)

    def _cancelar(self):
        if self.paso_actual < 5 or self.paso_actual == 6:
            if self.paso_actual < 5:
                if messagebox.askyesno("Cancelar Instalación", "¿Está seguro de que desea salir del asistente de instalación?"):
                    self.destroy()
            else:
                self.destroy()

def ejecutar_instalacion_silenciosa(destino, sin_acceso=False):
    """
    Modo silencioso para pruebas automatizadas e instalaciones desatendidas:
    Setup_BIMO_Pro.exe --silent --dest <ruta> [--sin-acceso]
    """
    try:
        destino = os.path.normpath(destino)
        print(f"[SETUP SILENT] Iniciando instalación en: {destino}")
        os.makedirs(destino, exist_ok=True)
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        payload_zip = os.path.join(base_dir, "bimo_payload.zip")
        if not os.path.exists(payload_zip):
            alt = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "bimo_payload.zip")
            if os.path.exists(alt):
                payload_zip = alt
            else:
                print("[SETUP SILENT ERROR] No se encontró bimo_payload.zip")
                return 1

        dest_db = os.path.join(destino, "bimo.db")
        es_actualizacion = os.path.exists(dest_db)
        if es_actualizacion:
            resp_dir = os.path.join(destino, "Respaldos_Locales")
            os.makedirs(resp_dir, exist_ok=True)
            ts_bk = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            bk_dest = os.path.join(resp_dir, f"bimo_pre_update_{ts_bk}.db")
            try:
                import sqlite3
                with sqlite3.connect(dest_db) as src, sqlite3.connect(bk_dest) as dst:
                    src.backup(dst)
                print(f"[SETUP SILENT] Backup pre-update guardado en: {bk_dest}")
            except Exception as e_bk:
                print(f"[SETUP SILENT WARN] Error en backup pre-update: {e_bk}")

        PROTECTED_FILES = {
            "bimo.db", "bimo.db-wal", "bimo.db-shm", "bimo.vault",
            "clinica.json", "vocabulario_aprendido.json", "token.json", "bimo.lic"
        }
        with zipfile.ZipFile(payload_zip, 'r') as zf:
            for m in zf.infolist():
                m_norm = os.path.normpath(m.filename)
                if os.path.basename(m_norm) in PROTECTED_FILES and os.path.exists(os.path.join(destino, m_norm)):
                    continue
                if (m_norm.startswith("Pacientes\\") or m_norm.startswith("Pacientes/")) and os.path.exists(os.path.join(destino, m_norm)):
                    continue
                zf.extract(m, destino)

        pac_dest = os.path.join(destino, "Pacientes")
        os.makedirs(os.path.join(pac_dest, "Pacientes_Adultos"), exist_ok=True)
        os.makedirs(os.path.join(pac_dest, "Pacientes_Pediatricos"), exist_ok=True)
        os.makedirs(os.path.join(destino, "assets", "sounds"), exist_ok=True)
        os.makedirs(os.path.join(destino, "data"), exist_ok=True)
        os.makedirs(os.path.join(destino, "Respaldos_Locales"), exist_ok=True)

        clinica_dest = os.path.join(destino, "clinica.json")
        clinica_def = os.path.join(destino, "clinica.default.json")
        if not os.path.exists(clinica_dest) and os.path.exists(clinica_def):
            import shutil
            shutil.copy2(clinica_def, clinica_dest)

        clinica_data = {}
        if os.path.exists(clinica_dest):
            try:
                with open(clinica_dest, "r", encoding="utf-8") as f:
                    clinica_data = json.load(f)
            except Exception:
                pass
        clinica_data["terminos_aceptados"] = True
        clinica_data["fecha_aceptacion_terminos"] = datetime.datetime.now().isoformat()
        clinica_data["version_terminos"] = "1.0"
        try:
            with open(clinica_dest, "w", encoding="utf-8") as f:
                json.dump(clinica_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        exe_path = os.path.join(destino, "BIMO_Pro.exe")
        cmd_init = []
        if os.path.exists(exe_path):
            cmd_init = [exe_path, "--setup-init"]
        elif os.path.exists(os.path.join(destino, "main.py")):
            cmd_init = [sys.executable, os.path.join(destino, "main.py"), "--setup-init"]

        doc_temp_path = None
        if not sin_acceso and not es_actualizacion:
            doc_info = {
                "nombre": "Dr. Pruebas Automáticas",
                "email": "doctor@bimo.local",
                "password": "PasswordPrueba123",
                "pin": "1234"
            }
            import tempfile
            fd, doc_temp_path = tempfile.mkstemp(prefix="bimo_doc_", suffix=".json")
            with os.fdopen(fd, "w", encoding="utf-8") as tf:
                json.dump(doc_info, tf)
            cmd_init.extend(["--doctor-file", doc_temp_path])

        if cmd_init:
            flags = 0x08000000 if sys.platform == "win32" else 0
            try:
                proc = subprocess.run(cmd_init, cwd=destino, timeout=120, creationflags=flags)
                if proc.returncode != 0:
                    print(f"[SETUP SILENT ERROR] --setup-init retornó código {proc.returncode}")
                    return 1
            finally:
                if doc_temp_path and os.path.exists(doc_temp_path):
                    try:
                        with open(doc_temp_path, "wb") as f_del:
                            f_del.write(os.urandom(1024))
                        os.remove(doc_temp_path)
                    except Exception:
                        pass

        ico_path = os.path.join(destino, "assets", "bimo_icon.ico")
        registrar_desinstalador_windows(destino, exe_path, ico_path)
        crear_acceso_directo(destino, exe_path, ico_path)
        print("[SETUP SILENT OK] Instalación silenciosa completada con éxito.")
        return 0
    except Exception as e:
        print(f"[SETUP SILENT FATAL]: {e}")
        return 1

if __name__ == "__main__":
    if "--silent" in sys.argv:
        dest_arg = obtener_ruta_instalacion_default()
        if "--dest" in sys.argv:
            idx = sys.argv.index("--dest")
            if idx + 1 < len(sys.argv):
                dest_arg = sys.argv[idx + 1]
        sin_acc = "--sin-acceso" in sys.argv
        sys.exit(ejecutar_instalacion_silenciosa(dest_arg, sin_acceso=sin_acc))
    else:
        app = BimoSetupWizard()
        app.mainloop()
