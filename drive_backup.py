"""
Respaldo automatico de BIMO en Google Drive.

- Snapshot CONSISTENTE de bimo.db con la API de backup de SQLite (la BD esta en modo WAL:
  copiar el .db "a pelo" puede dejar fuera transacciones que aun viven en el -wal).
- Comprime bimo.db + Pacientes/ en un .zip temporal.
- Cifrado opcional (Fernet + passphrase) porque son datos de salud.
- Sube a la carpeta "Respaldo BIMO Clínico" (scope drive.file: solo ve lo que crea BIMO).
- Conserva solo los ultimos MAX_RESPALDOS y omite el respaldo si no hubo cambios.
- Nunca lanza excepciones hacia la UI.
"""
import base64
import datetime
import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import time
import zipfile

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from config import DATA_DIR, RUTA_DB, RUTA_PACIENTES

SCOPE_DRIVE = "https://www.googleapis.com/auth/drive.file"
NOMBRE_CARPETA = "Respaldo BIMO Clínico"
MAX_RESPALDOS = 7
INTERVALO_MIN_SEGUNDOS = 30 * 60          # no subir mas de 1 vez cada 30 min salvo forzar=True
_ESTADO = os.path.join(str(DATA_DIR), "drive_backup_state.json")
_lock = threading.Lock()                   # evita dos respaldos simultaneos (login + cierre)


def _log(msg):
    print(f"[DRIVE BACKUP] {msg}")


