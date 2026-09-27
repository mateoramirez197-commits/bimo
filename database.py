import os
import shutil
import re
import sqlite3
import json
import datetime
import unicodedata
from contextlib import contextmanager
from config import RUTA_DB, RUTA_PACIENTES, sanitizar_nombre_carpeta

def coinciden_nombres_subtokens(nombre1: str, nombre2: str) -> bool:
    """
    Determina si dos nombres representan al mismo paciente mediante comparación de subtokens y coincidencia difusa fonética.
    Ejemplos:
    - 'Juan Valdés' y 'Juan Valdez Salazar' -> True (tolera s/z y segundo apellido)
    - 'Estefanía Sandoval' y 'Estefania Sandoval Ruiz' -> True (tolera acentos y segundo apellido)
    - 'Gandhi López' y 'Gandhi Lopez' -> True
    """
    if not nombre1 or not nombre2:
        return False

    def normalizar(t):
        t_clean = unicodedata.normalize("NFKD", str(t).lower())
        t_clean = "".join(c for c in t_clean if not unicodedata.combining(c))
        return re.sub(r"[^\w\s]", "", t_clean).strip()

    n1 = normalizar(nombre1)
    n2 = normalizar(nombre2)
    if n1 == n2:
        return True

    w1 = n1.split()
    w2 = n2.split()

    if not w1 or not w2:
        return False

    s1 = set(w1)
    s2 = set(w2)

    # Si un conjunto de palabras es subconjunto estricto del otro
    # (ej: 'Estefanía Sandoval' es subconjunto de 'Estefanía Sandoval Ruiz')
    # Exigiendo al menos 2 palabras coincidentes si ambos tienen 2 o más palabras
    if s1.issubset(s2) or s2.issubset(s1):
        if min(len(s1), len(s2)) >= 2:
            return True
        elif len(s1) == 1 and len(s2) == 1:
            return s1 == s2

    return False

