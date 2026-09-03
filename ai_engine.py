import os
import json
import datetime
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
    "Sisa, Inti, Tupac, Tupaq, Killa, Ñusta, Nayra, Amaru, Pacari, Nina, Raymi, Kuntur, "
    "Sayri, Chuki, Hakan, Wayra, Tamia, Runa, Quilla, Illari, Huáscar, Atahualpa, Rumiñahui, "
    "Llakta, Sumak, Kawsay, Ayllu, Pacha, Allpa, Urku, Yaku, Katari, Yupanqui, Manco, "
    "Huayna, Cusi, Ollanta, Chaski, Quispe, Quishpe, Toapanta, Guamán, Guaman, Chimbo, "
    "Pilataxi, Chuquimarca, Yánez, Yanez, Cango, Tipán, Tipan, Chango, Caiza, Guanoluisa, "
    "Chiluisa, Chushig, Alulema, Tasambay, Simaluiza, Masabanda, Tisalema, Paucar, Simbaña, "
    "Simbana, Pillajo, Muenala, Lema, Conejo, De la Torre, Cotacachi, Cachiguango, Cachimuel, "
    "Tuquerres, Farinango, Otavalo, Insuasti, Paspuel, Tituaña, Tituana, Guamangate, "
    "Caisaguano, Chusin, Maliza, Yanchaliquin, Moreta, Calapucha, Grefa, Shiguango, Cerda, "
    "Tanguila, Ushigua, Vargas, Santi, Andi, Dahua, Coquinche, Canelos, Aguinda, Tapuy, "
    "Alvarado, Mateo Ramírez, Sebastián Ramírez, Gandhi López, Juan Valdés, Juliana Aragón, "
    "Estefanía Sandoval, Carlos Mendoza, Patricio, Fabricio, Mayra, Fernando, Gisella."
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
    "Morales, Romero, Castro, Ortiz, Silva, Vargas, Ramos, Reyes, Cruz, Flores, Gutiérrez, Chávez."
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
        initial_prompt = (
            f"Consulta odontológica y médica del Doctor {doc_nom}. "
            f"{GLOSARIO_NOMBRES_HISPANOAMERICANOS} {GLOSARIO_ANDINO_KICHWA} {GLOSARIO_ODONTOLOGICO}"
        )
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
    return texto

def _normalizar_nombres_espanol(nombre: str) -> str:
    """Normaliza nombres hispanoamericanos y elimina deformaciones extranjeras (ej. 'Sebastiano' -> 'Sebastián')."""
    if not nombre or not isinstance(nombre, str):
        return nombre
    
    import re
    reemplazos = [
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
        (r"\bQuichpe\b", "Quishpe"),
        (r"\bQuiche\b", "Quishpe"),
        (r"\bChispe\b", "Quispe"),
        (r"\bKizpe\b", "Quispe"),
        (r"\bKispe\b", "Quispe"),
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

def procesar_comando_o_dictado(texto_crudo: str) -> dict:
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

Analiza la siguiente transcripción de voz y clasifícala estrictamente en una de cinco intenciones:
1. COMANDO_CITA: Si el doctor solicita agendar o programar una nueva cita.
2. CANCELAR_CITA: Si el doctor solicita cancelar o eliminar citas.
3. CONSULTA_MEDICA: Si el doctor hace una pregunta puntual médica o farmacológica (máximo 2 oraciones).
4. HISTORIA_CLINICA: Si el doctor está dictando la consulta de un paciente (filiación, antecedentes, examen bucal, dientes, diagnóstico, ortodoncia).
5. IGNORAR: Si el audio trata sobre cualquier tema ajeno a la odontología, medicina o citas clínicas.

Devuelve ÚNICAMENTE un formato JSON válido según la intención:

Si es COMANDO_CITA:
{{
    "tipo": "COMANDO_CITA",
    "nombre_paciente": "Nombre explícito del paciente mencionado o 'No especificado'",
    "fecha_hora": "AAAA-MM-DD HH:MM estimada",
    "motivo": "Motivo de la cita",
    "mensaje_confirmacion": "Cita detectada"
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
        respuesta = cliente.chat.completions.create(
            model=modelo,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        contenido = respuesta.choices[0].message.content
        resultado = json.loads(contenido)

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
            import re
            m_dias = re.search(r"(?:dentro de|en|para|despu[eé]s de)\s+(\d{1,3})\s+d[ií]as", texto_crudo, re.IGNORECASE)
            cita_obj = resultado.get("cita_programada", {})
            if m_dias:
                num_d = int(m_dias.group(1))
                dt_calc = datetime.datetime.now() + datetime.timedelta(days=num_d)
                cita_obj["agendar"] = True
                cita_obj["dias_relativos"] = num_d
                cita_obj["fecha_hora"] = dt_calc.strftime("%Y-%m-%d 10:00:00")
                resultado["cita_programada"] = cita_obj
            elif "en un mes" in texto_crudo.lower() or "un mes" in texto_crudo.lower():
                dt_calc = datetime.datetime.now() + datetime.timedelta(days=30)
                cita_obj["agendar"] = True
                cita_obj["dias_relativos"] = 30
                cita_obj["fecha_hora"] = dt_calc.strftime("%Y-%m-%d 10:00:00")
                resultado["cita_programada"] = cita_obj

            # Extracción y cálculo matemático estricto de honorarios y pagos
            resultado["pagos"] = _extraer_y_calcular_pagos(resultado.get("pagos", {}), texto_crudo)

        elif resultado.get("tipo") in ("COMANDO_CITA", "CANCELAR_CITA", "REPROGRAMAR_CITA"):
            nom = _normalizar_nombres_espanol(resultado.get("nombre_paciente", ""))
            resultado["nombre_paciente"] = nom

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
