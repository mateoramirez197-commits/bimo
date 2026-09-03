import os
import hashlib
import hmac
from database import get_connection

def hash_password(password: str) -> str:
    """
    Genera un hash criptográfico seguro usando PBKDF2-HMAC-SHA256 con sal única.
    Formato almacenado: 'salt_hex$hash_hex'
    """
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{salt.hex()}${key.hex()}"

def verify_password(stored_password_hash: str, provided_password: str) -> bool:
    """
    Verifica una contraseña contra su hash usando comparación de tiempo constante.
    """
    try:
        salt_hex, hash_hex = stored_password_hash.split("$")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(hash_hex)
        key = hashlib.pbkdf2_hmac("sha256", provided_password.encode("utf-8"), salt, 100_000)
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False

def registrar_usuario(nombre: str, email: str, password: str, rol: str = "medico"):
    pwd_hash = hash_password(password)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO usuarios (nombre, email, password_hash, rol, activo)
            VALUES (?, ?, ?, ?, 1)
        """, (nombre.strip(), email.strip().lower(), pwd_hash, rol))
        conn.commit()
        return cursor.lastrowid

def autenticar_usuario(email: str, password: str):
    """
    Autentica credenciales y retorna el dict del usuario si es válido, o None.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE email = ? AND activo = 1", (email.strip().lower(),))
        row = cursor.fetchone()
        if not row:
            return None
        
        user = dict(row)
        if verify_password(user["password_hash"], password):
            del user["password_hash"]
            return user
        return None

def inicializar_usuarios_default():
    """
    Crea los usuarios predeterminados de prueba comercial si no existen.
    - Dr. Mateo (Médico): admin@bimo.local / admin123
    - Asistente Clínica (Asistente): asistente@bimo.local / asistente123
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM usuarios;")
        count = cursor.fetchone()["total"]
        if count == 0:
            registrar_usuario("Dr. Mateo", "admin@bimo.local", "admin123", "medico")
            registrar_usuario("Asistente Clínica", "asistente@bimo.local", "asistente123", "asistente")
            print("[AUTH] Usuarios predeterminados creados: admin@bimo.local (Médico), asistente@bimo.local (Asistente)")

# Variable de sesión activa en memoria
_SESION_ACTUAL = None

def set_sesion_activa(usuario_dict):
    global _SESION_ACTUAL
    _SESION_ACTUAL = usuario_dict

def get_sesion_activa():
    global _SESION_ACTUAL
    return _SESION_ACTUAL

def cerrar_sesion():
    global _SESION_ACTUAL
    _SESION_ACTUAL = None