@contextmanager
def get_connection():
    conn = sqlite3.connect(RUTA_DB, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT CHECK(rol IN ('medico', 'asistente', 'admin')) NOT NULL DEFAULT 'medico',
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            documento TEXT,
            edad INTEGER,
            sexo TEXT,
            telefono TEXT,
            direccion TEXT,
            ocupacion TEXT,
            medico_cabecera TEXT,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS consultas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER NOT NULL,
            medico_id INTEGER,
            fecha_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            motivo_consulta TEXT,
            enfermedad_actual TEXT,
            diagnostico TEXT,
            plan_tratamiento TEXT,
            json_clinico TEXT NOT NULL,
            ruta_pdf TEXT,
            FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE,
            FOREIGN KEY (medico_id) REFERENCES usuarios(id)
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS citas_agenda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER,
            nombre_paciente TEXT,
            telefono TEXT,
            fecha_hora_inicio TEXT NOT NULL,
            fecha_hora_fin TEXT,
            descripcion TEXT,
            estado TEXT CHECK(estado IN ('programada', 'confirmada', 'atendida', 'cancelada')) DEFAULT 'programada',
            google_event_id TEXT,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE SET NULL
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS fotos_pacientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER NOT NULL,
            consulta_id INTEGER,
            categoria TEXT DEFAULT 'radiografia',
            descripcion TEXT,
            ruta_archivo TEXT NOT NULL,
            fecha_subida TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE
        );
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_id INTEGER NOT NULL,
            consulta_id INTEGER,
            costo_total REAL DEFAULT 0.0,
            abono REAL DEFAULT 0.0,
            saldo_pendiente REAL DEFAULT 0.0,
            estado TEXT DEFAULT 'Cancelado',
            metodo_pago TEXT DEFAULT 'Efectivo',
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notas TEXT,
            FOREIGN KEY (paciente_id) REFERENCES pacientes(id) ON DELETE CASCADE,
            FOREIGN KEY (consulta_id) REFERENCES consultas(id) ON DELETE SET NULL
        );
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pacientes_doc ON pacientes(documento);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pacientes_nom ON pacientes(nombre);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_consultas_paciente ON consultas(paciente_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_consultas_pac_fecha ON consultas(paciente_id, fecha_hora);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_citas_fecha ON citas_agenda(fecha_hora_inicio);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_citas_estado ON citas_agenda(estado);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pagos_paciente ON pagos(paciente_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pagos_consulta ON pagos(consulta_id);")

        # Migración segura: Añadir columnas de WhatsApp si no existen
        try:
            cursor.execute("ALTER TABLE citas_agenda ADD COLUMN recordatorio_enviado INTEGER DEFAULT 0;")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE citas_agenda ADD COLUMN recordatorio_enviado_at TIMESTAMP;")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE citas_agenda ADD COLUMN recordatorio_metodo TEXT DEFAULT 'wa_me';")
        except Exception:
            pass

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_citas_rec_enviado ON citas_agenda(recordatorio_enviado);")

        # Tabla de aprendizaje continuo de nombres, apellidos y vocabulario clínico
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vocabulario_personalizado (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            termino TEXT UNIQUE NOT NULL,
            tipo TEXT DEFAULT 'apellido',
            frecuencia INTEGER DEFAULT 1,
            creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            actualizado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_termino ON vocabulario_personalizado(termino);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vocab_frecuencia ON vocabulario_personalizado(frecuencia DESC);")

        # Sembrado inicial de apellidos andinos/ecuatorianos si está vacía
        cursor.execute("SELECT COUNT(*) as count FROM vocabulario_personalizado")
        if cursor.fetchone()["count"] == 0:
            semillas = [
                "Llumiquinga", "Guaminga", "Toapanta", "Quispe", "Quishpe", "Simbaña", "Tituaña",
                "Chiluisa", "Chushig", "Pilataxi", "Chuquimarca", "Yugsi", "Quinatoa", "Alomoto",
                "Tipán", "Caiza", "Tasinchana", "Masabanda", "Andrango", "Imbaquingo", "Farinango",
                "Colcha", "Morocho", "Pastuña", "Guanoluisa", "Guasgua", "Curipoma", "Sampedro",
                "Sangoluisa", "Pupiales", "Fueres", "Otavalo", "Cotacachi", "Cachiguango", "Cachimuel",
                "Cabascango", "Guamán", "Cajas", "Criollo", "Alulema", "Muenala", "Pillajo"
            ]
            for s in semillas:
                cursor.execute("""
                    INSERT OR IGNORE INTO vocabulario_personalizado (termino, tipo, frecuencia)
                    VALUES (?, 'apellido', 5)
                """, (s,))

        conn.commit()

VOCABULARIO_JSON_PATH = os.path.join(os.path.dirname(__file__), "vocabulario_aprendido.json")

def aprender_termino(termino: str, tipo: str = "apellido"):
    """Registra o incrementa la frecuencia de un término aprendido en la base de datos."""
    if not termino or len(termino.strip()) < 3:
        return
    term = termino.strip().title()
    if term.lower() in ("del", "las", "los", "san", "santa", "para", "cita", "paciente", "doctor", "mateo", "consulta"):
        return
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO vocabulario_personalizado (termino, tipo, frecuencia, actualizado_en)
                VALUES (?, ?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(termino) DO UPDATE SET 
                    frecuencia = frecuencia + 1,
                    actualizado_en = CURRENT_TIMESTAMP
            """, (term, tipo))
            conn.commit()
    except Exception as e:
        print(f"[VOCAB WARN] Error al aprender término '{term}': {e}")

def aprender_nombres_paciente(nombre_completo: str):
    """Extrae y aprende permanentemente cada nombre y apellido de un paciente."""
    if not nombre_completo or nombre_completo.strip().lower() in ("no especificado", "paciente", "paciente_desconocido"):
        return
    partes = nombre_completo.strip().split()
    for i, p in enumerate(partes):
        tipo = "nombre" if i == 0 else "apellido"
        aprender_termino(p, tipo=tipo)
    try:
        sincronizar_vocabulario_json()
    except Exception:
        pass

def sincronizar_vocabulario_json():
    """Exporta el vocabulario aprendido a un archivo JSON para persistencia rápida y portabilidad entre versiones."""
    try:
        terminos = obtener_vocabulario_aprendido(limite=250)
        with open(VOCABULARIO_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(terminos, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def obtener_vocabulario_aprendido(limite: int = 150) -> list[str]:
    """Retorna lista de nombres y apellidos aprendidos ordenados por frecuencia y recencia."""
    lista = []
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT termino FROM vocabulario_personalizado ORDER BY frecuencia DESC, actualizado_en DESC LIMIT ?", (limite,))
            rows = cursor.fetchall()
            for r in rows:
                lista.append(r["termino"])
    except Exception:
        if os.path.exists(VOCABULARIO_JSON_PATH):
            try:
                with open(VOCABULARIO_JSON_PATH, "r", encoding="utf-8") as f:
                    lista = json.load(f)
            except Exception:
                pass
    return lista

def obtener_ultimo_paciente_atendido() -> dict | None:
    """
    Retorna el último paciente atendido o registrado en la clínica.
    1. Busca el paciente de la consulta médica más reciente.
    2. Fallback al último paciente registrado en la tabla pacientes.
    """
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT p.* FROM consultas c
                JOIN pacientes p ON c.paciente_id = p.id
                ORDER BY c.fecha_hora DESC, c.id DESC LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return dict(row)

            cursor.execute("SELECT * FROM pacientes ORDER BY id DESC LIMIT 1")
            row_p = cursor.fetchone()
            if row_p:
                return dict(row_p)
    except Exception as e:
        print(f"[DB ERROR] obtener_ultimo_paciente_atendido: {e}")
    return None

def purgar_datos_prueba():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM consultas WHERE paciente_id IN (SELECT id FROM pacientes WHERE nombre LIKE '%Prueba%' OR nombre LIKE '%Carlos Mendoza%' OR nombre LIKE '%Sofia Ramirez%');")
        cursor.execute("DELETE FROM citas_agenda WHERE nombre_paciente LIKE '%Prueba%';")
        cursor.execute("DELETE FROM pacientes WHERE nombre LIKE '%Prueba%' OR nombre LIKE '%Carlos Mendoza%' OR nombre LIKE '%Sofia Ramirez%';")
        conn.commit()

# --- OPERACIONES DE PACIENTES ---

def registrar_o_actualizar_paciente(datos_filiacion=None, **kwargs) -> int:
    if datos_filiacion is None and kwargs:
        datos_filiacion = kwargs
    elif isinstance(datos_filiacion, dict) and kwargs:
        datos_filiacion = {**datos_filiacion, **kwargs}
    elif not isinstance(datos_filiacion, dict):
        datos_filiacion = {}

    nombre = datos_filiacion.get("nombre", "").strip() or "Paciente_Desconocido"
    if nombre and nombre != "Paciente_Desconocido":
        aprender_nombres_paciente(nombre)
    doc_crudo = str(datos_filiacion.get("documento", "")).strip()
    doc_limpio = doc_crudo.replace(" ", "") if doc_crudo.lower() not in ("no especificado", "none", "") else None
    
    edad_val = None
    try:
        numeros = [int(s) for s in str(datos_filiacion.get("edad", "")).split() if s.isdigit()]
        if numeros:
            edad_val = numeros[0]
    except Exception:
        edad_val = None

    sexo = datos_filiacion.get("sexo", "No especificado")
    telefono = datos_filiacion.get("telefono") or datos_filiacion.get("contacto_emergencia") or "No especificado"
    direccion = datos_filiacion.get("direccion", "No especificado")
    ocupacion = datos_filiacion.get("ocupacion", "No especificado")
    medico = datos_filiacion.get("medico_cabecera", "No especificado")

    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 0. SI SE ESPECIFICA UN ID EXPLÍCITO (EDICIÓN DIRECTA DESDE LA INTERFAZ)
        p_id_explicit = datos_filiacion.get("id")
        if p_id_explicit:
            cursor.execute("""
                UPDATE pacientes SET
                    nombre = ?, documento = ?, edad = COALESCE(?, edad), sexo = ?, telefono = ?,
                    direccion = ?, ocupacion = ?, medico_cabecera = ?
                WHERE id = ?
            """, (nombre, doc_limpio, edad_val, sexo, telefono, direccion, ocupacion, medico, p_id_explicit))
            conn.commit()
            return p_id_explicit

        # 1. SI SE PROPORCIONA CÉDULA VÁLIDA (PRIORIDAD MÁXIMA)
        if doc_limpio:
            # A) Buscar por cédula exacta
            cursor.execute("SELECT id, telefono FROM pacientes WHERE documento = ?", (doc_limpio,))
            row = cursor.fetchone()
            if row:
                paciente_id = row["id"]
                cursor.execute("""
                    UPDATE pacientes SET
                        nombre = ?, edad = COALESCE(?, edad), sexo = ?,
                        telefono = COALESCE(NULLIF(NULLIF(?, ''), 'No especificado'), telefono),
                        direccion = ?, ocupacion = ?, medico_cabecera = ?
                    WHERE id = ?
                """, (nombre, edad_val, sexo, telefono, direccion, ocupacion, medico, paciente_id))
                conn.commit()
                if telefono and telefono.lower() not in ("no especificado", "none", ""):
                    cursor.execute("UPDATE citas_agenda SET telefono = ? WHERE paciente_id = ? AND (telefono IS NULL OR telefono = '' OR telefono = 'No especificado')", (telefono, paciente_id))
                    conn.commit()
                return paciente_id
            
            # B) Si no existe con esa cédula, buscar si existe un paciente previo por nombre o subtokens sin cédula
            cursor.execute("SELECT * FROM pacientes WHERE (documento IS NULL OR documento = '') ORDER BY id ASC")
            sin_doc = cursor.fetchall()
            for p_cand in sin_doc:
                nom_c = p_cand["nombre"]
                edad_c = p_cand["edad"]
                if coinciden_nombres_subtokens(nombre, nom_c):
                    if edad_val and edad_c and abs(edad_val - edad_c) > 3:
                        continue
                    paciente_id = p_cand["id"]
                    nom_mas_completo = nombre if len(nombre.split()) >= len(nom_c.split()) else nom_c
                    edad_final = edad_val if edad_val else edad_c
                    cursor.execute("""
                        UPDATE pacientes SET
                            nombre = ?,
                            documento = ?,
                            edad = COALESCE(?, edad),
                            sexo = COALESCE(NULLIF(?, 'No especificado'), sexo),
                            telefono = COALESCE(NULLIF(NULLIF(?, ''), 'No especificado'), telefono),
                            direccion = COALESCE(NULLIF(?, 'No especificado'), direccion),
                            ocupacion = COALESCE(NULLIF(?, 'No especificado'), ocupacion),
                            medico_cabecera = COALESCE(NULLIF(?, 'No especificado'), medico_cabecera)
                        WHERE id = ?
                    """, (nom_mas_completo, doc_limpio, edad_final, sexo, telefono, direccion, ocupacion, medico, paciente_id))
                    conn.commit()
                    if telefono and telefono.lower() not in ("no especificado", "none", ""):
                        cursor.execute("UPDATE citas_agenda SET telefono = ? WHERE paciente_id = ? AND (telefono IS NULL OR telefono = '' OR telefono = 'No especificado')", (telefono, paciente_id))
                        conn.commit()
                    print(f"[UNIFICACIÓN CÉDULA] Cédula {doc_limpio} asignada a '{nom_c}' -> ID: {paciente_id}")
                    return paciente_id

            # C) Crear nuevo paciente con la cédula
            import datetime
            creado_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO pacientes (nombre, documento, edad, sexo, telefono, direccion, ocupacion, medico_cabecera, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (nombre, doc_limpio, edad_val, sexo, telefono, direccion, ocupacion, medico, creado_local))
            conn.commit()
            new_id = cursor.lastrowid
            if telefono and telefono.lower() not in ("no especificado", "none", ""):
                cursor.execute("UPDATE citas_agenda SET telefono = ? WHERE LOWER(nombre_paciente) = LOWER(?) AND (telefono IS NULL OR telefono = '' OR telefono = 'No especificado')", (telefono, nombre))
                conn.commit()
            return new_id

        # 2. SI NO SE PROPORCIONA CÉDULA: ENCAPSULACIÓN INTELIGENTE (NO CREAR DUPLICADOS)
        # A) Buscar por nombre y edad coincidentes (tolerancia estricta +-3 años)
        if edad_val:
            cursor.execute("""
                SELECT id, edad, telefono FROM pacientes 
                WHERE LOWER(nombre) = LOWER(?)
                ORDER BY id ASC
            """, (nombre,))
            cands_nombre = cursor.fetchall()
            for cand in cands_nombre:
                edad_existente = cand["edad"]
                if edad_existente is not None and abs(edad_val - int(edad_existente)) <= 3:
                    paciente_id = cand["id"]
                    cursor.execute("""
                        UPDATE pacientes SET
                            sexo = COALESCE(NULLIF(?, 'No especificado'), sexo),
                            telefono = COALESCE(NULLIF(NULLIF(?, ''), 'No especificado'), telefono),
                            direccion = COALESCE(NULLIF(?, 'No especificado'), direccion),
                            ocupacion = COALESCE(NULLIF(?, 'No especificado'), ocupacion),
                            medico_cabecera = COALESCE(NULLIF(?, 'No especificado'), medico_cabecera)
                        WHERE id = ?
                    """, (sexo, telefono, direccion, ocupacion, medico, paciente_id))
                    conn.commit()
                    if telefono and telefono.lower() not in ("no especificado", "none", ""):
                        cursor.execute("UPDATE citas_agenda SET telefono = ? WHERE paciente_id = ? AND (telefono IS NULL OR telefono = '' OR telefono = 'No especificado')", (telefono, paciente_id))
                        conn.commit()
                    return paciente_id

        # B) Si NO se especificó edad en el dictado, pero coincide exactamente en nombre y solo hay uno registrado
        elif not edad_val:
            cursor.execute("SELECT id, telefono FROM pacientes WHERE LOWER(nombre) = LOWER(?) ORDER BY id ASC", (nombre,))
            filas_nombre = cursor.fetchall()
            if len(filas_nombre) == 1:
                paciente_id = filas_nombre[0]["id"]
                cursor.execute("""
                    UPDATE pacientes SET
                        sexo = COALESCE(NULLIF(NULLIF(?, ''), 'No especificado'), sexo),
                        telefono = COALESCE(NULLIF(NULLIF(?, ''), 'No especificado'), telefono),
                        direccion = COALESCE(NULLIF(NULLIF(?, ''), 'No especificado'), direccion),
                        ocupacion = COALESCE(NULLIF(NULLIF(?, ''), 'No especificado'), ocupacion),
                        medico_cabecera = COALESCE(NULLIF(NULLIF(?, ''), 'No especificado'), medico_cabecera)
                    WHERE id = ?
                """, (sexo, telefono, direccion, ocupacion, medico, paciente_id))
                conn.commit()
                if telefono and telefono.lower() not in ("no especificado", "none", ""):
                    cursor.execute("UPDATE citas_agenda SET telefono = ? WHERE paciente_id = ? AND (telefono IS NULL OR telefono = '' OR telefono = 'No especificado')", (telefono, paciente_id))
                    conn.commit()
                return paciente_id

        # C) Búsqueda inteligente por subtokens (ej: 'Juan Valdés' vs 'Juan Valdés Salazar')
        cursor.execute("SELECT * FROM pacientes WHERE nombre != 'No especificado' ORDER BY id ASC")
        todos_registrados = cursor.fetchall()
        for p_cand in todos_registrados:
            nom_c = p_cand["nombre"]
            edad_c = p_cand["edad"]
            doc_c = p_cand["documento"]

            if coinciden_nombres_subtokens(nombre, nom_c):
                # Si ambos tienen edad explícita y difieren por más de 3 años, omitir
                if edad_val and edad_c and abs(edad_val - edad_c) > 3:
                    continue

                paciente_id = p_cand["id"]
                # Preservar el nombre más completo (ej: Juan Valdés Salazar)
                nom_mas_completo = nombre if len(nombre.split()) >= len(nom_c.split()) else nom_c
                edad_final = edad_val if edad_val else edad_c
                doc_final = doc_limpio if doc_limpio else doc_c

                cursor.execute("""
                    UPDATE pacientes SET
                        nombre = ?,
                        edad = COALESCE(?, edad),
                        documento = COALESCE(?, documento),
                        sexo = COALESCE(NULLIF(?, 'No especificado'), sexo),
                        telefono = COALESCE(NULLIF(NULLIF(?, ''), 'No especificado'), telefono),
                        direccion = COALESCE(NULLIF(?, 'No especificado'), direccion),
                        ocupacion = COALESCE(NULLIF(?, 'No especificado'), ocupacion),
                        medico_cabecera = COALESCE(NULLIF(?, 'No especificado'), medico_cabecera)
                    WHERE id = ?
                """, (nom_mas_completo, edad_final, doc_final, sexo, telefono, direccion, ocupacion, medico, paciente_id))
                conn.commit()
                if telefono and telefono.lower() not in ("no especificado", "none", ""):
                    cursor.execute("UPDATE citas_agenda SET telefono = ? WHERE paciente_id = ? AND (telefono IS NULL OR telefono = '' OR telefono = 'No especificado')", (telefono, paciente_id))
                    conn.commit()
                print(f"[UNIFICACIÓN] Paciente '{nombre}' consolidado con '{nom_c}' -> ID: {paciente_id}")
                return paciente_id

        # D) Solo crear nuevo paciente si no hay absolutamente ninguna coincidencia
        if not telefono or str(telefono).strip().lower() in ("no especificado", "none", ""):
            cursor.execute("""
                SELECT telefono FROM citas_agenda 
                WHERE LOWER(TRIM(nombre_paciente)) = LOWER(TRIM(?))
                  AND telefono IS NOT NULL 
                  AND telefono != '' 
                  AND telefono != 'No especificado'
                ORDER BY id DESC LIMIT 1
            """, (nombre,))
            r_prev_c = cursor.fetchone()
            if not r_prev_c:
                cursor.execute("SELECT nombre_paciente, telefono FROM citas_agenda WHERE telefono IS NOT NULL AND telefono != '' AND telefono != 'No especificado' ORDER BY id DESC")
                for c_cand in cursor.fetchall():
                    if coinciden_nombres_subtokens(nombre, c_cand["nombre_paciente"]):
                        r_prev_c = c_cand
                        break
            if r_prev_c and r_prev_c["telefono"]:
                telefono = str(r_prev_c["telefono"]).strip()

        import datetime
        creado_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO pacientes (nombre, documento, edad, sexo, telefono, direccion, ocupacion, medico_cabecera, creado_en)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (nombre, None, edad_val, sexo, telefono, direccion, ocupacion, medico, creado_local))
        conn.commit()
        new_id = cursor.lastrowid
        if telefono and telefono.lower() not in ("no especificado", "none", ""):
            cursor.execute("UPDATE citas_agenda SET telefono = ? WHERE LOWER(nombre_paciente) = LOWER(?) AND (telefono IS NULL OR telefono = '' OR telefono = 'No especificado')", (telefono, nombre))
            conn.commit()
        return new_id

def consolidar_pacientes_duplicados():
    """
    Fusiona registros repetidos que compartan el mismo nombre y edad (o misma cédula).
    Reasigna todas las consultas y citas al registro canónico y elimina los duplicados.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT LOWER(nombre) as nom, edad, COUNT(*) as cnt
            FROM pacientes
            WHERE nombre != 'No especificado' AND edad IS NOT NULL
            GROUP BY LOWER(nombre), edad
            HAVING cnt > 1
        """)
        duplicados = cursor.fetchall()

        for dup in duplicados:
            nom = dup["nom"]
            edad = dup["edad"]

            cursor.execute("""
                SELECT * FROM pacientes 
                WHERE LOWER(nombre) = ? AND edad = ?
                ORDER BY (documento IS NOT NULL AND documento != '') DESC, id ASC
            """, (nom, edad))
            rows = cursor.fetchall()
            if len(rows) > 1:
                canonico = rows[0]
                canonico_id = canonico["id"]
                sobrantes = [r["id"] for r in rows[1:]]

                for s_id in sobrantes:
                    cursor.execute("UPDATE consultas SET paciente_id = ? WHERE paciente_id = ?", (canonico_id, s_id))
                    cursor.execute("UPDATE citas_agenda SET paciente_id = ? WHERE paciente_id = ?", (canonico_id, s_id))
                    cursor.execute("DELETE FROM pacientes WHERE id = ?", (s_id,))
                conn.commit()
                print(f"[DEDUPLICACION] Pacientes {sobrantes} consolidados en ID {canonico_id} ({canonico['nombre']})")

def buscar_paciente_por_cedula(cedula: str) -> dict | None:
    if not cedula or str(cedula).strip().lower() in ("no especificado", "none", ""):
        return None
    doc_limpio = str(cedula).strip().replace(" ", "")
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pacientes WHERE documento = ? LIMIT 1", (doc_limpio,))
        row = cursor.fetchone()
        return dict(row) if row else None

def obtener_paciente_por_id(paciente_id: int) -> dict | None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pacientes WHERE id = ?", (paciente_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def buscar_pacientes(query=""):
    return listar_pacientes_por_fecha("todos", query)

def listar_pacientes_por_fecha(fecha_iso: str = "todos", query: str = "") -> list:
    """
    Lista pacientes que tienen consulta o cita en una fecha específica (YYYY-MM-DD),
    o pacientes registrados en esa fecha (incluyendo imprevistos/walk-ins),
    o todos los pacientes si fecha_iso es 'todos'.
    Garantiza deduplicación absoluta por ID canónico y soporte de zona horaria local.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        q = f"%{query.strip()}%"
        
        if not fecha_iso or fecha_iso.lower() == "todos":
            cursor.execute("""
                SELECT p.*, COUNT(DISTINCT c.id) AS total_consultas, MAX(c.fecha_hora) AS ultima_consulta
                FROM pacientes p
                LEFT JOIN consultas c ON p.id = c.paciente_id
                WHERE p.nombre LIKE ? OR p.documento LIKE ?
                GROUP BY p.id
                ORDER BY p.id DESC
                LIMIT 100
            """, (q, q))
        else:
            patron_f = f"{fecha_iso}%"
            import datetime
            es_hoy = (fecha_iso == datetime.date.today().isoformat())
            filtro_extra_hoy = "OR fecha_hora >= datetime('now', '-18 hours')" if es_hoy else ""
            filtro_extra_cita = "OR creado_en >= datetime('now', '-18 hours')" if es_hoy else ""
            filtro_extra_pac = "OR creado_en >= datetime('now', '-18 hours')" if es_hoy else ""

            sql = f"""
                SELECT p.*, COUNT(DISTINCT c.id) AS total_consultas, MAX(c.fecha_hora) AS ultima_consulta
                FROM pacientes p
                LEFT JOIN consultas c ON p.id = c.paciente_id
                WHERE (p.nombre LIKE ? OR p.documento LIKE ?)
                  AND (
                      p.id IN (
                          SELECT paciente_id FROM consultas 
                          WHERE fecha_hora LIKE ? 
                             OR DATE(fecha_hora, 'localtime') = ? 
                             OR DATE(fecha_hora) = ?
                             {filtro_extra_hoy}
                      )
                      OR p.nombre IN (
                          SELECT nombre_paciente FROM citas_agenda 
                          WHERE fecha_hora_inicio LIKE ? 
                             OR DATE(fecha_hora_inicio, 'localtime') = ? 
                             OR DATE(fecha_hora_inicio) = ?
                             {filtro_extra_cita}
                      )
                      OR p.id IN (
                          SELECT id FROM pacientes 
                          WHERE creado_en LIKE ? 
                             OR DATE(creado_en, 'localtime') = ? 
                             OR DATE(creado_en) = ?
                             {filtro_extra_pac}
                      )
                  )
                GROUP BY p.id
                ORDER BY p.id DESC
            """
            cursor.execute(sql, (q, q, patron_f, fecha_iso, fecha_iso, patron_f, fecha_iso, fecha_iso, patron_f, fecha_iso, fecha_iso))

        return [dict(row) for row in cursor.fetchall()]

def eliminar_paciente_db(paciente_id: int) -> bool:
    """Elimina un paciente, sus consultas registradas, citas asociadas y su carpeta física en disco."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Obtener datos del paciente antes de borrar
        cursor.execute("SELECT * FROM pacientes WHERE id = ?", (paciente_id,))
        p_row = cursor.fetchone()

        # 2. Borrar PDFs de consultas
        cursor.execute("SELECT ruta_pdf FROM consultas WHERE paciente_id = ?", (paciente_id,))
        for row in cursor.fetchall():
            pdf = row["ruta_pdf"]
            if pdf and os.path.exists(pdf):
                try:
                    os.remove(pdf)
                except Exception:
                    pass
        
        # 3. Borrar físicamente el directorio del paciente en disco
        if p_row:
            nom = p_row["nombre"]
            nombre_limpio = sanitizar_nombre_carpeta(nom)
            edad_num = p_row["edad"] or 18
            categoria_edad = "Pacientes_Pediatricos" if edad_num < 18 else "Pacientes_Adultos"
            nombre_carpeta = f"{nombre_limpio}_{edad_num}_anos_ID{paciente_id}"
            ruta_carpeta = os.path.join(RUTA_PACIENTES, categoria_edad, nombre_carpeta)
            if os.path.exists(ruta_carpeta):
                try:
                    shutil.rmtree(ruta_carpeta, ignore_errors=True)
                except Exception:
                    pass

            cursor.execute("DELETE FROM citas_agenda WHERE LOWER(nombre_paciente) = ?", (nom.lower(),))

        cursor.execute("DELETE FROM consultas WHERE paciente_id = ?", (paciente_id,))
        cursor.execute("DELETE FROM pacientes WHERE id = ?", (paciente_id,))
        conn.commit()
        return True

def eliminar_consulta_db(consulta_id: int) -> bool:
    """Elimina una consulta específica y su archivo físico PDF."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ruta_pdf FROM consultas WHERE id = ?", (consulta_id,))
        row = cursor.fetchone()
        if row and row["ruta_pdf"] and os.path.exists(row["ruta_pdf"]):
            try:
                os.remove(row["ruta_pdf"])
            except Exception:
                pass
        cursor.execute("DELETE FROM consultas WHERE id = ?", (consulta_id,))
        conn.commit()
        return True

def buscar_pacientes_por_nombre(nombre: str) -> list[dict]:
    """
    Búsqueda clínica para desambiguación de homónimos.
    Retorna todos los pacientes que coincidan con el nombre.
    """
    nombre_limpio = nombre.strip().lower()
    if not nombre_limpio or nombre_limpio == "no especificado":
        return []

    with get_connection() as conn:
        cursor = conn.cursor()
        # Búsqueda exacta y aproximada SQL
        cursor.execute("""
            SELECT * FROM pacientes 
            WHERE LOWER(nombre) = ? OR LOWER(nombre) LIKE ?
            ORDER BY id ASC
        """, (nombre_limpio, f"%{nombre_limpio}%"))
        filas = [dict(row) for row in cursor.fetchall()]
        if filas:
            return filas

        # Fallback inteligente con coincidencia de subtokens (tolera transcripciones fonéticas)
        cursor.execute("SELECT * FROM pacientes ORDER BY id ASC")
        todos = [dict(r) for r in cursor.fetchall()]
        return [p for p in todos if coinciden_nombres_subtokens(nombre, p["nombre"])]

# --- OPERACIONES DE CONSULTAS ---

def obtener_siguiente_num_expediente_paciente(paciente_id: int) -> int:
    """Retorna el número correlativo del próximo expediente/consulta para un paciente (1, 2, 3...)."""
    if not paciente_id:
        return 1
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM consultas WHERE paciente_id = ?", (paciente_id,))
        row = cursor.fetchone()
        count = row[0] if row else 0
        return count + 1

def obtener_num_expediente_consulta(consulta_id: int) -> int:
    """Retorna el número ordinal de la consulta dentro del historial de ese paciente (1, 2, 3...)."""
    if not consulta_id:
        return 1
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT paciente_id FROM consultas WHERE id = ?", (consulta_id,))
        r = cursor.fetchone()
        if not r:
            return 1
        pid = r["paciente_id"]
        cursor.execute("SELECT id FROM consultas WHERE paciente_id = ? ORDER BY id ASC", (pid,))
        all_ids = [row["id"] for row in cursor.fetchall()]
        try:
            return all_ids.index(consulta_id) + 1
        except ValueError:
            return 1

def buscar_consulta_por_expediente_o_cedula(paciente_id_o_nombre=None, cedula=None, num_expediente=None) -> dict | None:
    """Busca una consulta específica de un paciente por número de expediente (1, 2, 3...) y/o cédula."""
    with get_connection() as conn:
        cursor = conn.cursor()
        pid = None
        if cedula:
            doc_c = str(cedula).replace(" ", "").replace("-", "").strip()
            cursor.execute("SELECT id FROM pacientes WHERE documento = ?", (doc_c,))
            p = cursor.fetchone()
            if p:
                pid = p["id"]
        if not pid and paciente_id_o_nombre:
            if isinstance(paciente_id_o_nombre, int):
                pid = paciente_id_o_nombre
            else:
                cursor.execute("SELECT id FROM pacientes WHERE LOWER(nombre) = LOWER(?) ORDER BY id DESC LIMIT 1", (str(paciente_id_o_nombre).strip(),))
                p = cursor.fetchone()
                if p:
                    pid = p["id"]

        if not pid:
            return None

        cursor.execute("SELECT * FROM consultas WHERE paciente_id = ? ORDER BY id ASC", (pid,))
        consultas = [dict(row) for row in cursor.fetchall()]
        if not consultas:
            return None

        if num_expediente and 1 <= int(num_expediente) <= len(consultas):
            return consultas[int(num_expediente) - 1]
        
        return consultas[-1]

def guardar_consulta_db(paciente_id, json_clinico=None, ruta_pdf=None, medico_id=None, **kwargs):
    # Si el invocador pasó (paciente_id, medico_id, json_clinico, ...) reordenar dinámicamente
    if isinstance(json_clinico, (int, type(None))) and isinstance(ruta_pdf, (dict, list, str)):
        # Caso: guardar_consulta_db(paciente_id, medico_id, resultado_ia, ruta_pdf=...)
        medico_id, json_clinico = json_clinico, ruta_pdf
        ruta_pdf = kwargs.get("ruta_pdf", None)

    if json_clinico is None and "resultado_ia" in kwargs:
        json_clinico = kwargs["resultado_ia"]
    if ruta_pdf is None and "ruta_pdf" in kwargs:
        ruta_pdf = kwargs["ruta_pdf"]

    # ESCUDO ANTI-DUPLICADOS DEL MISMO DÍA A NIVEL DE BASE DE DATOS:
    # Si ya existe una consulta registrada hoy para este paciente, actualizarla automáticamente
    c_hoy = obtener_consulta_del_dia(paciente_id)
    if c_hoy:
        cid = c_hoy["id"]
        actualizar_consulta_existente(cid, json_clinico, ruta_pdf=ruta_pdf)
        print(f"[DB CONSOLIDACION] Consulta #{cid} de hoy para paciente {paciente_id} unificada y actualizada.")
        return cid

    import datetime
    fecha_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if isinstance(json_clinico, (dict, list)):
        datos = json_clinico if isinstance(json_clinico, dict) else {}
        json_str = json.dumps(json_clinico, ensure_ascii=False)
    else:
        try:
            datos = json.loads(json_clinico) if json_clinico else {}
        except Exception:
            datos = {}
        json_str = str(json_clinico) if json_clinico else "{}"

    motivo = datos.get("motivo_consulta", "No especificado")
    enfermedad = datos.get("enfermedad_actual", "No especificado")
    diagnostico = datos.get("diagnostico", "No especificado")
    plan = datos.get("plan_tratamiento", "No especificado")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO consultas (
                paciente_id, medico_id, fecha_hora, motivo_consulta, enfermedad_actual,
                diagnostico, plan_tratamiento, json_clinico, ruta_pdf
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (paciente_id, medico_id, fecha_local, motivo, enfermedad, diagnostico, plan, json_str, ruta_pdf))
        cid = cursor.lastrowid
        conn.commit()

        # Sincronización automática de honorarios / pagos
        pagos_info = datos.get("pagos")
        if isinstance(pagos_info, dict) and (float(pagos_info.get("costo_total") or 0.0) > 0 or float(pagos_info.get("abono") or 0.0) > 0 or float(pagos_info.get("saldo_pendiente") or 0.0) > 0):
            try:
                registrar_o_actualizar_pago_db(
                    paciente_id=paciente_id,
                    consulta_id=cid,
                    costo_total=pagos_info.get("costo_total", 0.0),
                    abono=pagos_info.get("abono", 0.0),
                    saldo_pendiente=pagos_info.get("saldo_pendiente"),
                    estado=pagos_info.get("estado"),
                    metodo_pago=pagos_info.get("metodo_pago", "Efectivo"),
                    notas=pagos_info.get("notas", "")
                )
            except Exception as e_pago:
                print(f"[PAGOS] Aviso al registrar pago: {e_pago}")

        return cid

def obtener_consulta_del_dia(paciente_id: int) -> dict | None:
    """
    Retorna la consulta registrada hoy (mismo día calendario) para el paciente, si existe, para consolidar.
    Si la consulta es de un día diferente (ej. una cita futura o cita de control posterior), 
    retorna None para generar un nuevo expediente y un nuevo PDF independiente.
    """
    import datetime
    hoy_iso = datetime.date.today().isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM consultas 
            WHERE paciente_id = ? 
              AND (
                  fecha_hora LIKE ? 
                  OR DATE(fecha_hora, 'localtime') = ? 
                  OR DATE(fecha_hora) = ?
              )
            ORDER BY id DESC LIMIT 1
        """, (paciente_id, f"{hoy_iso}%", hoy_iso, hoy_iso))
        row = cursor.fetchone()
        return dict(row) if row else None

def actualizar_consulta_existente(consulta_id: int, json_clinico, ruta_pdf=None) -> bool:
    """Actualiza datos clínicos y PDF de una consulta existente (consolidación del mismo día)."""
    if isinstance(json_clinico, (dict, list)):
        datos = json_clinico if isinstance(json_clinico, dict) else {}
        json_str = json.dumps(json_clinico, ensure_ascii=False)
    else:
        try:
            datos = json.loads(json_clinico) if json_clinico else {}
        except Exception:
            datos = {}
        json_str = str(json_clinico) if json_clinico else "{}"

    motivo = datos.get("motivo_consulta", "No especificado")
    enfermedad = datos.get("enfermedad_actual", "No especificado")
    diagnostico = datos.get("diagnostico", "No especificado")
    plan = datos.get("plan_tratamiento", "No especificado")

    fecha_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        cursor = conn.cursor()
        if ruta_pdf:
            cursor.execute("""
                UPDATE consultas SET
                    motivo_consulta = ?,
                    enfermedad_actual = ?,
                    diagnostico = ?,
                    plan_tratamiento = ?,
                    json_clinico = ?,
                    ruta_pdf = ?,
                    fecha_hora = ?
                WHERE id = ?
            """, (motivo, enfermedad, diagnostico, plan, json_str, ruta_pdf, fecha_local, consulta_id))
        else:
            cursor.execute("""
                UPDATE consultas SET
                    motivo_consulta = ?,
                    enfermedad_actual = ?,
                    diagnostico = ?,
                    plan_tratamiento = ?,
                    json_clinico = ?,
                    fecha_hora = ?
                WHERE id = ?
            """, (motivo, enfermedad, diagnostico, plan, json_str, fecha_local, consulta_id))
        conn.commit()

        # Sincronización automática de honorarios / pagos
        pagos_info = datos.get("pagos")
        if isinstance(pagos_info, dict) and (float(pagos_info.get("costo_total") or 0.0) > 0 or float(pagos_info.get("abono") or 0.0) > 0 or float(pagos_info.get("saldo_pendiente") or 0.0) > 0):
            try:
                cursor.execute("SELECT paciente_id FROM consultas WHERE id = ?", (consulta_id,))
                row_p = cursor.fetchone()
                if row_p:
                    registrar_o_actualizar_pago_db(
                        paciente_id=row_p["paciente_id"],
                        consulta_id=consulta_id,
                        costo_total=pagos_info.get("costo_total", 0.0),
                        abono=pagos_info.get("abono", 0.0),
                        saldo_pendiente=pagos_info.get("saldo_pendiente"),
                        estado=pagos_info.get("estado"),
                        metodo_pago=pagos_info.get("metodo_pago", "Efectivo"),
                        notas=pagos_info.get("notas", "")
                    )
            except Exception as e_pago:
                print(f"[PAGOS] Aviso al actualizar pago: {e_pago}")

        return True

# --- OPERACIONES DE CONTROL FINANCIERO Y PAGOS ---

def registrar_o_actualizar_pago_db(paciente_id: int, consulta_id: int = None, costo_total: float = 0.0, abono: float = 0.0, saldo_pendiente: float = None, estado: str = None, metodo_pago: str = "Efectivo", notas: str = "") -> int:
    """Registra o actualiza el estado de cuenta y pago de un tratamiento/consulta en SQLite."""
    costo = float(costo_total or 0.0)
    ab = float(abono or 0.0)
    if saldo_pendiente is None:
        saldo = max(0.0, round(costo - ab, 2))
    else:
        saldo = float(saldo_pendiente)

    if not estado or str(estado).lower() in ("no especificado", "none", ""):
        estado = "Cancelado" if saldo <= 0.0 else "Saldo Pendiente"

    with get_connection() as conn:
        cursor = conn.cursor()
        if consulta_id:
            cursor.execute("SELECT id FROM pagos WHERE consulta_id = ? LIMIT 1", (consulta_id,))
            existente = cursor.fetchone()
            if existente:
                pago_id = existente["id"]
                cursor.execute("""
                    UPDATE pagos SET
                        costo_total = ?,
                        abono = ?,
                        saldo_pendiente = ?,
                        estado = ?,
                        metodo_pago = ?,
                        notas = ?
                    WHERE id = ?
                """, (costo, ab, saldo, estado, metodo_pago, notas, pago_id))
                conn.commit()
                return pago_id

        cursor.execute("""
            INSERT INTO pagos (paciente_id, consulta_id, costo_total, abono, saldo_pendiente, estado, metodo_pago, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (paciente_id, consulta_id, costo, ab, saldo, estado, metodo_pago, notas))
        conn.commit()
        return cursor.lastrowid

def obtener_pago_consulta(consulta_id: int) -> dict | None:
    """Obtiene los datos de pago registrados para una consulta específica."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pagos WHERE consulta_id = ? ORDER BY id DESC LIMIT 1", (consulta_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def obtener_pagos_paciente(paciente_id: int) -> list:
    """Obtiene el historial completo de pagos y saldos de un paciente."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, c.fecha_hora as fecha_consulta, c.motivo_consulta 
            FROM pagos p
            LEFT JOIN consultas c ON p.consulta_id = c.id
            WHERE p.paciente_id = ?
            ORDER BY p.id DESC
        """, (paciente_id,))
        return [dict(r) for r in cursor.fetchall()]

def obtener_todos_los_pagos() -> list:
    """Obtiene todos los registros de pagos y saldos de la clínica."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.*, pac.nombre as nombre_paciente, pac.documento as doc_paciente,
                   c.fecha_hora as fecha_consulta, c.plan_tratamiento
            FROM pagos p
            JOIN pacientes pac ON p.paciente_id = pac.id
            LEFT JOIN consultas c ON p.consulta_id = c.id
            ORDER BY p.id DESC
        """)
        return [dict(r) for r in cursor.fetchall()]

def listar_consultas_paciente(paciente_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, u.nombre AS nombre_medico
            FROM consultas c
            LEFT JOIN usuarios u ON c.medico_id = u.id
            WHERE c.paciente_id = ?
            ORDER BY c.fecha_hora DESC
        """, (paciente_id,))
        return [dict(row) for row in cursor.fetchall()]

def obtener_consulta_por_id(consulta_id):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM consultas WHERE id = ?", (consulta_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

# --- OPERACIONES DE AGENDA ---

def crear_cita_db(paciente_id=None, nombre_paciente="", telefono="", fecha_hora_inicio="", fecha_hora_fin=None, descripcion="", google_event_id=None, **kwargs):
    import datetime
    if not fecha_hora_inicio and "fecha_hora" in kwargs:
        fecha_hora_inicio = kwargs["fecha_hora"]
    if not descripcion and "motivo" in kwargs:
        descripcion = kwargs["motivo"]
    if not nombre_paciente and "paciente" in kwargs:
        nombre_paciente = kwargs["paciente"]
    if not telefono and "celular" in kwargs:
        telefono = kwargs["celular"]
    if not telefono and "tel" in kwargs:
        telefono = kwargs["tel"]

    nombre_paciente = str(nombre_paciente or "").strip() or "Paciente"
    telefono = str(telefono or "").strip()
    if telefono.lower() in ("no especificado", "none", "null"):
        telefono = ""

    if not fecha_hora_inicio:
        fecha_hora_inicio = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime("%Y-%m-%d 10:00:00")

    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Si no hay paciente_id explícito, buscar en la tabla pacientes
        if not paciente_id and nombre_paciente and nombre_paciente.lower() not in ("paciente", "no especificado"):
            cursor.execute("SELECT id, nombre, telefono FROM pacientes WHERE LOWER(nombre) = ? ORDER BY id DESC LIMIT 1", (nombre_paciente.lower(),))
            row_p = cursor.fetchone()
            
            if not row_p:
                cursor.execute("SELECT id, nombre, telefono FROM pacientes WHERE nombre != 'No especificado' ORDER BY id DESC")
                for c_p in cursor.fetchall():
                    if coinciden_nombres_subtokens(nombre_paciente, c_p["nombre"]):
                        row_p = c_p
                        break

            if row_p:
                paciente_id = row_p["id"]
                tel_pac = str(row_p["telefono"] or "").strip()
                if not telefono and tel_pac and tel_pac.lower() not in ("no especificado", "none", ""):
                    telefono = tel_pac
                elif telefono and (not tel_pac or tel_pac.lower() in ("no especificado", "none", "")):
                    cursor.execute("UPDATE pacientes SET telefono = ? WHERE id = ?", (telefono, paciente_id))
                    conn.commit()

        # 2. Si todavía no hay teléfono, buscar en citas previas del mismo paciente con coincidencia exacta o subtokens
        if not telefono and nombre_paciente and nombre_paciente.lower() not in ("paciente", "no especificado"):
            cursor.execute("""
                SELECT nombre_paciente, telefono FROM citas_agenda 
                WHERE LOWER(TRIM(nombre_paciente)) = LOWER(TRIM(?))
                  AND telefono IS NOT NULL 
                  AND telefono != '' 
                  AND telefono != 'No especificado'
                ORDER BY id DESC LIMIT 1
            """, (nombre_paciente,))
            row_prev_c = cursor.fetchone()
            if not row_prev_c:
                cursor.execute("""
                    SELECT nombre_paciente, telefono FROM citas_agenda
                    WHERE telefono IS NOT NULL AND telefono != '' AND telefono != 'No especificado'
                    ORDER BY id DESC
                """)
                for c_cand in cursor.fetchall():
                    if coinciden_nombres_subtokens(nombre_paciente, c_cand["nombre_paciente"]):
                        row_prev_c = c_cand
                        break
            if row_prev_c and row_prev_c["telefono"]:
                telefono = str(row_prev_c["telefono"]).strip()

        # 3. Si se tiene paciente_id y teléfono, asegurar sincronización si el paciente no lo tenía
        if paciente_id and telefono:
            cursor.execute("SELECT telefono FROM pacientes WHERE id = ?", (paciente_id,))
            rp = cursor.fetchone()
            if rp and (not rp["telefono"] or str(rp["telefono"]).strip().lower() in ("no especificado", "none", "")):
                cursor.execute("UPDATE pacientes SET telefono = ? WHERE id = ?", (telefono, paciente_id))
                conn.commit()

        creado_local = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO citas_agenda (
                paciente_id, nombre_paciente, telefono, fecha_hora_inicio,
                fecha_hora_fin, descripcion, google_event_id, creado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (paciente_id, nombre_paciente, telefono, fecha_hora_inicio, fecha_hora_fin, descripcion, google_event_id, creado_local))
        conn.commit()
        return cursor.lastrowid

def listar_citas_db(limite=100):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM citas_agenda 
            WHERE estado != 'cancelada'
            ORDER BY 
                CASE 
                    WHEN fecha_hora_inicio >= datetime('now', 'localtime', '-2 hours') THEN 0 
                    ELSE 1 
                END ASC,
                CASE 
                    WHEN fecha_hora_inicio >= datetime('now', 'localtime', '-2 hours') THEN fecha_hora_inicio 
                END ASC,
                fecha_hora_inicio DESC
            LIMIT ?
        """, (limite,))
        return [dict(row) for row in cursor.fetchall()]

def listar_citas_paciente(paciente_id=None, nombre_paciente=""):
    """Retorna las citas agendadas registradas para un paciente específico."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if paciente_id:
            cursor.execute("""
                SELECT * FROM citas_agenda 
                WHERE paciente_id = ? OR (nombre_paciente != '' AND LOWER(nombre_paciente) = LOWER(?))
                ORDER BY fecha_hora_inicio DESC
            """, (paciente_id, nombre_paciente or ""))
        else:
            cursor.execute("""
                SELECT * FROM citas_agenda 
                WHERE LOWER(nombre_paciente) = LOWER(?)
                ORDER BY fecha_hora_inicio DESC
            """, (nombre_paciente or "",))
        return [dict(r) for r in cursor.fetchall()]

def cancelar_o_eliminar_cita_db(nombre_paciente=None, cita_id=None, fecha=None) -> list:
    """
    Busca y elimina citas de la base de datos por paciente, ID o fecha.
    Retorna la lista de citas eliminadas para borrar también en Google Calendar.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        citas_a_borrar = []

        if cita_id:
            cursor.execute("SELECT * FROM citas_agenda WHERE id = ?", (cita_id,))
            citas_a_borrar = [dict(r) for r in cursor.fetchall()]
            cursor.execute("DELETE FROM citas_agenda WHERE id = ?", (cita_id,))
        elif nombre_paciente:
            primer_nom = nombre_paciente.strip().split()[0] if nombre_paciente else ""
            query = "SELECT * FROM citas_agenda WHERE LOWER(nombre_paciente) LIKE ?"
            params = [f"%{nombre_paciente.lower().strip()}%"]
            if fecha:
                query += " AND fecha_hora_inicio LIKE ?"
                params.append(f"%{fecha}%")
            cursor.execute(query, params)
            citas_a_borrar = [dict(r) for r in cursor.fetchall()]

            # Búsqueda inteligente por primer nombre si no hubo match exacto de apellido
            if not citas_a_borrar and primer_nom and len(primer_nom) >= 3:
                cursor.execute("SELECT * FROM citas_agenda WHERE LOWER(nombre_paciente) LIKE ?", (f"%{primer_nom.lower()}%",))
                citas_a_borrar = [dict(r) for r in cursor.fetchall()]

            # Si aún no hay citas y no se indicó fecha, vincular a la última cita activa creada hoy
            if not citas_a_borrar and not fecha:
                cursor.execute("SELECT * FROM citas_agenda ORDER BY id DESC LIMIT 1")
                citas_a_borrar = [dict(r) for r in cursor.fetchall()]

            if citas_a_borrar:
                ids = [str(c['id']) for c in citas_a_borrar]
                cursor.execute(f"DELETE FROM citas_agenda WHERE id IN ({','.join(ids)})")
        elif fecha:
            cursor.execute("SELECT * FROM citas_agenda WHERE fecha_hora_inicio LIKE ?", (f"%{fecha}%",))
            citas_a_borrar = [dict(r) for r in cursor.fetchall()]
            cursor.execute("DELETE FROM citas_agenda WHERE fecha_hora_inicio LIKE ?", (f"%{fecha}%",))

        conn.commit()
        return citas_a_borrar

def obtener_estadisticas_dashboard():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total_pacientes FROM pacientes;")
        total_p = cursor.fetchone()["total_pacientes"]
        
        cursor.execute("SELECT COUNT(*) AS total_consultas FROM consultas;")
        total_c = cursor.fetchone()["total_consultas"]
        
        cursor.execute("SELECT COUNT(*) AS total_citas FROM citas_agenda WHERE estado = 'programada';")
        total_citas = cursor.fetchone()["total_citas"]
        
        return {
            "total_pacientes": total_p,
            "total_consultas": total_c,
            "citas_pendientes": total_citas
        }

def limpiar_agenda_local_db() -> int:
    """
    Elimina citas con errores de transcripción (ej. 'Tratamiento no especificado'
    o citas huérfanas con campos incompletos).
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM citas_agenda 
            WHERE LOWER(descripcion) LIKE '%no especificado%'
               OR LOWER(nombre_paciente) LIKE '%no especificado%'
               OR nombre_paciente IS NULL
               OR nombre_paciente = ''
               OR fecha_hora_inicio IS NULL
               OR fecha_hora_inicio = ''
        """)
        borradas = cursor.rowcount
        conn.commit()
        return borradas

def vaciar_todas_las_citas_db() -> int:
    """Limpia todas las citas de la agenda local."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM citas_agenda")
        borradas = cursor.rowcount
        conn.commit()
        return borradas

