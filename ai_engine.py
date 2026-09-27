import os
import json
import time
import datetime
import re
from faster_whisper import WhisperModel
from groq import Groq
from config import get_groq_api_key, get_groq_model, get_whisper_model

_whisper_model = None

def get_whisper_engine(device="cpu", compute_type="int8"):
    global _whisper_model
    if _whisper_model is None:
        model_size = get_whisper_model()
        threads = os.cpu_count() or 4
        print(f"[IA] Cargando Faster-Whisper ({model_size}) con {threads} hilos de CPU optimizados...")
        _whisper_model = WhisperModel(model_size, device=device, compute_type=compute_type, cpu_threads=threads)
    return _whisper_model
GLOSARIO_ANDINO_KICHWA = (
    "Nombres y apellidos andinos, kichwas, ecuatorianos y latinoamericanos: "
    "Llumiquinga, Yumiquinga, Llumi Kinga, Yumi Kinga, Guaminga, Huaminga, Toapanta, Tuapanta, "
    "Quispe, Quishpe, Simbaña, Simbana, Tituaña, Tituana, Chiluisa, Chushig, Pilataxi, Pilatagsi, "
    "Chuquimarca, Yugsi, Llugsi, Yucsi, Quinatoa, Kinatoa, Alomoto, Tipán, Tipan, Caiza, Kaisa, "
    "Tasinchana, Masabanda, Andrango, Imbaquingo, Farinango, Colcha, Morocho, Pastuña, Pastuna, "
    "Guanoluisa, Guasgua, Curipoma, Sampedro, Sangoluisa, Sangoquisa, Pupiales, Fueres, Otavalo, "
    "Cotacachi, Cachiguango, Cachimuel, Cabascango, Jimmy Cabascango, Cavascango, Guamán, Guaman, "
    "Cajas, Criollo, Alulema, Muenala, Pillajo, Chimbo, Chango, Cango, Yánez, Yanez, Tasambay, "
    "Simaluiza, Tisalema, Paucar, Sisa, Inti, Tupac, Tupaq, Killa, Ñusta, Nayra, Amaru, Pacari, Nina, "
    "Raymi, Kuntur, Sayri, Chuki, Hakan, Wayra, Tamia, Runa, Quilla, Illari, Huáscar, Atahualpa, Rumiñahui, "
    "Mateo Ramírez, Sebastián Ramírez, Gandhi López, Juan Valdés, Juliana Aragón, Estefanía Sandoval."
)

GLOSARIO_NOMBRES_HISPANOAMERICANOS = (
    "Nombres y apellidos hispanoamericanos frecuentes: "
    "Sebastián, Mateo, Santiago, Alejandro, Leonardo, Nicolás, Gabriel, Daniel, Samuel, David, "
    "Joaquín, Martín, Emilio, Emiliano, Camilo, Julián, Lucas, Tomás, Diego, Carlos, Juan, "
    "Andrés, Felipe, Fernando, Rodrigo, Gonzalo, Patricio, Fabricio, Mauricio, Marcelo, Javier, "
    "Álvaro, Cristian, Christian, Ignacio, Francisco, Ángel, Miguel, Manuel, Rafael, Pedro, "
    "Pablo, Jorge, José, Luis, Eduardo, Alberto, Ricardo, Guillermo, Alfonso, Roberto, Arturo, "
    "Raúl, Hugo, Mario, César, Enrique, Ramón, Jaime, Salvador, Estefanía, Juliana, Valentina, "
    "Camila, Sofía, Isabella, Lucía, Valeria, Daniela, Mariana, Gabriela, Victoria, Natalia, "
    "Andrea, Paula, Carolina, Alejandra, Fernanda, Constanza, Martina, Antonia, Renata, Florencia, "
    "Belén, Jimena, Ximena, Paulina, Montserrat, Rocío, Macarena, Micaela, Paloma, Elena, Carmen, "
    "Teresa, Patricia, Rosa, Beatriz, Gloria, Ramírez, Salazar, Valdés, Valdez, López, Mendoza, "
    "Sandoval, Aragón, Rodríguez, Gómez, González, Hernández, Martínez, Pérez, Sánchez, Díaz, "
    "Morales, Romero, Castro, Ortiz, Silva, Vargas, Ramos, Reyes, Cruz, Flores, Gutiérrez, Chávez, "
    "Barahona, Baraona, Dani Barahona, Dani Baraona."
)

GLOSARIO_ODONTOLOGICO = (
    "Términos odontológicos: odontograma, piezas FDI 11 al 48, caras oclusal, vestibular, "
    "palatino, lingual, mesial, distal, caries oclusal profunda, resina compuesta fotocurable, "
    "amalgama de plata, endodoncia birradicular multirradicular, pulpectomía, pulpotomía, "
    "exodoncia simple quirúrgica, diente ausente extracción previa, corona metal porcelana, "
    "incrustación onlay inlay, perno de fibra de vidrio, ionómero de vidrio, profilaxis dental, "
    "detartraje supragingival, gingivitis marginal, periodontitis crónica, recesión gingival, "
    "abfracción, atrición, fluorosis dental, ortodoncia arcos NiTi acero .019x.025 TMA, "
    "brackets Roth MBT, elásticos intermaxilares, mordida abierta cruzada sobremordida clase I II III."
)

def transcribir_audio(ruta_wav, initial_prompt=None) -> str:
    model = get_whisper_engine()
    if not initial_prompt:
        from config import cargar_datos_clinica
        datos = cargar_datos_clinica()
        doc_nom = datos.get("nombre_doctor", "Mateo Ramírez")
        
        # Inyección de vocabulario aprendido dinámicamente desde la base de datos
        vocab_aprendido = ""
        try:
            from database import obtener_vocabulario_aprendido
            terminos_db = obtener_vocabulario_aprendido(limite=50)
            if terminos_db:
                vocab_aprendido = " Apellidos y pacientes aprendidos: " + ", ".join(terminos_db) + "."
        except Exception:
            vocab_aprendido = ""

        initial_prompt = (
            f"Consulta odontológica y médica del Doctor {doc_nom}. "
            f"Dictado clínico de números y contactos: cero nueve, seis cero cero, seiscientos, seiscientos veintiocho, doble cero, teléfono, cédula. "
            f"{GLOSARIO_NOMBRES_HISPANOAMERICANOS} {GLOSARIO_ANDINO_KICHWA}{vocab_aprendido} {GLOSARIO_ODONTOLOGICO}"
        )
    try:
        segmentos, _ = model.transcribe(
            ruta_wav, 
            language="es",
            initial_prompt=initial_prompt,
            vad_filter=True,
            vad_parameters=dict(
                threshold=0.42,
                min_speech_duration_ms=250,
                max_speech_duration_s=60,
                min_silence_duration_ms=450,
                speech_pad_ms=300
            ),
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False
        )
        texto = "".join([s.text + " " for s in segmentos]).strip()
    except Exception as e_vad:
        print(f"[TRANSCRIPCIÓN VAD FALLBACK] VAD no disponible ({e_vad}). Transcribiendo directamente...")
        segmentos, _ = model.transcribe(
            ruta_wav, 
            language="es",
            initial_prompt=initial_prompt,
            vad_filter=False,
            beam_size=1,
            best_of=1,
            temperature=0.0,
            condition_on_previous_text=False
        )
        texto = "".join([s.text + " " for s in segmentos]).strip()
    return texto

def contiene_especificacion_temporal(texto: str) -> bool:
    """Detecta de forma determinista si un texto contiene indicación de día, fecha u hora."""
    if not texto:
        return False
    t = texto.lower().strip()
    dias = ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado", "sabado", "domingo", "mañana", "manana", "hoy", "pasado mañana", "semana", "mes"]
    if any(d in t for d in dias):
        return True
    import re
    if re.search(r'\b(?:a\s+las?|las?|a\s+la)\s+\d{1,2}\b', t):
        return True
    if re.search(r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm|de la mañana|de la tarde|de la noche)\b', t):
        return True
    if re.search(r'\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b', t):
        return True
    return False

def _normalizar_nombres_espanol(nombre: str) -> str:
    """Normaliza nombres hispanoamericanos y andinos, corrigiendo deformaciones acústicas (ej. 'Yumi Kinga' -> 'Llumiquinga')."""
    if not nombre or not isinstance(nombre, str):
        return nombre
    
    import re
    reemplazos = [
        # Normalización fonética andina clave (Llumiquinga)
        (r"\b(?:yumi|llumi)\s*k?i[nñ]ga\b", "Llumiquinga"),
        (r"\bYumiquinga\b", "Llumiquinga"),
        (r"\bYumi\s*kinga\b", "Llumiquinga"),
        (r"\bLlumikinga\b", "Llumiquinga"),
        (r"\bLlumi\s*kinga\b", "Llumiquinga"),
        (r"\bHuaminga\b", "Guaminga"),
        (r"\bWaminga\b", "Guaminga"),
        (r"\bTuapanta\b", "Toapanta"),
        (r"\b(?:Kizpe|Kispe|Quizhpe)\b", "Quispe"),
        (r"\bQuichpe\b", "Quishpe"),
        (r"\bQuiche\b", "Quishpe"),
        (r"\bChispe\b", "Quispe"),
        (r"\bSimbana\b", "Simbaña"),
        (r"\bTituana\b", "Tituaña"),
        (r"\bPilatagsi\b", "Pilataxi"),
        (r"\bLlugsi\b", "Yugsi"),
        (r"\bYucsi\b", "Yugsi"),
        (r"\bKinatoa\b", "Quinatoa"),
        (r"\bKaisa\b", "Caiza"),
        (r"\bPastuna\b", "Pastuña"),
        (r"\bHuaman\b", "Guamán"),
        (r"\bSan\s+Pedro\b", "Sampedro"),
        # Nombres y apellidos hispanoamericanos
        (r"\bSebastiano\b", "Sebastián"),
        (r"\bSebastian\b", "Sebastián"),
        (r"\bMatteo\b", "Mateo"),
        (r"\bStefania\b", "Estefanía"),
        (r"\bStefany\b", "Estefanía"),
        (r"\bEstefani\b", "Estefanía"),
        (r"\bAlessandro\b", "Alejandro"),
        (r"\bGiovanni\b", "Juan"),
        (r"\bValdes\b", "Valdés"),
        (r"\bValdez\b", "Valdés"),
        (r"\bRamirez\b", "Ramírez"),
        (r"\bLopez\b", "López"),
        (r"\bAragon\b", "Aragón"),
        (r"\bGomez\b", "Gómez"),
        (r"\bSanchez\b", "Sánchez"),
        (r"\bRodriguez\b", "Rodríguez"),
        (r"\bGonzalez\b", "González"),
        (r"\bMartinez\b", "Martínez"),
        (r"\bPerez\b", "Pérez"),
        (r"\bDiaz\b", "Díaz"),
        (r"\bNicolas\b", "Nicolás"),
        (r"\bMartin\b", "Martín"),
        (r"\bJoaquin\b", "Joaquín"),
        (r"\bJulian\b", "Julián"),
        (r"\bAndres\b", "Andrés"),
        (r"\bVarahona\b", "Barahona"),
        (r"\bVaraona\b", "Barahona"),
        (r"\bBaraona\b", "Barahona"),
        (r"\bJamie\s+Cabascango\b", "Jimmy Cabascango"),
        (r"\bYimi\s+Cabascango\b", "Jimmy Cabascango"),
        (r"\bJimi\s+Cabascango\b", "Jimmy Cabascango"),
        (r"\bJimmy\s+Cavascango\b", "Jimmy Cabascango"),
        (r"\bJamie\b", "Jimmy"),
        (r"\bYimi\b", "Jimmy"),
        (r"\bJimi\b", "Jimmy"),
        (r"\bCavascango\b", "Cabascango"),
        (r"\bCavazcango\b", "Cabascango"),
    ]
    res = nombre
    for pat, rep in reemplazos:
        res = re.sub(pat, rep, res, flags=re.IGNORECASE)
    return res