# ------------------------------------------------------------------ estado / cambios
def _leer_estado():
    try:
        with open(_ESTADO, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _guardar_estado(**kw):
    est = _leer_estado()
    est.update(kw)
    try:
        with open(_ESTADO, "w", encoding="utf-8") as f:
            json.dump(est, f)
    except Exception:
        pass


def _ultima_modificacion():
    """mtime maximo entre la BD (+wal) y todo Pacientes/."""
    mt = 0.0
    for p in (str(RUTA_DB), str(RUTA_DB) + "-wal"):
        if os.path.exists(p):
            mt = max(mt, os.path.getmtime(p))
    for raiz, _, archivos in os.walk(str(RUTA_PACIENTES)):
        for a in archivos:
            try:
                mt = max(mt, os.path.getmtime(os.path.join(raiz, a)))
            except OSError:
                pass
    return mt


# ------------------------------------------------------------------ zip
def _snapshot_db(destino):
    src = sqlite3.connect(str(RUTA_DB), timeout=30)
    try:
        dst = sqlite3.connect(destino)
        try:
            src.backup(dst)               # copia transaccionalmente consistente
        finally:
            dst.close()
    finally:
        src.close()


def _crear_zip(ruta_zip, tmpdir):
    db_snap = os.path.join(tmpdir, "bimo.db")
    _snapshot_db(db_snap)
    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.write(db_snap, "bimo.db")
        base = str(RUTA_PACIENTES)
        if os.path.isdir(base):
            for raiz, _, archivos in os.walk(base):
                for a in archivos:
                    full = os.path.join(raiz, a)
                    rel = os.path.relpath(full, os.path.dirname(base))   # -> Pacientes/...
                    try:
                        z.write(full, rel)
                    except OSError as e:                                  # PDF abierto/bloqueado
                        _log(f"omitido {rel}: {e}")


def _cifrar(ruta_in, ruta_out, passphrase):
    from cryptography.fernet import Fernet
    salt = os.urandom(16)
    key = base64.urlsafe_b64encode(hashlib.pbkdf2_hmac("sha256", passphrase.encode(), salt, 200_000))
    with open(ruta_in, "rb") as f:
        token = Fernet(key).encrypt(f.read())     # lee todo a RAM: ok para respaldos de cientos de MB
    with open(ruta_out, "wb") as f:
        f.write(b"BIMOENC1" + salt + token)


# ------------------------------------------------------------------ drive
def _carpeta_id(svc):
    q = ("mimeType='application/vnd.google-apps.folder' and trashed=false "
         f"and name='{NOMBRE_CARPETA}'")
    r = svc.files().list(q=q, spaces="drive", fields="files(id,name)", pageSize=1).execute()
    if r.get("files"):
        return r["files"][0]["id"]
    meta = {"name": NOMBRE_CARPETA, "mimeType": "application/vnd.google-apps.folder"}
    return svc.files().create(body=meta, fields="id").execute()["id"]


def _subir(svc, carpeta, ruta, nombre):
    media = MediaFileUpload(ruta, mimetype="application/octet-stream", resumable=True,
                            chunksize=5 * 1024 * 1024)
    req = svc.files().create(body={"name": nombre, "parents": [carpeta]}, media_body=media,
                             fields="id,name")
    resp = None
    reintentos = 0
    while resp is None:
        try:
            _, resp = req.next_chunk()
        except HttpError as e:
            if e.resp.status in (500, 502, 503, 504) and reintentos < 5:
                reintentos += 1
                time.sleep(2 ** reintentos)
                continue
            raise
    return resp


def _rotar(svc, carpeta):
    r = svc.files().list(q=f"'{carpeta}' in parents and trashed=false",
                         orderBy="createdTime desc", pageSize=100,
                         fields="files(id,name)").execute()
    for viejo in r.get("files", [])[MAX_RESPALDOS:]:
        try:
            svc.files().delete(fileId=viejo["id"]).execute()
        except Exception as e:
            _log(f"no se pudo borrar respaldo antiguo {viejo['name']}: {e}")


# ------------------------------------------------------------------ nucleo
def _ejecutar_respaldo(credenciales, forzar, passphrase):
    if not _lock.acquire(blocking=False):
        _log("ya hay un respaldo en curso; se omite.")
        return False
    try:
        if not credenciales:
            _log("sin credenciales de Google; respaldo omitido.")
            return False

        est = _leer_estado()
        ultimo_ok = est.get("ultimo_ok_ts", 0)
        if not forzar:
            if time.time() - ultimo_ok < INTERVALO_MIN_SEGUNDOS:
                return False
            if _ultima_modificacion() <= ultimo_ok:
                _log("sin cambios desde el ultimo respaldo; omitido.")
                return False

        inicio = time.time()
        with tempfile.TemporaryDirectory(prefix="bimo_bkp_") as tmp:
            sello = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
            ruta_zip = os.path.join(tmp, f"BIMO_respaldo_{sello}.zip")
            _crear_zip(ruta_zip, tmp)

            ruta_final, nombre = ruta_zip, os.path.basename(ruta_zip)
            if passphrase:
                ruta_final = ruta_zip + ".enc"
                _cifrar(ruta_zip, ruta_final, passphrase)
                nombre += ".enc"

            # servicio propio del hilo (httplib2 no es thread-safe: no reusar el de Calendar)
            svc = build("drive", "v3", credentials=credenciales, cache_discovery=False)
            carpeta = _carpeta_id(svc)
            _subir(svc, carpeta, ruta_final, nombre)
            _rotar(svc, carpeta)

        _guardar_estado(ultimo_ok_ts=inicio, ultimo_error=None)
        _log(f"respaldo subido en {time.time() - inicio:.1f}s -> {NOMBRE_CARPETA}/{nombre}")
        return True
    except HttpError as e:
        detalle = str(e)
        if "accessNotConfigured" in detalle or "has not been used" in detalle:
            detalle = "Activa la 'Google Drive API' en tu proyecto de Google Cloud. " + detalle
        _guardar_estado(ultimo_error=detalle[:300])
        _log(f"error de Drive: {detalle}")
    except Exception as e:
        _guardar_estado(ultimo_error=str(e)[:300])
        _log(f"error: {e}")
    finally:
        try:
            _lock.release()
        except RuntimeError:
            pass
    return False


def respaldar_en_drive(credenciales, forzar=False, passphrase=None, daemon=True):
    """
    Lanza el respaldo en un hilo secundario y devuelve el Thread.
    - daemon=True  : para inicio de sesion (la app sigue viva).
    - daemon=False : para el cierre; el llamador hace .join(timeout) para no perder la subida.
    """
    t = threading.Thread(target=_ejecutar_respaldo, args=(credenciales, forzar, passphrase),
                         name="bimo-drive-backup", daemon=daemon)
    t.start()
    return t
