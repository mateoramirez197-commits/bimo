# -*- coding: utf-8 -*-
r"""
restaurar_respaldo.py
Herramienta independiente para restaurar respaldos locales o descargados de Google Drive.
Soporta archivos:
  - .zip (respaldo estándar sin cifrar)
  - .zip.enc / .enc (respaldo clínico cifrado E2E formato BIMOENC1 con PBKDF2 + Fernet)

Modos de uso:
  1. Gráfico (Tkinter): python restaurar_respaldo.py
  2. Línea de comandos (CLI):
     python restaurar_respaldo.py --archivo "C:\ruta\respaldo.zip.enc" --destino "C:\destino\data" --passphrase "mi_clave_segura"
"""

import sys
import os
import argparse
import base64
import hashlib
import zipfile
import sqlite3
import tempfile
from pathlib import Path

def descifrar_archivo(ruta_cifrada: str, ruta_salida_zip: str, passphrase: str) -> bool:
    """
    Descifra un archivo con formato BIMOENC1:
    - Cabecera: b'BIMOENC1' (8 bytes)
    - Salt: 16 bytes
    - Token: Fernet payload derivado con PBKDF2-HMAC-SHA256 (200,000 iteraciones)
    """
    if not passphrase:
        raise ValueError("Se requiere una contraseña para descifrar este archivo.")

    from cryptography.fernet import Fernet, InvalidToken

    with open(ruta_cifrada, "rb") as f:
        header = f.read(8)
        if header != b"BIMOENC1":
            raise ValueError("Formato de cifrado no reconocido (cabecera BIMOENC1 faltante o inválida).")
        salt = f.read(16)
        token = f.read()

    # Derivación de clave idéntica a drive_backup._cifrar
    key = base64.urlsafe_b64encode(hashlib.pbkdf2_hmac("sha256", passphrase.encode("utf-8"), salt, 200_000))
    fernet = Fernet(key)

    try:
        data_descomprimida = fernet.decrypt(token)
    except InvalidToken:
        raise ValueError("Contraseña incorrecta o el archivo de respaldo está dañado.")
    except Exception as e:
        raise ValueError(f"Error al descifrar el archivo: {e}")

    with open(ruta_salida_zip, "wb") as f_out:
        f_out.write(data_descomprimida)

    return True

def restaurar_desde_zip(ruta_zip: str, carpeta_destino: str) -> dict:
    """
    Descomprime el zip de respaldo en la carpeta destino y valida la integridad de bimo.db.
    """
    os.makedirs(carpeta_destino, exist_ok=True)
    with zipfile.ZipFile(ruta_zip, "r") as z:
        z.extractall(carpeta_destino)

    db_path = os.path.join(carpeta_destino, "bimo.db")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"El archivo bimo.db no se encontró dentro del respaldo extraído en {carpeta_destino}.")

    # Verificación de integridad SQLite
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        filas = cursor.fetchall()
        if not filas or filas[0][0] != "ok":
            raise ValueError(f"Falla crítica en la verificación de integridad de SQLite: {filas}")
    finally:
        conn.close()

    total_pacientes_dir = os.path.join(carpeta_destino, "Pacientes")
    num_pacientes_archivos = 0
    if os.path.isdir(total_pacientes_dir):
        for _, _, files in os.walk(total_pacientes_dir):
            num_pacientes_archivos += len(files)

    return {
        "status": "ok",
        "mensaje": "Respaldo restaurado con éxito e integridad SQLite verificada.",
        "db_path": db_path,
        "pacientes_archivos": num_pacientes_archivos
    }