def sanitizar_cedula(doc: str) -> str:
    """Limpia cédula o documento extrayendo dígitos y eliminando comas, puntos o espacios del dictado."""
    if not doc or str(doc).lower() in ("no especificado", "none", ""):
        return "No especificado"
    solo_digitos = "".join([c for c in str(doc) if c.isdigit()])
    if len(solo_digitos) >= 5:
        return solo_digitos
    return str(doc).replace(",", "").replace(" ", "").strip()

def _inferir_sexo_por_nombre(nombre: str) -> str:
    """Infiere el sexo del paciente por su nombre de pila en español si no fue dictado."""
    if not nombre or nombre.lower() in ("no especificado", "paciente", "paciente_consulta"):
        return "No especificado"
    
    primer_nombre = nombre.strip().split()[0].lower()
    # Nombres femeninos comunes (incluyendo andinos/kichwas femeninos)
    if primer_nombre in ("sisa", "killa", "ñusta", "nusta", "nayra", "tamia", "quilla", "illari", "estefanía", "estefania", "maria", "maría", "ana", "carmen", "laura", "sofia", "sofía", "lucia", "lucía", "paula", "andrea", "daniela", "valeria", "camila", "carolina", "juliana"):
        return "Femenino"
    if primer_nombre in ("inti", "tupac", "tupaq", "amaru", "pacari", "raymi", "kuntur", "sayri", "hakan", "wayra", "huáscar", "huascar", "atahualpa", "rumiñahui", "mateo", "sebastian", "sebastián", "juan", "carlos", "gandhi", "diego", "luis", "pablo", "alejandro", "andres", "andrés", "felipe", "miguel"):
        return "Masculino"
        
    if primer_nombre.endswith(("a", "ia", "ina", "ela", "ita")):
        return "Femenino"
    elif primer_nombre.endswith(("o", "on", "án", "an", "el", "or", "os")):
        return "Masculino"
    return "No especificado"

def _limpiar_edad_dictada(edad_raw: str, texto_completo: str = "") -> str:
    """
    Limpia y normaliza la edad del paciente en español.
    Corrige confusiones acústicas comunes como 'diez y seis' -> '10 años y 6 meses' -> '16 años'.
    """
    import re
    if not edad_raw or str(edad_raw).lower() in ("no especificado", "none", ""):
        s = ""
    else:
        s = str(edad_raw).strip()

    # Confusiones fonéticas acústicas explícitas (diez y seis -> 10 años y 6 meses o 10 y 6)
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?6\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "16 años"
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?7\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "17 años"
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?8\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "18 años"
    if re.search(r'\b10\s*(?:años?)?\s*(?:y\s*)?9\s*(?:meses?)?\b', s, re.IGNORECASE):
        return "19 años"

    if texto_completo:
        t_lower = texto_completo.lower()
        if re.search(r'\b(?:16|diecis[eé]is|diez y seis)\s*a[ñn]os?\b', t_lower):
            return "16 años"
        if re.search(r'\b(?:17|diecisiete|diez y siete)\s*a[ñn]os?\b', t_lower):
            return "17 años"
        if re.search(r'\b(?:18|dieciocho|diez y ocho)\s*a[ñn]os?\b', t_lower):
            return "18 años"
        if re.search(r'\b(?:19|diecinueve|diez y nueve)\s*a[ñn]os?\b', t_lower):
            return "19 años"
        m_txt = re.search(r'\b(\d{1,3})\s*a[ñn]os?\b', t_lower)
        if m_txt:
            return f"{m_txt.group(1)} años"

    m_dig = re.search(r'\b(\d{1,3})\b', s)
    if m_dig:
        return f"{m_dig.group(1)} años"

    if "año" in s.lower():
        return s
    return f"{s} años" if s else "No especificado"

def _extraer_y_calcular_pagos(pagos_dict: dict, texto_crudo: str = "") -> dict:
    """
    Extrae, valida y calcula con precisión matemática los honorarios, abonos y saldo restante.
    Determina si el estado es 'Cancelado' (saldo <= 0) o 'Saldo Pendiente'.
    """
    import re

    costo = 0.0
    abono = 0.0
    saldo = 0.0
    metodo = "Efectivo"
    notas = ""

    if isinstance(pagos_dict, dict):
        try:
            costo = float(pagos_dict.get("costo_total") or 0.0)
        except (ValueError, TypeError):
            costo = 0.0
        try:
            abono = float(pagos_dict.get("abono") or 0.0)
        except (ValueError, TypeError):
            abono = 0.0
        try:
            saldo = float(pagos_dict.get("saldo_pendiente") or 0.0)
        except (ValueError, TypeError):
            saldo = 0.0
        metodo = str(pagos_dict.get("metodo_pago") or "Efectivo")
        notas = str(pagos_dict.get("notas") or "")

    # Respaldo de extracción matemática regex directamente sobre el texto dictado
    if texto_crudo:
        t_lower = texto_crudo.lower()
        
        # 1. Costo: "cuesta 150", "costo de 150", "coste 150", "valor de 150", "total 150"
        m_costo = re.search(r'(?:costo|precio|valor|cuesta|coste|total)\s*(?:es\s*de|es|de)?\s*(?:un\s*total\s*de)?\s*\$?\s*(\d+(?:[.,]\d+)?)', t_lower)
        if m_costo and costo == 0.0:
            try:
                costo = float(m_costo.group(1).replace(",", "."))
            except Exception:
                pass

        # 2. Abono: "abono de 50", "abona 50", "deja 50", "paga 50", "adelanto de 50", "entrada de 50"
        m_abono = re.search(r'(?:abono|abona|adelanto|entrada|deja|paga)\s*(?:es\s*de|es|de)?\s*\$?\s*(\d+(?:[.,]\d+)?)', t_lower)
        if m_abono and abono == 0.0:
            try:
                abono = float(m_abono.group(1).replace(",", "."))
            except Exception:
                pass

        # 3. Saldo dictado: "queda 100", "restante 100", "saldo de 100", "resta 100", "debe 100"
        m_saldo = re.search(r'(?:saldo|restante|resta|queda|debe|pendiente)\s*(?:es\s*de|es|de)?\s*\$?\s*(\d+(?:[.,]\d+)?)', t_lower)
        if m_saldo and saldo == 0.0:
            try:
                saldo = float(m_saldo.group(1).replace(",", "."))
            except Exception:
                pass

        # 4. Cancelación total explícita
        if any(k in t_lower for k in ["cancelado en su totalidad", "saldo cancelado", "totalmente cancelado", "pago completo", "cancela todo", "cancela en su totalidad", "al dia", "al día"]):
            if costo > 0.0:
                abono = costo
                saldo = 0.0

    # Lógica de balance financiero
    if costo > 0.0:
        if abono > 0.0:
            saldo = max(0.0, round(costo - abono, 2))
        elif saldo > 0.0:
            abono = max(0.0, round(costo - saldo, 2))
        else:
            saldo = costo

    estado = "Cancelado" if (costo > 0.0 and saldo <= 0.0) else ("Saldo Pendiente" if saldo > 0.0 else "Cancelado")

    return {
        "costo_total": round(costo, 2),
        "abono": round(abono, 2),
        "saldo_pendiente": round(saldo, 2),
        "estado": estado,
        "metodo_pago": metodo,
        "notas": notas
    }

DIAS_SEMANA_MAP = {
    'lunes': 0, 'martes': 1, 'miercoles': 2, 'miércoles': 2,
    'jueves': 3, 'viernes': 4, 'sabado': 5, 'sábado': 5, 'domingo': 6
}

HORAS_PALABRAS_MAP = {
    'una': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5, 'seis': 6,
    'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10, 'once': 11, 'doce': 12
}

def resolver_fecha_relativa_espanol(texto: str, base_dt: datetime.datetime = None) -> str | None:
    """
    Resuelve con precisión matemática y sin alucinaciones expresiones de tiempo relativo en español:
    'el lunes', 'el martes', 'mañana', 'pasado mañana', 'en 15 días', 'a las 3 de la tarde', etc.
    """
    if not texto:
        return None
    if base_dt is None:
        base_dt = datetime.datetime.now()

    t = texto.lower()
    fecha_res = None

    # 1. Días de la semana explícitos
    for nom_dia, num_dia in DIAS_SEMANA_MAP.items():
        if re.search(rf'\b(?:el|para el|este|pr[oó]ximo)?\s*{nom_dia}\b', t):
            cur_wd = base_dt.weekday()
            diff = (num_dia - cur_wd) % 7
            if diff == 0:
                diff = 7  # El próximo si se dicta el mismo día
            fecha_res = (base_dt + datetime.timedelta(days=diff)).date()
            break

    # 2. Mañana / Pasado mañana
    if not fecha_res:
        if 'pasado mañana' in t or 'pasado manana' in t:
            fecha_res = (base_dt + datetime.timedelta(days=2)).date()
        elif re.search(r'\b(?:para|el d[ií]a de|desde)?\s*ma[ñn]ana\b', t) and not re.search(r'\bde la ma[ñn]ana\b', t):
            fecha_res = (base_dt + datetime.timedelta(days=1)).date()
        elif re.search(r'\bma[ñn]ana\s+(?:a las|por la|en la)', t):
            fecha_res = (base_dt + datetime.timedelta(days=1)).date()

    # 3. 'en / dentro de X días'
    if not fecha_res:
        m_d = re.search(r'\b(?:en|dentro de)\s+(\d{1,3})\s+d[ií]as\b', t)
        if m_d:
            fecha_res = (base_dt + datetime.timedelta(days=int(m_d.group(1)))).date()

    # 4. 'en una semana' / 'en dos semanas' / 'en un mes'
    if not fecha_res:
        if 'en una semana' in t or 'una semana' in t:
            fecha_res = (base_dt + datetime.timedelta(days=7)).date()
        elif 'en dos semanas' in t or 'dos semanas' in t:
            fecha_res = (base_dt + datetime.timedelta(days=14)).date()
        elif 'en un mes' in t or 'un mes' in t:
            fecha_res = (base_dt + datetime.timedelta(days=30)).date()

    if not fecha_res:
        return None

    # Extraer hora de la cita
    hora = 10
    minuto = 0
    m_h = re.search(r'a las\s+(\d{1,2})(?::(\d{2})|\s+y\s+(media|cuarto|\d{1,2}))?\s*(am|pm|de la tarde|de la noche|de la ma[ñn]ana)?', t)
    if m_h:
        h_num = int(m_h.group(1))
        if m_h.group(2):
            minuto = int(m_h.group(2))
        elif m_h.group(3):
            sub_m = m_h.group(3)
            if sub_m == 'media':
                minuto = 30
            elif sub_m == 'cuarto':
                minuto = 15
            else:
                minuto = int(sub_m)
        suf = m_h.group(4) or ''
        if any(x in suf for x in ['pm', 'tarde', 'noche']) and h_num < 12:
            h_num += 12
        elif any(x in suf for x in ['am', 'mañana', 'manana']) and h_num == 12:
            h_num = 0
        hora = h_num
    else:
        for w_h, val_h in HORAS_PALABRAS_MAP.items():
            if re.search(rf'a las\s+{w_h}', t):
                hora = val_h
                if any(x in t for x in ['tarde', 'noche', 'pm']) and hora < 12:
                    hora += 12
                break
        if 'y media' in t:
            minuto = 30
        elif 'y cuarto' in t:
            minuto = 15

    return f"{fecha_res.isoformat()} {hora:02d}:{minuto:02d}:00"

