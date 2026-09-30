# -*- coding: utf-8 -*-
"""
Auditor de Seguridad y Puerta de Enlace del Payload (verificar_payload.py)
Verifica que el archivo zip del instalador (bimo_payload.zip) no contenga
ningún dato clínico, base de datos, credenciales, certificados ni secretos.
Falla con código de salida 1 si encuentra algún archivo de la lista negra.
"""
import os
import sys
import fnmatch
import hashlib
import zipfile

# Lista negra de patrones de nombres y rutas prohibidas
PATRONES_PROHIBIDOS = [
    "*.db",
    "*.db-wal",
    "*.db-shm",
    "bimo.vault*",
    "bimo.lic*",
    "token.json",
    ".env",
    "*.pem",
    "*.bak*",
    "*.log",
    "drive_backup_state.json",
]

PREFIJOS_PROHIBIDOS = [
    "Pacientes/",
    "Pacientes\\",
    "Respaldos_Locales/",
    "Respaldos_Locales\\",
    "_respaldos_bimo/",
    "_respaldos_bimo\\",
    "data/",
    "data\\",
    "evidencias/",
    "evidencias\\",
    "scratch/",
    "scratch\\",
    ".git/",
    ".git\\",
]

def calcular_sha256(archivo_path):
    sha = hashlib.sha256()
    with open(archivo_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()

def es_archivo_prohibido(nombre_en_zip):
    norm = nombre_en_zip.replace("/", "\\")
    base = os.path.basename(norm).lower()

    # clinica.json está estrictamente prohibido (solo se admite clinica.default.json)
    if base == "clinica.json":
        return True, "Archivo clinica.json real prohibido (use clinica.default.json)"

    # Verificar patrones de archivo
    for pat in PATRONES_PROHIBIDOS:
        if fnmatch.fnmatch(base, pat.lower()):
            if base == "cacert.pem" and "certifi" in norm.lower():
                continue
            return True, f"Coincide con patrón prohibido '{pat}'"

    # Verificar carpetas protegidas
    for pref in PREFIJOS_PROHIBIDOS:
        pref_norm = pref.replace("/", "\\").lower()
        if norm.lower().startswith(pref_norm) and not norm.endswith("\\") and not norm.endswith("/"):
            return True, f"Contenido clínico/desarrollo dentro de carpeta prohibida '{pref}'"

    return False, ""

def verificar_zip_payload(zip_path):
    if not os.path.exists(zip_path):
        return False, [(zip_path, f"El archivo zip no existe: {zip_path}")], {}

    violaciones = []
    total_archivos = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        nombres = zf.namelist()
        total_archivos = len(nombres)
        for nombre in nombres:
            prohibido, razon = es_archivo_prohibido(nombre)
            if prohibido:
                violaciones.append((nombre, razon))

    sha = calcular_sha256(zip_path)
    tamano_bytes = os.path.getsize(zip_path)
    stats = {
        "total_archivos": total_archivos,
        "tamano_bytes": tamano_bytes,
        "tamano_mb": tamano_bytes / (1024 * 1024),
        "sha256": sha,
    }

    if violaciones:
        return False, violaciones, stats
    return True, [], stats

def main():
    print("=" * 65)
    print("      AUDITORIA DE SEGURIDAD DEL PAYLOAD (VERIFICAR_PAYLOAD)")
    print("=" * 65)

    if len(sys.argv) > 1:
        zip_path = sys.argv[1]
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        zip_path = os.path.join(base_dir, "dist", "bimo_payload.zip")

    print(f"Examinando paquete: {zip_path}\n")
    es_valido, violaciones, stats = verificar_zip_payload(zip_path)

    if not es_valido:
        print("[FALLA CRITICA DE AUDITORIA] Se detectaron archivos prohibidos:")
        for archivo, razon in violaciones:
            print(f"  [X] {archivo} -> {razon}")
        print("\nEl proceso de empaquetado SE DETIENE por seguridad del paciente.")
        sys.exit(1)

    print("[VERIFICADO] Auditoría del payload 100% LIMPIA (0 archivos prohibidos).")
    print(f"  - Total archivos: {stats.get('total_archivos')}")
    print(f"  - Tamaño: {stats.get('tamano_mb', 0):.2f} MB ({stats.get('tamano_bytes')} bytes)")
    print(f"  - SHA-256: {stats.get('sha256')}")
    print("=" * 65)
    sys.exit(0)

if __name__ == "__main__":
    main()
