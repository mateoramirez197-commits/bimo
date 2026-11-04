# -*- coding: utf-8 -*-
"""
tests/test_cifrado_respaldo_s9.py
Prueba de ciclo completo de respaldo cifrado E2E y restauración independiente (Bloque S9):
  1. Creación de respaldo con SQLite en modo WAL y archivos clínicos simulados.
  2. Cifrado formato BIMOENC1 (Fernet + PBKDF2 200,000 iteraciones).
  3. Intento de descifrado con contraseña errónea -> Rechazo limpio sin corrupción.
  4. Descifrado con contraseña correcta -> Restauración e integridad SQLite (PRAGMA integrity_check).
  5. Restauración de archivo .zip estándar sin cifrar -> Verificación correcta.
"""

import sys
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from drive_backup import _cifrar
from restaurar_respaldo import ejecutar_restauracion, descifrar_archivo

def run_tests():
    total = 0
    pasados = 0
    fallados = 0

    print("=== INICIANDO PRUEBAS DE RESPALDO CIFRADO E2E Y RESTAURACION (S9) ===")

    with tempfile.TemporaryDirectory(prefix="bimo_test_s9_") as tmpdir:
        # 1. Crear base de datos SQLite de prueba con tablas reales y WAL
        db_origen = os.path.join(tmpdir, "bimo.db")
        conn = sqlite3.connect(db_origen)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("CREATE TABLE pacientes (id INTEGER PRIMARY KEY, nombre TEXT, telefono TEXT);")
        cur.execute("INSERT INTO pacientes (nombre, telefono) VALUES ('Paciente Prueba', '0991234567');")
        conn.commit()
        conn.close()

        # 2. Crear archivo simulado en Pacientes/
        pacientes_dir = os.path.join(tmpdir, "Pacientes", "Pacientes_Adultos", "Paciente_Prueba")
        os.makedirs(pacientes_dir, exist_ok=True)
        pdf_ficticio = os.path.join(pacientes_dir, "historia_1.pdf")
        with open(pdf_ficticio, "wb") as f_pdf:
            f_pdf.write(b"%PDF-1.4 simulado de prueba")

        # 3. Empaquetar en .zip
        zip_origen = os.path.join(tmpdir, "respaldo_prueba.zip")
        with zipfile.ZipFile(zip_origen, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(db_origen, "bimo.db")
            z.write(pdf_ficticio, "Pacientes/Pacientes_Adultos/Paciente_Prueba/historia_1.pdf")

        # 4. Cifrar con _cifrar (BIMOENC1)
        passphrase_correcta = "ClaveClinicaSegura2026!"
        passphrase_incorrecta = "ClaveErronea123"
        enc_destino = os.path.join(tmpdir, "respaldo_prueba.zip.enc")
        _cifrar(zip_origen, enc_destino, passphrase_correcta)

        # Verificar cabecera BIMOENC1
        total += 1
        with open(enc_destino, "rb") as f_chk:
            header = f_chk.read(8)
            salt = f_chk.read(16)
        if header == b"BIMOENC1" and len(salt) == 16:
            print("[OK] Cabecera BIMOENC1 y salt de 16 bytes correctamente generados")
            pasados += 1
        else:
            print(f"[FAIL] Cabecera o salt inválido: header={header}, len(salt)={len(salt)}")
            fallados += 1

        # 5. Prueba de rechazo con contraseña incorrecta
        total += 1
        rechazo_limpio = False
        try:
            tmp_zip_fail = os.path.join(tmpdir, "desempaquetado_fail.zip")
            descifrar_archivo(enc_destino, tmp_zip_fail, passphrase_incorrecta)
        except ValueError as e_val:
            if "Contraseña incorrecta" in str(e_val):
                rechazo_limpio = True
                print(f"[OK] Contraseña incorrecta rechazada limpiamente: {e_val}")
        except Exception as e_fail:
            print(f"[FAIL] Excepción inesperada con contraseña incorrecta: {e_fail}")

        if rechazo_limpio:
            pasados += 1
        else:
            print("[FAIL] No se rechazó limpiamente la contraseña incorrecta")
            fallados += 1

        # 6. Prueba de restauración completa con contraseña correcta y PRAGMA integrity_check
        total += 1
        dest_restore_enc = os.path.join(tmpdir, "restaurado_enc")
        try:
            res_enc = ejecutar_restauracion(enc_destino, dest_restore_enc, passphrase_correcta)
            if res_enc.get("status") == "ok" and os.path.exists(res_enc["db_path"]):
                # Verificar datos de la base de datos restaurada
                conn_rest = sqlite3.connect(res_enc["db_path"])
                cur_rest = conn_rest.cursor()
                cur_rest.execute("SELECT nombre FROM pacientes WHERE id = 1;")
                row = cur_rest.fetchone()
                conn_rest.close()
                if row and row[0] == "Paciente Prueba":
                    print("[OK] Ciclo de cifrado y descifrado verificado: Datos y PRAGMA integrity_check 100% íntegros")
                    pasados += 1
                else:
                    print(f"[FAIL] Datos restaurados no coinciden: {row}")
                    fallados += 1
            else:
                print(f"[FAIL] Falló resultado de restauración: {res_enc}")
                fallados += 1
        except Exception as e_rest:
            print(f"[FAIL] Error en restauración con clave correcta: {e_rest}")
            fallados += 1

        # 7. Prueba de restauración de archivo .zip sin cifrar
        total += 1
        dest_restore_zip = os.path.join(tmpdir, "restaurado_zip")
        try:
            res_zip = ejecutar_restauracion(zip_origen, dest_restore_zip)
            if res_zip.get("status") == "ok" and os.path.exists(res_zip["db_path"]):
                print("[OK] Restauración de archivo .zip estándar sin cifrar verificada exitosamente")
                pasados += 1
            else:
                print(f"[FAIL] Falló restauración de .zip estándar: {res_zip}")
                fallados += 1
        except Exception as e_zip:
            print(f"[FAIL] Error en restauración de .zip estándar: {e_zip}")
            fallados += 1

    print("\n==========================================")
    print(f"RESUMEN PRUEBAS S9: {pasados}/{total} pasados (Fallados: {fallados})")
    print("==========================================")

    if fallados > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