def resolver_reprogramacion_relativa(texto: str) -> dict | None:
    """
    Detecta y resuelve reprogramaciones de citas contextuales o relativas a otro paciente:
    Ejemplo: 'necesito que la cita del 11 de Jackeline Villacreses se cambie para el sábado antes de la de Julián Taxopamba, una hora antes'
    """
    if not texto:
        return None
    t = texto.lower()
    if not any(k in t for k in ["reprograma", "cambia", "cambiar", "mueve", "mover", "pasa", "pasar", "antes de", "despues de", "después de"]):
        return None

    # 1. Detectar relación (antes / después)
    direccion = "antes"
    if "después de" in t or "despues de" in t:
        direccion = "despues"

    # 2. Detectar delta (1 hora, 2 horas, media hora, 30 min, etc.)
    delta_minutos = 60
    if re.search(r'\b(?:2|dos)\s+horas?\b', t):
        delta_minutos = 120
    elif re.search(r'\b(?:1|una)\s+hora\b', t):
        delta_minutos = 60
    elif re.search(r'\b(?:media\s+hora|30\s*min(?:utos)?)\b', t):
        delta_minutos = 30
    elif re.search(r'\b(?:15\s*min(?:utos)?|un cuarto de hora)\b', t):
        delta_minutos = 15

    # 3. Detectar nombre de referencia tras 'antes de / después de'
    m_ref = re.search(r'(?:antes|despu[eé]s)\s+de\s+(?:la\s+(?:cita\s+)?de\s+)?([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+){1,3})', t)
    if not m_ref:
        return None

    nom_referencia = m_ref.group(1).strip().title()
    nom_referencia = re.sub(r'\b(Es|Decir|Para|El|La|Una|Dos|Horas|Antes|Despues)\b', '', nom_referencia).strip()

    # 4. Buscar cita del paciente de referencia en la base de datos
    from config import RUTA_DB
    import sqlite3
    try:
        with sqlite3.connect(RUTA_DB) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            palabras_ref = nom_referencia.lower().split()
            cand = None
            for p in palabras_ref:
                if len(p) >= 4:
                    c.execute("SELECT * FROM citas_agenda WHERE LOWER(nombre_paciente) LIKE ? AND estado != 'cancelada' ORDER BY id DESC LIMIT 1", (f"%{p}%",))
                    cand = c.fetchone()
                    if cand:
                        break
            
            if not cand:
                return None

            ref_f_inicio = cand["fecha_hora_inicio"]
            nom_ref_real = cand["nombre_paciente"]

        # 5. Parsear fecha de referencia
        dt_ref = None
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
            try:
                dt_ref = datetime.datetime.strptime(ref_f_inicio, fmt)
                break
            except Exception:
                pass

        if not dt_ref:
            return None

        # 6. Calcular nueva fecha/hora sumando o restando el delta
        delta = datetime.timedelta(minutes=delta_minutos)
        nueva_dt = dt_ref - delta if direccion == "antes" else dt_ref + delta
        nueva_fecha_hora = nueva_dt.strftime("%Y-%m-%d %H:%M:00")

        # 7. Detectar paciente objetivo (quién se quiere reprogramar)
        nom_objetivo = None
        m_obj = re.search(r'(?:cita\s+(?:del\s+\d+\s+)?de\s+)([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*?)(?=\s+(?:para|a|al|hacia|por|el|la|antes|despu[eé]s|se|que|\d+|una|dos|tres|media)|$)', t)
        if m_obj:
            nom_objetivo = m_obj.group(1).strip().title()
            nom_objetivo = re.sub(r'\b(Se|Cambie|Mueva|Pase|Para|El|La|Sábado|Sabado|Viernes)\b', '', nom_objetivo).strip()

        nom_final = _normalizar_nombres_espanol(nom_objetivo or "No especificado")

        # Si el nombre detectado es parcial o un solo nombre (ej: 'Jackeline'), sincronizar con la cita real registrada
        if nom_final and nom_final != "No especificado":
            try:
                with sqlite3.connect(RUTA_DB) as conn_obj:
                    conn_obj.row_factory = sqlite3.Row
                    c_obj = conn_obj.cursor()
                    palabras_obj = nom_final.lower().split()
                    primer_tok = palabras_obj[0] if palabras_obj else ""
                    if len(primer_tok) >= 3:
                        c_obj.execute("SELECT nombre_paciente FROM citas_agenda WHERE LOWER(nombre_paciente) LIKE ? AND estado != 'cancelada' ORDER BY id DESC LIMIT 1", (f"%{primer_tok}%",))
                        row_obj = c_obj.fetchone()
                        if row_obj and row_obj["nombre_paciente"]:
                            nom_final = row_obj["nombre_paciente"]
            except Exception:
                pass

        horas_texto = f"{delta_minutos//60} hora{'s' if delta_minutos>=120 else ''}" if delta_minutos % 60 == 0 else f"{delta_minutos} minutos"
        return {
            "tipo": "REPROGRAMAR_CITA",
            "nombre_paciente": nom_final,
            "nombre_referencia": nom_ref_real,
            "fecha_hora": nueva_fecha_hora,
            "delta_minutos": delta_minutos,
            "direccion": direccion,
            "motivo": f"Cita reprogramada {horas_texto} {direccion} de {nom_ref_real}",
            "mensaje_confirmacion": f"Cita de {nom_final} reprogramada para {nueva_fecha_hora} ({horas_texto} {direccion} de {nom_ref_real})"
        }
    except Exception as e_rel:
        print(f"[REPROGRAMAR RELATIVO WARN]: {e_rel}")
        return None

def _enriquecer_evaluacion_ortodoncia(orto_dict: dict, texto_crudo: str) -> dict:
    """Estructura y enriquece la ficha especializada de ortodoncia según el dictado clínico."""
    if not isinstance(orto_dict, dict):
        orto_dict = {}

    t_low = texto_crudo.lower()

    # Perfil Facial
    if "convexo" in t_low:
        orto_dict["perfil_facial"] = "Perfil convexo"
    elif "concavo" in t_low or "cóncavo" in t_low:
        orto_dict["perfil_facial"] = "Perfil cóncavo"
    elif not orto_dict.get("perfil_facial") or orto_dict.get("perfil_facial") == "No especificado":
        orto_dict["perfil_facial"] = "Perfil recto - armónico"

    # Biotipo Facial
    if "dolicofacial" in t_low:
        orto_dict["biotipo_facial"] = "Dolicofacial"
    elif "braquifacial" in t_low:
        orto_dict["biotipo_facial"] = "Braquifacial"
    elif not orto_dict.get("biotipo_facial") or orto_dict.get("biotipo_facial") == "No especificado":
        orto_dict["biotipo_facial"] = "Mesofacial armónico"

    # Simetría Facial
    if any(k in t_low for k in ["asimetria", "asimetría", "desviacion", "desviación"]):
        orto_dict["simetria_facial"] = "Asimetría / desviación facial detectada"
    elif not orto_dict.get("simetria_facial") or orto_dict.get("simetria_facial") == "No especificado":
        orto_dict["simetria_facial"] = "Simetría frontal conservada sin desviaciones"

    # Hábitos Orales
    habitos_detectados = []
    if "respirador bucal" in t_low or "respiracion bucal" in t_low:
        habitos_detectados.append("Respirador bucal")
    if "interposicion lingual" in t_low or "interposición lingual" in t_low:
        habitos_detectados.append("Interposición lingual")
    if "deglucion atipica" in t_low or "deglución atípica" in t_low:
        habitos_detectados.append("Deglución atípica")
    if "succion digital" in t_low or "succión digital" in t_low or "chuparse el dedo" in t_low:
        habitos_detectados.append("Succión digital")
    if "bruxismo" in t_low:
        habitos_detectados.append("Bruxismo céntrico / excéntrico")
    if "onicofagia" in t_low:
        habitos_detectados.append("Onicofagia")

    if habitos_detectados:
        orto_dict["habitos_orales"] = ", ".join(habitos_detectados)
    elif not orto_dict.get("habitos_orales") or orto_dict.get("habitos_orales") == "No especificado":
        orto_dict["habitos_orales"] = "No refiere hábitos perniciosos activos"

    # Planificación y Fases de Ortodoncia
    fases = orto_dict.get("fases_planificacion", {})
    if not isinstance(fases, dict):
        fases = {}

    fases.setdefault("fase_1", "Fase I (Alineación): Arcos NiTi redondos (.012 a .016)")
    fases.setdefault("fase_2", "Fase II (Trabajo): Arcos de Acero rectangular (.019x.025) y cierre")
    fases.setdefault("fase_3", "Fase III (Finalización): Arcos TMA y elásticos intermaxilares")
    fases.setdefault("fase_4", "Fase IV (Retención): Termoformado Essix y/o barra fija lingual")
    orto_dict["fases_planificacion"] = fases

    # Hoja de Evolución Clínica y Activaciones
    evo = orto_dict.get("evolucion_activacion", {})
    if not isinstance(evo, dict):
        evo = {}

    m_arco = re.search(r'(?:arcos?|colocaci[oó]n de|ajuste de|cambio de|instalaci[oó]n de)\s+([^\.,;]+)', t_low)
    if m_arco:
        evo.setdefault("procedimiento", f"Activación: {m_arco.group(0).strip().capitalize()}")
    elif any(k in t_low for k in ["instalacion", "instalación", "colocacion", "colocación", "brackets"]):
        evo.setdefault("procedimiento", "Instalación de aparatología ortodóncica fija y cementado.")
    else:
        evo.setdefault("procedimiento", "Control ortodóncico, valoración de arcos y ajuste de ligaduras.")

    evo.setdefault("higiene", "Buena" if "buena" in t_low else ("Deficiente" if any(k in t_low for k in ["mala", "deficiente", "placa"]) else "Adecuada"))
    evo.setdefault("proxima_cita", "4 semanas (1 mes)")
    orto_dict["evolucion_activacion"] = evo

    # Aparatología
    if not orto_dict.get("aparatologia") or "sin" in str(orto_dict.get("aparatologia")).lower():
        orto_dict["aparatologia"] = "Brackets metálicos (Tratamiento activo)"

    return orto_dict