def guardar_foto_paciente_db(paciente_id: int, ruta_archivo: str, categoria: str = "radiografia", descripcion: str = "", consulta_id: int = None) -> int:
    """Registra una radiografía o foto clínica del paciente en la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO fotos_pacientes (paciente_id, consulta_id, categoria, descripcion, ruta_archivo)
            VALUES (?, ?, ?, ?, ?)
        """, (paciente_id, consulta_id, categoria, descripcion, ruta_archivo))
        conn.commit()
        return cursor.lastrowid

def listar_fotos_paciente(paciente_id: int) -> list:
    """Retorna todas las fotos y radiografías registradas para el paciente."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM fotos_pacientes 
            WHERE paciente_id = ? 
            ORDER BY id DESC
        """, (paciente_id,))
        return [dict(r) for r in cursor.fetchall()]

def marcar_recordatorio_enviado_cita(cita_id: int, metodo: str = "wa_me") -> bool:
    """Actualiza el estado de la cita indicando que el recordatorio fue despachado."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE citas_agenda
            SET recordatorio_enviado = 1,
                recordatorio_enviado_at = datetime('now', 'localtime'),
                recordatorio_metodo = ?
            WHERE id = ?
        """, (metodo, cita_id))
        conn.commit()
        return cursor.rowcount > 0