def ejecutar_restauracion(ruta_archivo: str, carpeta_destino: str, passphrase: str = None) -> dict:
    """Función de alto nivel que detecta si el archivo está cifrado y ejecuta la restauración."""
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"No existe el archivo especificado: {ruta_archivo}")

    # Determinar si está cifrado leyendo los primeros 8 bytes
    es_cifrado = False
    with open(ruta_archivo, "rb") as f_chk:
        head = f_chk.read(8)
        if head == b"BIMOENC1":
            es_cifrado = True

    if es_cifrado:
        with tempfile.TemporaryDirectory(prefix="bimo_restore_") as tmpdir:
            tmp_zip = os.path.join(tmpdir, "desempaquetado.zip")
            descifrar_archivo(ruta_archivo, tmp_zip, passphrase)
            return restaurar_desde_zip(tmp_zip, carpeta_destino)
    else:
        return restaurar_desde_zip(ruta_archivo, carpeta_destino)

def lanzar_gui():
    """Interfaz gráfica amigable e independiente con Tkinter."""
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("BIMO Pro - Restauración de Respaldo Clínico")
    root.geometry("640x420")
    root.minsize(580, 360)
    root.configure(bg="#0B0F19")

    # Estilos TTK
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TLabel", background="#0B0F19", foreground="#F8FAFC", font=("Segoe UI", 10))
    style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#00F5D4")
    style.configure("TEntry", fieldbackground="#141C2E", foreground="#F8FAFC", insertcolor="#F8FAFC")
    style.configure("Action.TButton", background="#2563EB", foreground="#FFFFFF", font=("Segoe UI", 10, "bold"), padding=6)
    style.map("Action.TButton", background=[("active", "#1D4ED8")])

    main_frame = tk.Frame(root, bg="#0B0F19", padx=24, pady=20)
    main_frame.pack(fill="both", expand=True)

    lbl_header = ttk.Label(main_frame, text="Restaurador de Respaldo Clínico BIMO", style="Header.TLabel")
    lbl_header.pack(anchor="w", pady=(0, 6))

    lbl_sub = ttk.Label(main_frame, text="Restaura historias clínicas y expedientes desde archivos .zip o .enc cifrados.", font=("Segoe UI", 9))
    lbl_sub.pack(anchor="w", pady=(0, 20))

    # 1. Archivo de respaldo
    lbl_arch = ttk.Label(main_frame, text="1. Archivo de respaldo (.zip o .enc):")
    lbl_arch.pack(anchor="w")
    f_arch = tk.Frame(main_frame, bg="#0B0F19")
    f_arch.pack(fill="x", pady=(4, 12))
    ent_arch = tk.Entry(f_arch, bg="#141C2E", fg="#F8FAFC", insertbackground="#F8FAFC", relief="flat", font=("Segoe UI", 10))
    ent_arch.pack(side="left", fill="x", expand=True, ipady=4)

    def sel_archivo():
        fn = filedialog.askopenfilename(
            title="Seleccionar archivo de respaldo",
            filetypes=[("Respaldos BIMO", "*.zip;*.enc;*.zip.enc"), ("Todos los archivos", "*.*")]
        )
        if fn:
            ent_arch.delete(0, tk.END)
            ent_arch.insert(0, fn)
            # Detectar si está cifrado para habilitar contraseña
            try:
                with open(fn, "rb") as test_f:
                    if test_f.read(8) == b"BIMOENC1":
                        ent_pass.config(state="normal")
            except Exception:
                pass

    btn_arch = tk.Button(f_arch, text="Examinar...", command=sel_archivo, bg="#1E293B", fg="#F8FAFC", relief="flat", padx=12)
    btn_arch.pack(side="left", padx=(8, 0))

    # 2. Contraseña (si aplica)
    lbl_pass = ttk.Label(main_frame, text="2. Contraseña de descifrado (requerida solo para archivos .enc):")
    lbl_pass.pack(anchor="w")
    ent_pass = tk.Entry(main_frame, bg="#141C2E", fg="#F8FAFC", insertbackground="#F8FAFC", show="*", relief="flat", font=("Segoe UI", 10))
    ent_pass.pack(fill="x", pady=(4, 12), ipady=4)

    # 3. Carpeta de destino
    lbl_dest = ttk.Label(main_frame, text="3. Carpeta de destino (donde se restaurará bimo.db y Pacientes/):")
    lbl_dest.pack(anchor="w")
    f_dest = tk.Frame(main_frame, bg="#0B0F19")
    f_dest.pack(fill="x", pady=(4, 16))

    # Destino por defecto:AppData/Local/BIMO_Pro/data o ruta de BIMO
    def_dest = os.path.join(os.getenv("LOCALAPPDATA", str(Path.home())), "BIMO_Pro", "data")
    ent_dest = tk.Entry(f_dest, bg="#141C2E", fg="#F8FAFC", insertbackground="#F8FAFC", relief="flat", font=("Segoe UI", 10))
    ent_dest.insert(0, def_dest)
    ent_dest.pack(side="left", fill="x", expand=True, ipady=4)

    def sel_destino():
        dn = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if dn:
            ent_dest.delete(0, tk.END)
            ent_dest.insert(0, dn)

    btn_dest = tk.Button(f_dest, text="Examinar...", command=sel_destino, bg="#1E293B", fg="#F8FAFC", relief="flat", padx=12)
    btn_dest.pack(side="left", padx=(8, 0))

    # Estado y botón de acción
    lbl_status = tk.Label(main_frame, text="Listo para restaurar.", bg="#0B0F19", fg="#94A3B8", font=("Segoe UI", 9))
    lbl_status.pack(anchor="w", pady=(0, 12))

    def accion_restaurar():
        arch = ent_arch.get().strip()
        dest = ent_dest.get().strip()
        pwd = ent_pass.get().strip() or None

        if not arch:
            messagebox.showwarning("Atención", "Por favor seleccione un archivo de respaldo.")
            return
        if not dest:
            messagebox.showwarning("Atención", "Por favor seleccione la carpeta de destino.")
            return

        lbl_status.config(text="Procesando y verificando integridad...", fg="#FBC02D")
        root.update_idletasks()

        try:
            res = ejecutar_restauracion(arch, dest, pwd)
            lbl_status.config(text="Restauración completada con éxito.", fg="#00F5D4")
            messagebox.showinfo(
                "Restauración Exitosa",
                f"El respaldo se ha restaurado correctamente.\n\n"
                f"- Base de datos: {res['db_path']}\n"
                f"- Integridad SQLite: VERIFICADA (OK)\n"
                f"- Archivos clínicos restaurados: {res['pacientes_archivos']}"
            )
        except Exception as e:
            lbl_status.config(text=f"Error: {e}", fg="#FF006E")
            messagebox.showerror("Error de Restauración", str(e))

    btn_run = tk.Button(main_frame, text="Iniciar Restauración", command=accion_restaurar, bg="#00F5D4", fg="#070913", font=("Segoe UI", 11, "bold"), relief="flat", pady=8, cursor="hand2")
    btn_run.pack(fill="x")

    root.mainloop()

def main():
    parser = argparse.ArgumentParser(description="Restaurador independiente de respaldos BIMO Pro (CLI / GUI)")
    parser.add_argument("--archivo", help="Ruta al archivo .zip o .enc de respaldo")
    parser.add_argument("--destino", help="Carpeta de destino para restaurar bimo.db y Pacientes/")
    parser.add_argument("--passphrase", help="Contraseña de descifrado si el archivo está cifrado")
    parser.add_argument("--gui", action="store_true", help="Forzar apertura de la interfaz gráfica Tkinter")

    args = parser.parse_args()

    # Si se especificaron parámetros CLI completos y no se forzó GUI, correr en CLI
    if args.archivo and args.destino and not args.gui:
        try:
            res = ejecutar_restauracion(args.archivo, args.destino, args.passphrase)
            print(f"[RESTAURACIÓN OK] {res['mensaje']}")
            print(f"  Base de datos: {res['db_path']}")
            print(f"  Archivos clínicos: {res['pacientes_archivos']}")
            sys.exit(0)
        except Exception as e:
            print(f"[RESTAURACIÓN ERROR] {e}")
            sys.exit(1)
    else:
        lanzar_gui()

if __name__ == "__main__":
    main()