# ==========================================
# EXTRACTOR DETERMINISTA DE TELÉFONOS DICTADOS
# ==========================================
_CENTENAS_DICTADAS = {
    'cien': 100, 'ciento': 100, 'doscientos': 200, 'doscientas': 200,
    'trescientos': 300, 'trescientas': 300, 'cuatrocientos': 400, 'cuatrocientas': 400,
    'quinientos': 500, 'quinientas': 500, 'seiscientos': 600, 'seiscientas': 600,
    'setecientos': 700, 'setecientas': 700, 'ochocientos': 800, 'ochocientas': 800,
    'novecientos': 900, 'novecientas': 900
}
_NUMEROS_ESPECIALES_DICTADOS = {
    'dieciseis': '16', 'dieciséis': '16', 'diecisiete': '17', 'dieciocho': '18', 'diecinueve': '19',
    'veintiuno': '21', 'veintidos': '22', 'veintidós': '22', 'veintitres': '23', 'veintitrés': '23',
    'veinticuatro': '24', 'veinticinco': '25', 'veintiseis': '26', 'veintiséis': '26',
    'veintisiete': '27', 'veintiocho': '28', 'veintinueve': '29',
    'once': '11', 'doce': '12', 'trece': '13', 'catorce': '14', 'quince': '15'
}
_DECENAS_DICTADAS = {
    'diez': 10, 'veinte': 20, 'treinta': 30, 'cuarenta': 40,
    'cincuenta': 50, 'sesenta': 60, 'setenta': 70, 'ochenta': 80, 'noventa': 90
}
_UNIDADES_DICTADAS = {
    'cero': 0, 'un': 1, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4,
    'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9
}

def normalizar_palabras_numericas(texto: str) -> str:
    """Convierte secuencias de números hablados en español a dígitos numéricos."""
    if not texto:
        return ""
    t = texto.lower()

    # 1. Limpieza de conectores fonéticos y artículos entre dígitos ('el 6 y el 0 y el 0' -> '6 0 0')
    t = re.sub(r'\by\s+(?:el|la)\b', ' ', t)
    t = re.sub(r'\b(?:el|la)\b', ' ', t)

    # 2. Doble y triple
    for palabra, d in [('cero','0'), ('uno','1'), ('dos','2'), ('tres','3'), ('cuatro','4'),
                       ('cinco','5'), ('seis','6'), ('siete','7'), ('ocho','8'), ('nueve','9')]:
        t = re.sub(rf'\bdoble\s+{palabra}\b', f'{d} {d}', t)
        t = re.sub(rf'\btriple\s+{palabra}\b', f'{d} {d} {d}', t)

    # 3. Centenas compuestas y simples
    for c_nom, c_val in _CENTENAS_DICTADAS.items():
        for d_nom, d_val in _DECENAS_DICTADAS.items():
            for u_nom, u_val in _UNIDADES_DICTADAS.items():
                if u_val > 0:
                    t = re.sub(rf'\b{c_nom}\s+{d_nom}\s+y\s+{u_nom}\b', str(c_val + d_val + u_val), t)
                    t = re.sub(rf'\b{c_nom}\s+{d_nom}\s+{u_nom}\b', str(c_val + d_val + u_val), t)
        for esp_nom, esp_str in _NUMEROS_ESPECIALES_DICTADOS.items():
            t = re.sub(rf'\b{c_nom}\s+{esp_nom}\b', str(c_val + int(esp_str)), t)
        for d_nom, d_val in _DECENAS_DICTADAS.items():
            t = re.sub(rf'\b{c_nom}\s+{d_nom}\b', str(c_val + d_val), t)
        for u_nom, u_val in _UNIDADES_DICTADAS.items():
            if u_val > 0:
                t = re.sub(rf'\b{c_nom}\s+{u_nom}\b', str(c_val + u_val), t)
        t = re.sub(rf'\b{c_nom}\b', str(c_val), t)

    # 4. Compuestos especiales (11-29): 'veintiocho' -> '28'
    for k, v in _NUMEROS_ESPECIALES_DICTADOS.items():
        t = re.sub(rf'\b{k}\b', v, t)

    # 5. Decenas compuestas: 'noventa y ocho' -> '98'
    for d_nombre, d_val in _DECENAS_DICTADAS.items():
        for u_nombre, u_val in _UNIDADES_DICTADAS.items():
            if u_val > 0:
                t = re.sub(rf'\b{d_nombre}\s+y\s+{u_nombre}\b', str(d_val + u_val), t)
                t = re.sub(rf'\b{d_nombre}\s+{u_nombre}\b', str(d_val + u_val), t)

    # 6. Decenas simples: 'treinta' -> '30'
    for d_nombre, d_val in _DECENAS_DICTADAS.items():
        t = re.sub(rf'\b{d_nombre}\b', str(d_val), t)

    # 7. Unidades simples: 'cero' -> '0', 'nueve' -> '9'
    for u_nombre, u_val in _UNIDADES_DICTADAS.items():
        t = re.sub(rf'\b{u_nombre}\b', str(u_val), t)

    return t

def extraer_telefono_dictado(texto: str) -> str:
    """
    Extrae un número de teléfono o celular dictado por voz en un comando de cita,
    actualización de contacto o en la historia clínica médica.
    Soporta dígitos directos, con guiones/espacios, o palabras habladas ('cero nueve...').
    Retorna los dígitos limpios o '' si no se detectó teléfono.
    """
    if not texto:
        return ""
    t = normalizar_palabras_numericas(texto)

    # 1. Buscar con prefijo explícito (teléfono, celular, móvil, contacto, whatsapp, cel, al, para)
    patrones_prefijo = [
        r'(?:tel[eé]fono|celular|m[oó]vil|contacto|whatsapp|n[uú]mero|num|tlf|cel)(?:[^\d]{1,40}?)(?:es|al|para|con\s+el|con|de)?\s*[:\-]?\s*([+\d\s\-\.]{7,35})',
        r'(?:con\s+el\s+n[uú]mero|con\s+el|n[uú]mero\s+de\s+tel[eé]fono)\s*[:\-]?\s*([+\d\s\-\.]{7,35})',
        r'(?:al|para)\s+([09]\d[\d\s\-\.]{6,20})'
    ]
    for pat in patrones_prefijo:
        m = re.search(pat, t)
        if m:
            digits = re.sub(r'\D', '', m.group(1))
            if len(digits) == 9 and digits.startswith('9'):
                digits = '0' + digits
            if len(digits) in (7, 8, 9, 10, 11, 12):
                return digits

    # 2. Buscar secuencias de teléfono estándar (móviles 09..., convencionales 02..., o internacionales 593...)
    def compactar_digitos(m):
        return m.group(0).replace(' ', '')
    t_comp = re.sub(r'(?:\b\d{1,4}\s+){2,}\d{1,4}\b', compactar_digitos, t)
    m_cel = re.search(r'\b(09\d{8}|0[2-7]\d{7}|5939\d{8}|593[2-7]\d{7}|9\d{8})\b', t_comp)
    if m_cel:
        val = m_cel.group(1)
        if len(val) == 9 and val.startswith('9'):
            val = '0' + val
        return val

    return ""

def detectar_paciente_en_texto(texto: str) -> dict | None:
    """
    Identifica de forma determinista si en el texto se menciona a un paciente ya registrado
    en la base de datos con verificación de concordancia de nombre completo, cédula y edad.
    Retorna el dict del paciente o None si no hay coincidencia estricta.
    """
    if not texto:
        return None
    try:
        from database import listar_pacientes_por_fecha
        pacientes = listar_pacientes_por_fecha("todos", "")
        if not pacientes:
            return None
        
        t_clean = re.sub(r'[^\w\s]', ' ', texto.lower())
        palabras_texto = set(t_clean.split())
        
        # Detección de edad en el texto para evitar colisiones entre adultos y niños
        m_edad = re.search(r'\b(\d{1,3})\s*a[ñn]os?\b', t_clean)
        edad_dictada = int(m_edad.group(1)) if m_edad else None

        # Detección de cédula en el texto
        m_ced = re.search(r'(?:c[eé]dula|identificaci[oó]n|documento|c\.i\.?)\s*[:\-]?\s*([0-9\s]{8,15})', t_clean)
        ced_dictada = re.sub(r'\D', '', m_ced.group(1)) if m_ced else None
        
        STOP_WORDS = {"el", "la", "los", "las", "de", "del", "a", "al", "para", "por", "con", "en", "que", "es", "un", "una", "paciente", "cita", "telefono", "celular", "numero", "anos", "edad", "dr", "doctor", "bimo"}
        
        candidatos = []
        for p in pacientes:
            nom_p = (p.get("nombre") or "").lower().strip()
            if not nom_p or nom_p in ("paciente", "no especificado"):
                continue
            
            # Si se dictó cédula y el paciente tiene cédula, debe coincidir estrictamente
            p_doc = str(p.get("documento") or "").replace(" ", "").replace("-", "")
            if ced_dictada and p_doc and ced_dictada != p_doc:
                continue

            # Si se dictó edad y el paciente tiene edad registrada, validar compatibilidad
            p_edad = p.get("edad")
            if edad_dictada is not None and p_edad is not None:
                try:
                    if abs(edad_dictada - int(p_edad)) > 3:
                        continue
                except Exception:
                    pass

            # 1. Coincidencia exacta del nombre completo
            if nom_p in t_clean:
                candidatos.append((len(nom_p) * 3, p))
                continue
            
            # 2. Coincidencia de subtokens (requiere al menos 2 palabras clave, jamás 1 sola)
            partes = [w for w in nom_p.split() if len(w) >= 3 and w not in STOP_WORDS]
            if len(partes) >= 2:
                coincidentes = [part for part in partes if part in palabras_texto]
                if len(coincidentes) == len(partes):
                    candidatos.append((sum(len(w) for w in coincidentes) * 2, p))
                elif len(coincidentes) >= 2:
                    candidatos.append((sum(len(w) for w in coincidentes), p))
        
        if candidatos:
            candidatos.sort(key=lambda x: x[0], reverse=True)
            return candidatos[0][1]
    except Exception as e:
        print(f"[DETECTAR PACIENTE ERROR] {e}")
    return None

def extraer_cedula_y_telefono_dictados(texto: str) -> tuple[str | None, str | None]:
    """
    Extrae de forma precisa y desacoplada la cédula ecuatoriana y/o el número de teléfono/celular
    dictados en una misma frase, eliminando colisiones y ambigüedades entre números de 10 dígitos.
    """
    if not texto:
        return None, None
    t = normalizar_palabras_numericas(texto)
    
    # 1. Cédula por ancla léxica explícita
    ced_match = re.search(r'(?:c[eé]dula|identificaci[oó]n|documento|identidad|c\.i\.?)(?:[^\d]{1,30}?)(?:es|al|para|con\s+el|con|del\s+paciente)?\s*[:\-]?\s*([0-9\s]{8,30})', t, re.I)
    ced = None
    if ced_match:
        digits = re.sub(r'\D', '', ced_match.group(1))
        if len(digits) >= 10:
            ced = digits[:10]
        elif len(digits) in (8, 9):
            ced = digits

    # 2. Teléfono por ancla léxica explícita
    tel_match = re.search(r'(?:tel[eé]fono|celular|m[oó]vil|movil|whatsapp|contacto)(?:[^\d]{1,30}?)(?:es|al|para|con\s+el|con)?\s*[:\-]?\s*([0-9\s]{8,30})', t, re.I)
    tel = None
    if tel_match:
        digits = re.sub(r'\D', '', tel_match.group(1))
        if len(digits) >= 10:
            tel = digits[:10]
        elif len(digits) == 9 and digits.startswith('9'):
            tel = '0' + digits
        elif len(digits) in (7, 8, 9):
            tel = digits

    # 3. Si no se anclaron ambos pero hay teléfono general
    if not tel:
        tel = extraer_telefono_dictado(texto)
        if tel and tel == ced:
            if not tel.startswith('09') and not tel.startswith('9'):
                tel = None

    return ced, tel