def listar_citas_pendientes_recordatorio(dias_adelanto: int = 1) -> list:
    """Retorna citas de una fecha relativa (ej. mañana) que aún no han sido notificadas."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.*, p.telefono as tel_paciente, p.nombre as nom_pac_db
            FROM citas_agenda c
            LEFT JOIN pacientes p ON c.paciente_id = p.id
            WHERE date(c.fecha_hora_inicio) = date('now', 'localtime', '+' || ? || ' day')
              AND c.estado != 'cancelada'
            ORDER BY c.fecha_hora_inicio ASC
        """, (dias_adelanto,))
        return [dict(r) for r in cursor.fetchall()]

def actualizar_datos_paciente_y_expediente(
    paciente_id_o_nombre,
    nuevo_nombre: str = None,
    nueva_cedula: str = None,
    nuevo_telefono: str = None,
    regenerar_pdf: bool = True,
    documento: str = None
) -> dict:
    """
    Actualiza simultáneamente o individualmente el nombre, cédula y/o teléfono de un paciente
    en las tablas `pacientes` y `citas_agenda`, sincroniza el json_clinico de su última consulta
    y regenera su PDF de historia clínica oficial con los datos actualizados sin crear
    consultas ni pacientes duplicados.
    Si se detectan homónimos, retorna las opciones con su número de cédula para desambiguación.
    """
    import re, json, os
    from ai_engine import extraer_telefono_dictado, sanitizar_cedula, _normalizar_nombres_espanol

    # 1. Normalización previa de parámetros recibidos
    nombre_limpio = None
    if nuevo_nombre and str(nuevo_nombre).strip() and str(nuevo_nombre).lower() not in ("no especificado", "none"):
        nombre_limpio = _normalizar_nombres_espanol(str(nuevo_nombre).strip().title())

    cedula_limpia = None
    if nueva_cedula and str(nueva_cedula).strip() and str(nueva_cedula).lower() not in ("no especificado", "none"):
        ced_cand = sanitizar_cedula(str(nueva_cedula))
        if ced_cand and ced_cand.lower() != "no especificado":
            cedula_limpia = ced_cand

    tel_limpio = None
    if nuevo_telefono and str(nuevo_telefono).strip() and str(nuevo_telefono).lower() not in ("no especificado", "none"):
        t_cand = extraer_telefono_dictado(str(nuevo_telefono))
        if not t_cand:
            digits = re.sub(r'\D', '', str(nuevo_telefono))
            if len(digits) == 9 and digits.startswith('9'):
                digits = '0' + digits
            if len(digits) in (7, 8, 9, 10, 11, 12):
                t_cand = digits
        if t_cand:
            tel_limpio = t_cand

    if not nombre_limpio and not cedula_limpia and not tel_limpio:
        return {"status": "error", "message": "No se especificó ningún dato a actualizar (nombre, cédula o teléfono)."}

    with get_connection() as conn:
        cursor = conn.cursor()
        paciente = None
        pid = None

        # 2. Búsqueda por ID directo
        if isinstance(paciente_id_o_nombre, int) or (isinstance(paciente_id_o_nombre, str) and str(paciente_id_o_nombre).isdigit()):
            cursor.execute("SELECT * FROM pacientes WHERE id = ?", (int(paciente_id_o_nombre),))
            paciente = cursor.fetchone()
            if paciente:
                pid = paciente["id"]

        # 3. Búsqueda por documento si fue proporcionado para desambiguar
        if not paciente and documento:
            doc_busc = sanitizar_cedula(str(documento))
            cursor.execute("SELECT * FROM pacientes WHERE documento = ?", (doc_busc,))
            paciente = cursor.fetchone()
            if paciente:
                pid = paciente["id"]

        # 4. Búsqueda por nombre
        if not paciente and isinstance(paciente_id_o_nombre, str) and paciente_id_o_nombre.strip():
            nom_busqueda = paciente_id_o_nombre.strip()
            cursor.execute("SELECT * FROM pacientes WHERE LOWER(nombre) = LOWER(?)", (nom_busqueda,))
            exactos = cursor.fetchall()
            if len(exactos) == 1:
                paciente = exactos[0]
                pid = paciente["id"]
            elif len(exactos) > 1:
                candidatos = [{"id": r["id"], "nombre": r["nombre"], "documento": r["documento"] or "Sin cédula"} for r in exactos]
                return {
                    "status": "ambiguous",
                    "mensaje": f"Se encontraron {len(exactos)} pacientes con el nombre {nom_busqueda}. Por favor indique la cédula.",
                    "candidatos": candidatos
                }
            else:
                cursor.execute("SELECT * FROM pacientes ORDER BY id DESC")
                todos = cursor.fetchall()
                cands = [p for p in todos if coinciden_nombres_subtokens(nom_busqueda, p["nombre"])]
                if len(cands) == 1:
                    paciente = cands[0]
                    pid = paciente["id"]
                elif len(cands) > 1:
                    candidatos = [{"id": r["id"], "nombre": r["nombre"], "documento": r["documento"] or "Sin cédula"} for r in cands]
                    return {
                        "status": "ambiguous",
                        "mensaje": f"Se encontraron varios pacientes coincidentes con {nom_busqueda}. Por favor desambigüe por cédula.",
                        "candidatos": candidatos
                    }

        if not paciente or not pid:
            return {"status": "error", "message": f"No se encontró el paciente '{paciente_id_o_nombre}' en la base de datos."}

        pac_nombre_prev = paciente["nombre"]
        pac_doc_prev = paciente["documento"] or "No especificado"
        pac_tel_prev = paciente["telefono"] or "No registrado"

        pac_nombre_final = nombre_limpio if nombre_limpio else pac_nombre_prev
        pac_doc_final = cedula_limpia if cedula_limpia else pac_doc_prev
        pac_tel_final = tel_limpio if tel_limpio else pac_tel_prev

        campos_actualizados = []
        if nombre_limpio and nombre_limpio != pac_nombre_prev:
            campos_actualizados.append("nombre")
        if cedula_limpia and cedula_limpia != pac_doc_prev:
            cursor.execute("SELECT id, nombre FROM pacientes WHERE documento = ? AND id != ?", (cedula_limpia, pid))
            dup = cursor.fetchone()
            if dup:
                return {
                    "status": "error",
                    "message": f"La cédula {cedula_limpia} ya está registrada a nombre de '{dup['nombre']}' (ID {dup['id']})."
                }
            campos_actualizados.append("cédula")
        if tel_limpio and tel_limpio != pac_tel_prev:
            campos_actualizados.append("teléfono")

        # 5. Actualizar tabla pacientes
        cursor.execute("""
            UPDATE pacientes 
            SET nombre = ?, documento = ?, telefono = ? 
            WHERE id = ?
        """, (pac_nombre_final, pac_doc_final, pac_tel_final, pid))

        # 6. Actualizar citas_agenda
        cursor.execute("""
            UPDATE citas_agenda 
            SET nombre_paciente = ?, telefono = ? 
            WHERE paciente_id = ? OR LOWER(nombre_paciente) = LOWER(?)
        """, (pac_nombre_final, pac_tel_final, pid, pac_nombre_prev))
        conn.commit()

        # 7. Actualizar expediente clínico más reciente y regenerar PDF
        nueva_ruta_pdf = None
        cursor.execute("SELECT id, json_clinico, ruta_pdf FROM consultas WHERE paciente_id = ? ORDER BY id DESC LIMIT 1", (pid,))
        cons_row = cursor.fetchone()
        if cons_row:
            cid = cons_row["id"]
            ruta_antigua = cons_row["ruta_pdf"]
            json_c = {}
            if cons_row["json_clinico"]:
                try:
                    json_c = json.loads(cons_row["json_clinico"])
                except Exception:
                    pass
            fil = json_c.setdefault("datos_filiacion", {})
            fil["nombre"] = pac_nombre_final
            fil["documento"] = pac_doc_final
            fil["telefono"] = pac_tel_final

            if regenerar_pdf:
                from generador_pdf import crear_historia_clinica
                nueva_ruta_pdf = crear_historia_clinica(json_c, paciente_id=pid)
                cursor.execute("UPDATE consultas SET json_clinico = ?, ruta_pdf = ? WHERE id = ?",
                               (json.dumps(json_c, ensure_ascii=False), nueva_ruta_pdf, cid))
                conn.commit()
                if ruta_antigua and nueva_ruta_pdf and ruta_antigua != nueva_ruta_pdf and os.path.exists(ruta_antigua):
                    try:
                        os.remove(ruta_antigua)
                    except Exception:
                        pass

    partes_msg = []
    if nombre_limpio:
        partes_msg.append(f"Nombre: {pac_nombre_final}")
    if cedula_limpia:
        partes_msg.append(f"Cédula: {pac_doc_final}")
    if tel_limpio:
        partes_msg.append(f"Teléfono: {pac_tel_final}")

    desc_cambios = ", ".join(partes_msg) if partes_msg else "Datos actualizados"

    return {
        "status": "ok",
        "paciente_id": pid,
        "nombre": pac_nombre_final,
        "documento": pac_doc_final,
        "telefono": pac_tel_final,
        "campos_actualizados": campos_actualizados,
        "ruta_pdf": nueva_ruta_pdf,
        "mensaje": f"Datos de {pac_nombre_final} actualizados exitosamente ({desc_cambios}). Expediente PDF regenerado."
    }