def resolver_actualizacion_datos_paciente(texto: str) -> dict | None:
    """
    Detecta de forma determinista comandos de voz para agregar o actualizar simultáneamente
    el nombre, la cédula y/o el número de teléfono de un paciente existente o de una cita,
    sin generar consultas ficticias.
    Ejemplos:
    - 'editar paciente Jules Pilataxi la cédula es 1041622100 y el teléfono 0996001234'
    - 'actualizar datos de Jules Pilataxi nombre Jules Mateo Pilataxi cédula 1041622100 y teléfono 0996001234'
    - 'cambiar teléfono de Jules Pilataxi al 0996001234'
    - 'agregar teléfono para la cita de mañana 0996001234'
    """
    if not texto:
        return None
    t = texto.lower()

    # Si el texto es una consulta clínica extensa o contiene descriptores clínicos, NO es una actualización breve de datos
    palabras_clinicas = [
        "consulta", "años", "paciente ", "pieza", "diente", "caries", "dolor", "resina", 
        "plan", "tratamiento", "prótesis", "protesis", "desdentado", "enfilado", "sutura", 
        "alvéolo", "alveolo", "endodoncia", "exodoncia", "profilaxis", "detartraje", 
        "periodontitis", "gingivitis", "acrilizado", "bracket", "ortodoncia", "oclusión", 
        "oclusion", "mordida", "rehabilitación", "rehabilitacion", "examen", "diagnóstico", "diagnostico", "cie-10"
    ]
    if len(t.split()) > 18 or any(pc in t for pc in palabras_clinicas):
        return None

    claves_accion = [
        "actualizar", "cambiar", "corregir", "modificar", "editar", "agregar", 
        "guardar", "poner", "colocar", "registrar", "anotar",
        "nuevo teléfono", "nuevo telefono", "nueva cédula", "nueva cedula", 
        "nuevo número", "nuevo numero", "nuevo nombre"
    ]
    claves_datos = ["teléfono", "telefono", "celular", "contacto", "cédula", "cedula", "documento", "nombre", "datos"]

    if not any(k in t for k in claves_accion):
        return None
    if not any(k in t for k in claves_datos):
        return None

    if any(k in t for k in ["agendar cita", "nueva cita", "programar cita", "motivo de consulta", "diagnóstico", "diagnostico", "examen"]):
        return None

    # Caso Cita Mañana
    es_cita = any(k in t for k in ["cita", "agenda", "recordatorio"])
    if es_cita and any(k in t for k in ["mañana", "manana", "de hoy", "proxima", "próxima"]):
        tel_cita = extraer_telefono_dictado(texto)
        if tel_cita:
            return {
                "tipo": "ACTUALIZAR_DATOS_PACIENTE",
                "para_cita": True,
                "nombre_paciente": "Cita Mañana",
                "telefono": tel_cita,
                "cedula": None,
                "nuevo_nombre": None,
                "mensaje_confirmacion": f"Número de teléfono {tel_cita} registrado para la cita."
            }

    ced_extraida, tel_extraido = extraer_cedula_y_telefono_dictados(texto)

    # Identificar paciente existente en base de datos
    pac = detectar_paciente_en_texto(texto)
    nombre_pac = ""
    pac_id = None
    doc_pac = ""
    if pac:
        nombre_pac = pac.get("nombre", "")
        pac_id = pac.get("id")
        doc_pac = pac.get("documento") or ""
    else:
        m = re.search(r'(?:paciente|para|de|del\s+paciente|a)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)', t)
        if m:
            cands = m.group(1).strip()
            cands = re.sub(r'\b(que|es|el|la|telefono|teléfono|celular|cedula|cédula|numero|número|al|con|y)\b.*', '', cands).strip()
            if cands:
                nombre_pac = _normalizar_nombres_espanol(cands.title())

    if not nombre_pac:
        nombre_pac = "Paciente"

    # Detectar si se dictó un nuevo nombre para el paciente
    nuevo_nombre = None
    m_nom2 = re.search(r'cambia[r]?\s+(?:el\s+)?nombre(?:\s+del?\s+paciente)?(?:\s+de\s+[a-záéíóúñ\s]+?)?\s+(?:por|a)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)', t)
    if m_nom2:
        cands2 = m_nom2.group(1).strip()
        cands2 = re.sub(r'\b(que|es|el|la|telefono|teléfono|celular|cedula|cédula|numero|número|al|con|y|ponle|pon|poniendo)\b.*', '', cands2).strip()
        if cands2 and len(cands2) >= 3:
            nuevo_nombre = _normalizar_nombres_espanol(cands2.title())
    else:
        m_nom = re.search(r'(?:nuevo\s+nombre(?:\s+es)?|nombre\s+correcto(?:\s+es)?|(?:y\s+el|el)\s+nombre(?:\s+es)?)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)', t)
        if m_nom:
            cands = m_nom.group(1).strip()
            m_sub = re.match(r'^(?:del?\s+paciente\s+|de\s+[a-záéíóúñ\s]+?\s+)(?:por|a)\s+(.*)', cands)
            if m_sub:
                cands = m_sub.group(1).strip()
            cands = re.sub(r'\b(que|es|el|la|telefono|teléfono|celular|cedula|cédula|numero|número|al|con|y|ponle|pon|poniendo)\b.*', '', cands).strip()
            if cands and len(cands) >= 3:
                nom_cand = _normalizar_nombres_espanol(cands.title())
                if nom_cand.lower() != nombre_pac.lower():
                    nuevo_nombre = nom_cand

    if not ced_extraida and not tel_extraido and not nuevo_nombre:
        return None

    partes_conf = []
    if nuevo_nombre:
        partes_conf.append(f"Nombre: {nuevo_nombre}")
    if ced_extraida:
        partes_conf.append(f"Cédula: {ced_extraida}")
    if tel_extraido:
        partes_conf.append(f"Teléfono: {tel_extraido}")

    nombre_referencia = nuevo_nombre or nombre_pac
    msg = f"Datos de {nombre_referencia} actualizados: {', '.join(partes_conf)}."

    return {
        "tipo": "ACTUALIZAR_DATOS_PACIENTE",
        "para_cita": False,
        "paciente_id": pac_id,
        "nombre_paciente": nombre_pac,
        "nuevo_nombre": nuevo_nombre,
        "documento": doc_pac,
        "cedula": ced_extraida,
        "telefono": tel_extraido,
        "mensaje_confirmacion": msg
    }

def resolver_actualizacion_contacto(texto: str) -> dict | None:
    """Mantiene compatibilidad delegando en resolver_actualizacion_datos_paciente."""
    return resolver_actualizacion_datos_paciente(texto)

def resolver_comando_whatsapp(texto: str) -> dict | None:
    """
    Detecta de forma determinista comandos de voz para envío de recordatorios o mensajes de WhatsApp.
    Ejemplos:
    - 'enviar recordatorio de whatsapp a Jackeline'
    - 'notificar por whatsapp a los pacientes de mañana'
    - 'recordatorios de whatsapp de mañana'
    """
    if not texto:
        return None
    t = texto.lower()
    if not any(k in t for k in ["whatsapp", "guasap", "watsap", "wasap"]):
        return None

    # Caso 1: Lote de citas de mañana / todos los pacientes
    if any(k in t for k in ["mañana", "manana", "todas las citas", "todos los pacientes", "lote"]):
        return {
            "tipo": "COMANDO_WHATSAPP",
            "accion": "recordatorio_lote_manana",
            "nombre_paciente": "todos",
            "mensaje_confirmacion": "Procesando envío de recordatorios de WhatsApp para los pacientes de mañana..."
        }

    # Caso 2: Paciente específico
    nombre = ""
    m_after = re.search(r'(?:whatsapp|guasap|wasap|watsap)(?:\s+(?:de\s+confirmacion|de\s+asistencia|de\s+cita|recordatorio))?\s+(?:a|para|al|al\s+paciente|a\s+la\s+paciente)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*)', t)
    if m_after and m_after.group(1).strip():
        nombre = m_after.group(1).strip()
    else:
        m_before = re.search(r'(?:a|para)\s+([a-záéíóúñ]+(?:\s+[a-záéíóúñ]+)*?)(?=\s+(?:por\s+whatsapp|por\s+guasap|por\s+wasap|al\s+whatsapp|$))', t)
        if m_before and m_before.group(1).strip():
            nombre = m_before.group(1).strip()

    nombre = re.sub(r'^(?:al\s+|a\s+|para\s+|de\s+|el\s+|la\s+|paciente\s+)+', '', nombre).strip()
    nombre = re.sub(r'\b(whatsapp|guasap|wasap|watsap|recordatorio|cita|favor|por)\b', '', nombre, flags=re.IGNORECASE).strip()
    nombre = nombre.title() if nombre else "No especificado"

    nom_final = _normalizar_nombres_espanol(nombre) if nombre and nombre != "No especificado" else "No especificado"

    return {
        "tipo": "COMANDO_WHATSAPP",
        "accion": "recordatorio_cita",
        "nombre_paciente": nom_final,
        "mensaje_confirmacion": f"Preparando recordatorio de WhatsApp para {nom_final}..."
    }

def resolver_comando_hora(texto_crudo: str) -> dict:
    """
    Detecta determinísticamente preguntas sobre la hora actual con 0ms de latencia y sin costo de tokens.
    Responde con frase natural en español y formato digital.
    """
    if not texto_crudo:
        return None

    t = texto_crudo.lower().strip()
    t_limpio = re.sub(r'^(?:bimo|vimo|hola|oye|hey|ok|favor|por favor)\b[\s,]*', '', t).strip()

    patrones_hora = [
        r'\bqu[eé]\s+hora\s+(?:es|tienes|ser[aá]|tenemos)\b',
        r'\bdime\s+la\s+hora\b',
        r'\b(?:la\s+)?hora\s+actual\b',
        r'\btienes\s+la\s+hora\b',
        r'\bme\s+dices\s+la\s+hora\b',
        r'\bqu[eé]\s+horas?\s+son\b',
        r'\bdar\s+la\s+hora\b',
        r'\bhora\s+por\s+favor\b',
        r'\bqu[eé]\s+tiempo\s+es\b',
        r'^la\s+hora$'
    ]

    if any(re.search(pat, t) or re.search(pat, t_limpio) for pat in patrones_hora):
        ahora = datetime.datetime.now()
        h = ahora.hour
        m = ahora.minute

        periodo = "de la mañana" if h < 12 else ("de la tarde" if h < 19 else "de la noche")
        h12 = h % 12
        if h12 == 0:
            h12 = 12

        prefijo = "Es la" if h12 == 1 else "Son las"
        if m == 0:
            min_str = "en punto"
        elif m == 15:
            min_str = "y cuarto"
        elif m == 30:
            min_str = "y media"
        else:
            min_str = f"y {m}"

        frase_voz = f"{prefijo} {h12} {min_str} {periodo}."
        hora_digital = ahora.strftime("%I:%M %p").lstrip("0")

        return {
            "tipo": "COMANDO_HORA",
            "hora": hora_digital,
            "hora_24": ahora.strftime("%H:%M"),
            "frase": frase_voz,
            "mensaje": f"Son las {hora_digital}"
        }
    return None

def resolver_comando_agendar_cita(texto_crudo: str) -> dict | None:
    """
    Detecta y resuelve determinísticamente comandos verbales de agendamiento de citas con 0ms de latencia y 0 costo de tokens:
    - 'Bimo genera una cita para el último paciente en 3 días a las 10:00'
    - 'Bimo agenda una cita para Sisa Llumiquinga' (activa slot-filling pidiendo fecha/hora)
    - 'crea una cita para Juan Pérez mañana a las 10'
    - 'cita para el último paciente el viernes a las 15:00'
    """
    if not texto_crudo:
        return None

    t = texto_crudo.lower().strip()

    # REGLA DE PROTECCIÓN: Si el texto describe una consulta clínica odontológica completa,
    # descartar para permitir la estructuración de la consulta completa con IA y odontograma.
    indicadores_hc = (
        "consulta por", "acude por", "diagnóstico", "diagnostico", "cie-10",
        "examen clínico", "pieza ", "piezas ", "años, cédula", "anos, cedula",
        "síntoma", "sintoma", "plan de tratamiento", "tratamiento con",
        "restauración con", "restauracion con", "obturación", "obturacion",
        "prescripción", "prescripcion", "radiografía", "radiografia",
        "caries", "pulpar", "fractura", "detartraje", "profilaxis", "exodoncia"
    )
    if any(ind in t for ind in indicadores_hc):
        return None

    # Limpiar prefijos de invocación habituales
    t_limpio = re.sub(r'^(?:bimo|vimo|hola|oye|hey|ok|favor|por favor)\b[\s,]*', '', t).strip()

    # Patrón general de agendamiento
    patron_cita = r'\b(?:genera|generar|agenda|agendar|crea|crear|programa|programar|separa|separar|haz|hacer|pon|poner)\s+(?:una\s+)?cita\s+(?:para|a|con)\s+(.+)$'
    m = re.search(patron_cita, t_limpio, flags=re.IGNORECASE)
    if not m:
        m = re.search(r'^cita\s+(?:para|a|con)\s+(.+)$', t_limpio, flags=re.IGNORECASE)

    if not m:
        return None

    resto = m.group(1).strip()

    # 1. Determinar si el objetivo es 'el último paciente'
    es_ultimo = any(u in resto.lower() for u in (
        "último paciente", "ultimo paciente", "la última", "la ultima",
        "el ultimo", "el último", "al último", "al ultimo"
    )) or any(u in t for u in ("último paciente", "ultimo paciente", "la última paciente", "el último paciente"))

    # 2. Extraer nombre del paciente
    if es_ultimo:
        nombre_paciente = "el último paciente"
    else:
        partes_temp = re.split(r'\b(?:en\s+\d+|mañana|manana|hoy|el\s+(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo|pr[oó]ximo)|a\s+las\s+\d+|para\s+el\s+\d+|dentro\s+de)\b', resto, flags=re.IGNORECASE)
        raw_nom = partes_temp[0].strip() if partes_temp else resto
        raw_nom = re.sub(r'[,\.]', '', raw_nom).strip()
        nombre_paciente = _normalizar_nombres_espanol(raw_nom.title()) if raw_nom else "el último paciente"

    # 3. Resolver fecha y hora con el algoritmo matemático determinista
    tiene_tiempo = contiene_especificacion_temporal(texto_crudo)
    f_calc = resolver_fecha_relativa_espanol(texto_crudo)

    if f_calc:
        fecha_hora = f_calc
        requiere_fecha_hora = False
        msg_conf = f"Cita agendada para {nombre_paciente} el {fecha_hora}"
    else:
        fecha_hora = None
        requiere_fecha_hora = True
        msg_conf = f"¿Para qué fecha y hora deseas la cita para {nombre_paciente}?"

    tel = extraer_telefono_dictado(texto_crudo) or "No especificado"

    return {
        "tipo": "COMANDO_CITA",
        "nombre_paciente": nombre_paciente,
        "fecha_hora": fecha_hora,
        "requiere_fecha_hora": requiere_fecha_hora,
        "motivo": "Consulta agendada por voz",
        "telefono": tel,
        "mensaje_confirmacion": msg_conf
    }