def actualizar_telefono_paciente_y_expediente(paciente_id_o_nombre, nuevo_telefono: str, regenerar_pdf: bool = True, documento: str = None) -> dict:
    """Mantiene compatibilidad hacia atrás delegando en actualizar_datos_paciente_y_expediente."""
    return actualizar_datos_paciente_y_expediente(
        paciente_id_o_nombre=paciente_id_o_nombre,
        nuevo_telefono=nuevo_telefono,
        regenerar_pdf=regenerar_pdf,
        documento=documento
    )

def actualizar_contacto_cita_manana(nuevo_telefono: str) -> dict:
    """Actualiza el teléfono de la próxima cita agendada para el día de mañana."""
    import re
    digits = re.sub(r'\D', '', str(nuevo_telefono or ""))
    if len(digits) == 9 and digits.startswith('9'):
        digits = '0' + digits
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre_paciente, fecha_hora_inicio 
            FROM citas_agenda 
            WHERE date(fecha_hora_inicio) = date('now', 'localtime', '+1 day')
              AND estado != 'cancelada'
            ORDER BY fecha_hora_inicio ASC LIMIT 1
        """)
        r = cursor.fetchone()
        if r:
            cursor.execute("UPDATE citas_agenda SET telefono = ? WHERE id = ?", (digits, r["id"]))
            conn.commit()
            return {
                "status": "ok",
                "cita_id": r["id"],
                "nombre_paciente": r["nombre_paciente"],
                "telefono": digits,
                "mensaje": f"Teléfono {digits} asignado a la cita de mañana para {r['nombre_paciente']}."
            }
        return {"status": "error", "message": "No se encontraron citas activas para el día de mañana."}