def procesar_comando_o_dictado(texto_crudo: str) -> dict:
    # 0. Verificación determinista instantánea de comando de hora
    cmd_hora = resolver_comando_hora(texto_crudo)
    if cmd_hora:
        return cmd_hora

    # 0.05 Verificación determinista instantánea de agendamiento de citas (0ms, 0 tokens)
    cmd_cita = resolver_comando_agendar_cita(texto_crudo)
    if cmd_cita:
        return cmd_cita

    # 0.1 Verificación determinista de reprogramación relativa de citas
    rep_rel = resolver_reprogramacion_relativa(texto_crudo)
    if rep_rel:
        return rep_rel

    # 0.2 Verificación determinista de comandos WhatsApp
    cmd_wa = resolver_comando_whatsapp(texto_crudo)
    if cmd_wa:
        return cmd_wa

    # 0.3 Verificación determinista de actualización de datos de paciente (nombre, cédula, teléfono)
    act_datos = resolver_actualizacion_datos_paciente(texto_crudo)
    if act_datos:
        return act_datos

    api_key = get_groq_api_key()
    modelo = get_groq_model()
    cliente = Groq(api_key=api_key)

    prompt = f"""Eres BIMO, el asistente clínico y copiloto odontológico de élite.
Fecha actual: {datetime.date.today().isoformat()}

Analiza la siguiente transcripción dictada por el profesional.
REGLAS ESTRICTAS DE IDIOMA Y NOMBRES EN ESPAÑOL:
- Estás en un consultorio odontológico hispanohablante en Ecuador/Latinoamérica.
- NUNCA uses terminaciones extranjeras o italianas para nombres comunes en español.
- Si escuchas 'Sebastiano', SIEMPRE debe ser 'Sebastián'.
- Si escuchas 'Matteo', SIEMPRE debe ser 'Mateo'.
- Si escuchas 'Stefania', SIEMPRE debe ser 'Estefanía'.
- Todos los nombres deben conservar sus tildes y ortografía correcta (ej. Sebastián, Mateo, Valdés, Ramírez, González).

REGLA DE ORO DE NOMBRES ANDINOS Y KICHWAS:
Preserva y normaliza con máxima precisión la ortografía canónica de nombres y apellidos andinos, kichwas y latinoamericanos.
Si la transcripción contiene variaciones fonéticas o aproximaciones acústicas comunes de Whisper, corrígelas a su ortografía correcta:
- 'yumi kinga' / 'yumikinga' / 'llumi kinga' -> 'Llumiquinga'
- 'huaminga' / 'waminga' -> 'Guaminga'
- 'kispe' / 'kizpe' -> 'Quispe'
- 'tuapanta' -> 'Toapanta'
- 'guaman' -> 'Guamán'
- 'chiluisa' -> 'Chiluisa'
- 'chushig' -> 'Chushig'
- 'simbana' -> 'Simbaña'
- 'tituana' -> 'Tituaña'
- 'pilatagsi' / 'pilataxi' -> 'Pilataxi'
- 'chuquimarca' -> 'Chuquimarca'
- 'rumiñahui' / 'ruminahui' -> 'Rumiñahui'
- 'sisa' -> 'Sisa'
- 'inti' -> 'Inti'
- 'tupac' -> 'Tupac'

REGLA ESPECIAL PARA CITAS Y ÚLTIMO PACIENTE:
- Si el usuario dice 'el último paciente', 'la última paciente', 'último paciente atendido' o 'al último', pon estrictamente 'nombre_paciente': 'el último paciente'.
- Si el usuario solicita agendar una cita pero NO especifica fecha ni hora en el audio (ej: 'genera una cita para el último paciente', 'agenda una cita para Juan'):
  pon 'fecha_hora': null y 'requiere_fecha_hora': true. NUNCA inventes una fecha u hora si no fue dictada.

REGLAS ESTRICTAS DE FILIACIÓN CLÍNICA:
- Si el doctor no dicta el sexo, infiérelo por el nombre (Femenino para mujeres, Masculino para hombres). Si no es evidente, pon 'No especificado'.
- Si el doctor no dicta teléfono ni contacto, pon siempre 'No especificado'. El teléfono NUNCA es obligatorio.
- Si el doctor no dicta cédula, pon 'No especificado'.
- Si se dictan extracciones realizadas, dientes sacados o perdidos, regístralos en 'odontograma' con el hallazgo 'Extracción previa / Ausente' para pintarse en gris.

REGLAS OBLIGATORIAS DE EXTRACCIÓN CLÍNICA:
- 'edad': Extrae la edad en años enteros (ej. '16 años', '25 años'). Si el usuario dice '16 años', 'dieciséis años' o 'diez y seis años', escribe estrictamente '16 años'. NUNCA pongas '10 años y 6 meses' a menos que sea explícitamente un lactante menor a 2 años.
- 'odontograma': Para CADA pieza dental mencionada, en 'pieza_dental' debes colocar SIEMPRE su NÚMERO FDI (ej: '14', '16', '21', '24', '36', '46'). Si el doctor dice 'premolar superior derecho' conviértelo a '14'; si dice 'premolar superior izquierdo' a '24'; si dice 'premolar inferior izquierdo' a '34'; si dice 'molar superior derecho' o 'muela superior derecha' a '16'; si dice 'molar inferior izquierdo' o 'muela inferior izquierda' a '36'.
- 'pagos': Si el doctor menciona costo del tratamiento, abono o saldo (ej: 'el tratamiento cuesta 150 dólares, se agrega un abono de 50 y queda 100 restante', 'costo 200, abono 50', 'costo 80 cancelado'):
  "pagos": {{
      "costo_total": 150.0,
      "abono": 50.0,
      "saldo_pendiente": 100.0,
      "estado": "Saldo Pendiente" (o "Cancelado" si saldo <= 0),
      "metodo_pago": "Efectivo / Transferencia / Tarjeta / No especificado",
      "notas": "Concepto o detalle del tratamiento"
  }}
  Si no se dictan pagos, escribe "pagos": {{ "costo_total": 0.0, "abono": 0.0, "saldo_pendiente": 0.0, "estado": "Cancelado", "metodo_pago": "No especificado", "notas": "Sin registro de pagos" }}

DETECCIÓN DE CITAS FUTURAS DENTRO DE HISTORIA CLÍNICA:
- Si mientras se dicta la historia clínica el doctor menciona una próxima cita o control (ej: 'dejamos cita para dentro de 15 días', 'control en 30 días', 'cita el próximo martes a las 3', 'lo veo en un mes'), activa obligatoriamente en 'cita_programada':
  "cita_programada": {{
      "agendar": true,
      "fecha_hora": "AAAA-MM-DD HH:MM estimada calculada según la fecha actual",
      "dias_relativos": número de días mencionado (ej. 15, 30) o null,
      "motivo": "Control post-tratamiento / Próxima sesión"
  }}
  Asume SIEMPRE que la cita corresponde al MISMO paciente de la historia clínica.

REGLA OBLIGATORIA DE APROBACIÓN DE ORTODONCIA:
- Si el doctor indica que 'se aprueba ortodoncia', 'aprobado para ortodoncia', 'aprobada la ortodoncia', 'ortodoncia aprobada', 'iniciar ortodoncia' o colocación de brackets:
  1. En 'plan_tratamiento', incluye: 'Tratamiento de ortodoncia aprobado (aparatología fija / brackets)'.
  2. En 'evaluacion_ortodoncia', NUNCA pongas 'Sin aparatología'; coloca 'Brackets metálicos' o aparatología indicada, con 'clase_angle' y 'alineacion' acordes.

Analiza la siguiente transcripción de voz y clasifícala estrictamente en una de las siguientes intenciones:
1. COMANDO_CITA: Si el usuario solicita agendar, programar, generar, crear, separar o sacar una cita (ej: 'genera una cita para...', 'crea una cita para...', 'agenda una cita para...', 'haz una cita para...', 'cita para...'). ATENCIÓN CRÍTICA: Si el texto contiene síntomas, motivo de consulta, piezas dentales, examen, diagnóstico CIE-10 o plan de tratamiento, NUNCA debe ser COMANDO_CITA; es OBLIGATORIAMENTE HISTORIA_CLINICA.
2. CANCELAR_CITA: Si el doctor solicita cancelar o eliminar citas.
3. REPROGRAMAR_CITA: Si el doctor solicita cambiar o mover una cita.
4. ACTUALIZAR_DATOS_PACIENTE: ÚNICAMENTE cuando se trate de una instrucción verbal directa y breve para modificar o corregir datos de contacto (ej: 'cambia el teléfono de María a 0991234567', 'actualiza la cédula de Juan', 'el nuevo número es 098...'). NUNCA selecciones esto si el texto describe una consulta clínica, dolor, examen, diagnóstico, piezas dentales o tratamiento.
5. CONSULTA_MEDICA: Si el doctor hace una pregunta puntual médica o farmacológica (máximo 2 oraciones).
6. HISTORIA_CLINICA: Si el doctor está dictando una consulta clínica dental (síntomas, motivo, examen clínico, piezas dentales, diagnóstico CIE-10, plan de tratamiento, ortodoncia o indicaciones). ATENCIÓN: Es MUY COMÚN que el doctor comience dictando la filiación completa ('Paciente [Nombre], [Edad] años, cédula [X], teléfono [Y]... Consulta por...') y que al final mencione una próxima cita o control (ej: 'cita en 15 días'). En todos esos casos, la intención es OBLIGATORIAMENTE HISTORIA_CLINICA (la cita futura se guarda dentro del campo 'cita_programada', NUNCA clasificar la consulta general como COMANDO_CITA).
7. IGNORAR: Si el audio trata sobre cualquier tema ajeno a la odontología, medicina o citas clínicas.

Devuelve ÚNICAMENTE un formato JSON válido según la intención:

Si es COMANDO_CITA:
{{
    "tipo": "COMANDO_CITA",
    "nombre_paciente": "Nombre explícito del paciente mencionado o 'No especificado'",
    "fecha_hora": "AAAA-MM-DD HH:MM estimada",
    "motivo": "Motivo de la cita",
    "telefono": "Teléfono o celular del paciente si fue dictado (ej. '0991234567'), o 'No especificado'",
    "mensaje_confirmacion": "Cita detectada"
}}

Si es ACTUALIZAR_DATOS_PACIENTE:
{{
    "tipo": "ACTUALIZAR_DATOS_PACIENTE",
    "nombre_paciente": "Nombre del paciente o 'Cita'",
    "nuevo_nombre": null,
    "cedula": null,
    "telefono": "Teléfono o celular dictado",
    "para_cita": false,
    "mensaje_confirmacion": "Datos de paciente detectados"
}}

Si es CANCELAR_CITA:
{{
    "tipo": "CANCELAR_CITA",
    "nombre_paciente": "Nombre del paciente a cancelar o 'No especificado'",
    "fecha": "Fecha si se mencionó o 'No especificado'",
    "mensaje_confirmacion": "Solicitud de cancelación detectada"
}}

Si es REPROGRAMAR_CITA (ej. "corrige la cita de...", "cambia la cita de...", "reprograma la cita...", "no puede para ese día sino el...", "muévela para...", "para el ... entonces"):
{{
    "tipo": "REPROGRAMAR_CITA",
    "nombre_paciente": "Nombre del paciente a reprogramar o 'No especificado'",
    "fecha_hora": "AAAA-MM-DD HH:MM nueva fecha y hora solicitada",
    "motivo": "Motivo de la cita o consulta",
    "mensaje_confirmacion": "Cita reprogramada detectada"
}}

Si es CONSULTA_MEDICA:
{{
    "tipo": "CONSULTA_MEDICA",
    "respuesta_asistente": "Respuesta médica precisa, técnica y concisa (máximo 2 oraciones para voz alta)"
}}

Si es IGNORAR:
{{
    "tipo": "IGNORAR",
    "respuesta_asistente": ""
}}

Si es HISTORIA_CLINICA:
{{
    "tipo": "HISTORIA_CLINICA",
    "datos_filiacion": {{
        "nombre": "No especificado",
        "edad": "No especificado",
        "sexo": "Femenino / Masculino / No especificado",
        "documento": "No especificado",
        "telefono": "Teléfono o celular del paciente si fue dictado (ej. '0991234567'), o 'No especificado'",
        "ocupacion": "No especificado",
        "direccion": "No especificado",
        "contacto_emergencia": "No especificado",
        "medico_cabecera": "No especificado"
    }},
    "motivo_consulta": "No especificado",
    "enfermedad_actual": "No especificado",
    "antecedentes": {{
        "enfermedades_sistemicas": "No especificado",
        "alergias": "No especificado",
        "medicamentos": "No especificado",
        "trastornos_coagulacion": "No especificado",
        "cirugias_previas": "No especificado"
    }},
    "examen_extraoral": "No especificado",
    "examen_intraoral": "No especificado",
    "evaluacion_ortodoncia": {{
        "clase_angle": "Clase I (Normo-oclusión) / Clase II / Clase III / No evaluada",
        "mordida": "Normo-oclusión / Mordida profunda / Mordida abierta / Mordida cruzada / No especificado",
        "alineacion": "Alineada / Apiñamiento / Diastemas / No especificado",
        "aparatologia": "Sin aparatología / Brackets / Alineadores / Retenedores"
    }},
    "odontograma": [
        {{
            "pieza_dental": "Pieza 21",
            "procedimientos_o_hallazgos": ["Hallazgo explícito dictado"]
        }}
    ],
    "indices_higiene": {{
        "placa_bacteriana": "No especificado",
        "sangrado_gingival": "No especificado"
    }},
    "diagnostico": "No especificado",
    "plan_tratamiento": "No especificado",
    "pagos": {{
        "costo_total": 0.0,
        "abono": 0.0,
        "saldo_pendiente": 0.0,
        "estado": "Cancelado",
        "metodo_pago": "Efectivo",
        "notas": ""
    }},
    "cita_programada": {{
        "agendar": false,
        "fecha_hora": "No especificado",
        "motivo": "No especificado"
    }}
}}

Texto dictado:
"{texto_crudo}"
"""

    try:
        modelos_candidatos = [modelo]
        for m_fb in ("openai/gpt-oss-20b", "qwen/qwen3.8-27b"):
            if m_fb not in modelos_candidatos:
                modelos_candidatos.append(m_fb)

        respuesta = None
        ultimo_error = None
        modelo_activo = modelo

        for m_actual in modelos_candidatos:
            for intento in range(2):
                try:
                    respuesta = cliente.chat.completions.create(
                        model=m_actual,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.0,
                        response_format={"type": "json_object"},
                        timeout=25.0
                    )
                    modelo_activo = m_actual
                    break
                except Exception as e_groq:
                    ultimo_error = e_groq
                    err_str = str(e_groq).lower()
                    if ("429" in err_str or "rate limit" in err_str):
                        print(f"[GROQ RATE LIMIT] Modelo {m_actual} con límite de tokens. Pasando a modelo de respaldo...")
                        break
                    else:
                        time.sleep(1.5)
            if respuesta:
                break

        if not respuesta:
            raise ultimo_error or Exception("No se pudo obtener respuesta de ningún modelo de IA")

        contenido = respuesta.choices[0].message.content
        resultado = json.loads(contenido)

        # REGLA DE ROBUSTEZ: Si el clasificador devolvió COMANDO_CITA o ACTUALIZAR_DATOS_PACIENTE
        # pero el dictado contiene estructura clínica evidente (diagnóstico, piezas, plan, etc.),
        # reencaminar obligatoriamente a HISTORIA_CLINICA.
        indicadores_hc = (
            "diagnóstico", "diagnostico", "cie-10", "plan de tratamiento", "examen clínico",
            "pieza ", "piezas ", "acude por", "consulta por", "años, cédula", "anos, cedula",
            "caries", "pulpar", "fractura", "detartraje", "profilaxis", "exodoncia", "resina"
        )
        t_low = texto_crudo.lower()
        if resultado.get("tipo") in ("COMANDO_CITA", "ACTUALIZAR_DATOS_PACIENTE") and any(ind in t_low for ind in indicadores_hc):
            print(f"[AI ENGINE] Dictado clínico profundo reclasificado de {resultado.get('tipo')} a HISTORIA_CLINICA...")
            prompt_hc = prompt + "\n\nINSTRUCCIÓN CRÍTICA DE RECLASIFICACIÓN: El texto describe una consulta clínica odontológica completa con examen, diagnóstico y tratamiento. Devuelve OBLIGATORIAMENTE el JSON con 'tipo': 'HISTORIA_CLINICA' estructurando todos los campos clínicos y odontograma."
            for intento_hc in range(2):
                try:
                    resp_hc = cliente.chat.completions.create(
                        model=modelo_activo,
                        messages=[{"role": "user", "content": prompt_hc}],
                        temperature=0.0,
                        response_format={"type": "json_object"},
                        timeout=25.0
                    )
                    resultado = json.loads(resp_hc.choices[0].message.content)
                    break
                except Exception as e_re:
                    for m_alt in ("openai/gpt-oss-20b", "qwen/qwen3.8-27b"):
                        if m_alt != modelo_activo:
                            try:
                                resp_hc = cliente.chat.completions.create(
                                    model=m_alt,
                                    messages=[{"role": "user", "content": prompt_hc}],
                                    temperature=0.0,
                                    response_format={"type": "json_object"},
                                    timeout=25.0
                                )
                                resultado = json.loads(resp_hc.choices[0].message.content)
                                break
                            except Exception:
                                pass
                    break

        # Post-procesamiento amigable de filiación y normalización en español
        if resultado.get("tipo") == "HISTORIA_CLINICA":
            fil = resultado.get("datos_filiacion", {})
            nom = _normalizar_nombres_espanol(fil.get("nombre", ""))
            fil["nombre"] = nom
            fil["documento"] = sanitizar_cedula(fil.get("documento", ""))
            fil["edad"] = _limpiar_edad_dictada(fil.get("edad", ""), texto_crudo)
            sex = fil.get("sexo", "No especificado")
            if not sex or sex.lower() in ("no especificado", "none", ""):
                fil["sexo"] = _inferir_sexo_por_nombre(nom)
            if not fil.get("contacto_emergencia") or fil.get("contacto_emergencia").lower() in ("none", ""):
                fil["contacto_emergencia"] = "No especificado"

            # Extracción o rescate determinista de teléfono si fue dictado
            tel_fil = str(fil.get("telefono") or "").strip()
            if not tel_fil or tel_fil.lower() in ("no especificado", "none", ""):
                tel_det = extraer_telefono_dictado(texto_crudo)
                if tel_det:
                    fil["telefono"] = tel_det
            else:
                digits_f = re.sub(r'\D', '', tel_fil)
                if len(digits_f) in (7, 8, 9, 10, 11, 12):
                    fil["telefono"] = digits_f

            # Normalizar piezas en odontograma al estándar FDI
            from generador_pdf import extraer_fdi
            odonto = resultado.get("odontograma", [])
            if isinstance(odonto, list):
                for item in odonto:
                    if isinstance(item, dict):
                        p_raw = item.get("pieza_dental") or item.get("pieza") or item.get("diente") or ""
                        fdi_calc = extraer_fdi(p_raw)
                        if fdi_calc:
                            item["pieza_dental"] = fdi_calc

            # CÁLCULO MATEMÁTICO EXACTO DE CITAS A FUTURO EN PYTHON (Evita alucinaciones del LLM)
            f_calc = resolver_fecha_relativa_espanol(texto_crudo)
            cita_obj = resultado.setdefault("cita_programada", {})
            if f_calc:
                cita_obj["agendar"] = True
                cita_obj["fecha_hora"] = f_calc
            elif "en un mes" in texto_crudo.lower() or "un mes" in texto_crudo.lower():
                dt_calc = datetime.datetime.now() + datetime.timedelta(days=30)
                cita_obj["agendar"] = True
                cita_obj["dias_relativos"] = 30
                cita_obj["fecha_hora"] = dt_calc.strftime("%Y-%m-%d 10:00:00")

            if fil.get("telefono") and fil.get("telefono") != "No especificado":
                cita_obj["telefono"] = fil.get("telefono")

            # Garantizar diagnóstico y plan de tratamiento robustos
            if not resultado.get("diagnostico") or str(resultado.get("diagnostico")).strip().lower() in ("no especificado", "none", ""):
                m_diag = re.search(r'diagn[oó]stico\s+([^\.]+)', texto_crudo, re.IGNORECASE)
                resultado["diagnostico"] = m_diag.group(1).strip() if m_diag else "Evaluación clínica general"

            if not resultado.get("plan_tratamiento") or str(resultado.get("plan_tratamiento")).strip().lower() in ("no especificado", "none", ""):
                m_plan = re.search(r'plan\s+(?:de\s+tratamiento\s+)?([^\.]+)', texto_crudo, re.IGNORECASE)
                resultado["plan_tratamiento"] = m_plan.group(1).strip() if m_plan else "Tratamiento odontológico integral"

            # Extracción y cálculo matemático estricto de honorarios y pagos
            resultado["pagos"] = _extraer_y_calcular_pagos(resultado.get("pagos", {}), texto_crudo)

            # Detección y estructuración profunda de Ortodoncia
            t_low = texto_crudo.lower()
            palabras_orto = [
                "ortodoncia", "bracket", "frenillo", "alineador", "perfil ", "biotipo",
                "dolicofacial", "braquifacial", "mesofacial", "habito", "hábito", "respirador bucal",
                "interposicion", "interposición", "deglucion", "deglución", "fase 1", "fase 2",
                "fase 3", "fase 4", "fase i", "fase ii", "fase iii", "fase iv", "activacion", "activación",
                "arcos niti", "arco niti", "arcos de acero", "se aprueba ortodoncia", "aprobada la ortodoncia"
            ]
            if any(k in t_low for k in palabras_orto):
                resultado["incluir_ortodoncia"] = True
                resultado["evaluacion_ortodoncia"] = _enriquecer_evaluacion_ortodoncia(resultado.get("evaluacion_ortodoncia", {}), texto_crudo)
                
                plan_t = resultado.get("plan_tratamiento", "")
                if not plan_t or plan_t == "No especificado":
                    resultado["plan_tratamiento"] = "Tratamiento de ortodoncia activo con aparatología fija."
                elif "ortodoncia" not in plan_t.lower():
                    resultado["plan_tratamiento"] = f"{plan_t}. Tratamiento de ortodoncia activo con aparatología fija."

        elif resultado.get("tipo") in ("COMANDO_CITA", "CANCELAR_CITA", "REPROGRAMAR_CITA"):
            raw_nom = resultado.get("nombre_paciente", "")
            raw_nom = re.sub(r'\s+(?:al|para|tel[eé]fono|celular|con|de)?\s*[+\d\-\s\.]{6,20}$', '', raw_nom, flags=re.IGNORECASE).strip()
            
            # Soporte determinista para 'el último paciente'
            if any(u in raw_nom.lower() for u in ("último paciente", "ultimo paciente", "la última", "la ultima", "el ultimo", "el último", "último", "ultimo")) or any(u in texto_crudo.lower() for u in ("último paciente", "ultimo paciente", "la última", "la ultima", "el ultimo", "el último")):
                nom = "el último paciente"
            else:
                nom = _normalizar_nombres_espanol(raw_nom)
            resultado["nombre_paciente"] = nom
            
            # Resolver fecha y hora con el algoritmo matemático determinista
            tiene_tiempo = contiene_especificacion_temporal(texto_crudo)
            f_calc = resolver_fecha_relativa_espanol(texto_crudo)
            if f_calc:
                resultado["fecha_hora"] = f_calc
                resultado["requiere_fecha_hora"] = False
            elif tiene_tiempo and resultado.get("fecha_hora") and resultado.get("fecha_hora") not in ("No especificado", "null", "None"):
                resultado["requiere_fecha_hora"] = False
            else:
                resultado["fecha_hora"] = None
                resultado["requiere_fecha_hora"] = True
                resultado["mensaje_confirmacion"] = f"¿Para qué fecha y hora deseas la cita para {nom}?"

            # Extracción determinista de teléfono para la cita
            tel_cita = str(resultado.get("telefono") or "").strip()
            if not tel_cita or tel_cita.lower() in ("no especificado", "none", ""):
                tel_det = extraer_telefono_dictado(texto_crudo)
                if tel_det:
                    resultado["telefono"] = tel_det
            else:
                digits_c = re.sub(r'\D', '', tel_cita)
                if len(digits_c) in (7, 8, 9, 10, 11, 12):
                    resultado["telefono"] = digits_c

        elif resultado.get("tipo") in ("ACTUALIZAR_DATOS_PACIENTE", "ACTUALIZAR_CONTACTO_PACIENTE"):
            indicadores_clinicos = (
                "consulta por", "diagnóstico", "diagnostico", "cie-10", "plan", 
                "pieza ", "diente", "caries", "dolor", "resina", "endodoncia", "exodoncia",
                "periodontitis", "detartraje", "profilaxis", "sutura", "alvéolo", "alveolo",
                "examen clínico", "examen clinico", "reconstrucción", "reconstruccion",
                "tratamiento", "k0", "s0", "z4", "ortodoncia", "brackets"
            )
            t_min = texto_crudo.lower()
            if any(ind in t_min for ind in indicadores_clinicos):
                print("[IA] Consulta clínica detectada en ACTUALIZAR_DATOS_PACIENTE. Re-encaminando a HISTORIA_CLINICA...")
                prompt_reintento = prompt.replace(
                    "Analiza la siguiente transcripción de voz y clasifícala estrictamente en una de las siguientes intenciones:",
                    "Analiza la siguiente transcripción de voz sabiendo que es OBLIGATORIAMENTE una HISTORIA_CLINICA:"
                )
                try:
                    resp_re = cliente.chat.completions.create(
                        model=modelo,
                        messages=[{"role": "user", "content": prompt_reintento}],
                        temperature=0.0,
                        response_format={"type": "json_object"},
                        timeout=25.0
                    )
                    resultado = json.loads(resp_re.choices[0].message.content)
                    resultado["tipo"] = "HISTORIA_CLINICA"
                except Exception as e_retry:
                    print(f"[IA WARN] Error al reintentar HISTORIA_CLINICA: {e_retry}")
                    resultado["tipo"] = "HISTORIA_CLINICA"
                    resultado.setdefault("datos_filiacion", {})["nombre"] = resultado.get("nombre_paciente") or "Paciente_Consulta"
                    resultado.setdefault("datos_filiacion", {})["documento"] = resultado.get("cedula") or ""
                    resultado.setdefault("datos_filiacion", {})["telefono"] = resultado.get("telefono") or ""
                    resultado["motivo_consulta"] = texto_crudo
                    resultado["diagnostico"] = "Consulta estructurada por rescate"
                    resultado["plan_tratamiento"] = "Evaluación clínica"
                    resultado["odontograma"] = []
                    resultado["pagos"] = _extraer_y_calcular_pagos({}, texto_crudo)

                fil = resultado.setdefault("datos_filiacion", {})
                nom = _normalizar_nombres_espanol(fil.get("nombre", ""))
                fil["nombre"] = nom
                fil["documento"] = sanitizar_cedula(fil.get("documento", ""))
                fil["edad"] = _limpiar_edad_dictada(fil.get("edad", ""), texto_crudo)
                sex = fil.get("sexo", "No especificado")
                if not sex or sex.lower() in ("no especificado", "none", ""):
                    fil["sexo"] = _inferir_sexo_por_nombre(nom)
                tel_det = extraer_telefono_dictado(texto_crudo)
                if tel_det:
                    fil["telefono"] = tel_det
                return resultado

            resultado["tipo"] = "ACTUALIZAR_DATOS_PACIENTE"
            ced_ext, tel_ext = extraer_cedula_y_telefono_dictados(texto_crudo)

            # 1. Teléfono
            tel_act = str(resultado.get("telefono") or "").strip()
            if not tel_act or tel_act.lower() in ("no especificado", "none", "null", ""):
                if tel_ext:
                    resultado["telefono"] = tel_ext
            else:
                d_clean = re.sub(r'\D', '', tel_act)
                if len(d_clean) == 9 and d_clean.startswith('9'):
                    d_clean = '0' + d_clean
                if len(d_clean) in (7, 8, 9, 10, 11, 12):
                    resultado["telefono"] = d_clean

            # 2. Cédula
            ced_act = str(resultado.get("cedula") or "").strip()
            if not ced_act or ced_act.lower() in ("no especificado", "none", "null", ""):
                if ced_ext:
                    resultado["cedula"] = ced_ext
            else:
                c_clean = sanitizar_cedula(ced_act)
                if c_clean and c_clean.lower() != "no especificado":
                    resultado["cedula"] = c_clean

            # 3. Paciente
            pac_det = detectar_paciente_en_texto(texto_crudo)
            if pac_det:
                resultado["paciente_id"] = pac_det.get("id")
                if not resultado.get("nombre_paciente") or resultado.get("nombre_paciente") in ("Paciente", "Cita", "No especificado"):
                    resultado["nombre_paciente"] = pac_det.get("nombre")
                resultado["documento"] = pac_det.get("documento") or ""

        return resultado
    except Exception as e:
        print(f"[GROQ ERROR] Error al estructurar con IA: {e}")
        return {
            "tipo": "HISTORIA_CLINICA",
            "datos_filiacion": {"nombre": "No especificado", "documento": "No especificado", "sexo": "No especificado", "contacto_emergencia": "No especificado"},
            "motivo_consulta": texto_crudo,
            "diagnostico": "Pendiente de estructuración",
            "plan_tratamiento": "Evaluación clínica general",
            "odontograma": [],
            "pagos": _extraer_y_calcular_pagos({}, texto_crudo)
        }
