import os
import re
import json
import urllib.parse
import webbrowser
import datetime
import requests
from config import cargar_datos_clinica, RUTA_DB
from database import get_connection

DIAS_SEMANA_ES = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo"
}

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

def normalizar_numero_whatsapp(telefono: str, codigo_pais="593") -> str:
    """
    Normaliza números telefónicos al formato internacional E.164 sin símbolos ni espacios.
    Por defecto asume Ecuador (+593):
    - '099 333 444' -> '59399333444'
    - '0987654321'  -> '593987654321'
    - '+593 99 123 456' -> '59399123456'
    - '02 2456789'  -> '59322456789'
    """
    if not telefono:
        return ""
    digits = re.sub(r'\D', '', str(telefono).strip())
    if not digits:
        return ""

    cp = str(codigo_pais or "593").replace("+", "").strip()

    # Si empieza con 00 (formato de marcación internacional), quitar 00
    if digits.startswith("00"):
        digits = digits[2:]

    # Si empieza con el código de país (ej. 593...)
    if digits.startswith(cp):
        return digits

    # Si empieza con 0 (ej. celular local 09... o convencional 02...)
    if digits.startswith("0"):
        return cp + digits[1:]

    # Si tiene 9 dígitos y empieza con 9 (ej. 99333444)
    if len(digits) == 9 and digits.startswith("9"):
        return cp + digits

    # Si tiene 8 dígitos (ej. convencional sin 02)
    if len(digits) == 8:
        return cp + digits

    # Si ya tiene más de 10 dígitos y no empieza con 0, asumimos formato internacional
    if len(digits) >= 10:
        return digits

    return cp + digits

def formatear_fecha_espanol(fecha_iso: str) -> tuple[str, str]:
    """
    Parsea 'AAAA-MM-DD HH:MM:SS' o 'AAAA-MM-DD HH:MM' a:
    ('Miércoles 09 de Septiembre', '14:00')
    """
    fecha_txt = "Fecha indicada"
    hora_txt = "10:00"
    if not fecha_iso:
        return fecha_txt, hora_txt

    try:
        dt = None
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
            try:
                dt = datetime.datetime.strptime(fecha_iso, fmt)
                break
            except Exception:
                pass
        if dt:
            dia_sem = DIAS_SEMANA_ES.get(dt.weekday(), "")
            mes_nom = MESES_ES.get(dt.month, "")
            fecha_txt = f"{dia_sem} {dt.day:02d} de {mes_nom}"
            hora_txt = f"{dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        pass

    return fecha_txt, hora_txt

def generar_mensaje_recordatorio(cita: dict, config_clinica: dict = None) -> str:
    """
    Construye la plantilla clínica formal y empática del recordatorio de cita.
    """
    if config_clinica is None:
        config_clinica = cargar_datos_clinica()

    paciente = cita.get("nombre_paciente") or "Estimado/a Paciente"
    f_iso = cita.get("fecha_hora_inicio") or ""
    fecha_legible, hora_legible = formatear_fecha_espanol(f_iso)
    motivo = cita.get("descripcion") or "Consulta odontológica"
    clinica = config_clinica.get("nombre_clinica") or "Clínica Dental BIMO"
    doctor = config_clinica.get("nombre_doctor") or "Dr. Mateo"
    telefono_clinica = config_clinica.get("telefono_contacto") or ""

    contacto_linea = f"\n📞 Contáctenos al {telefono_clinica} si requiere reprogramar." if telefono_clinica else ""

    mensaje = (
        f"¡Hola {paciente}! Le saludamos cordialmente de *{clinica}*.\n\n"
        f"🦷 Le recordamos su cita odontológica agendada:\n"
        f"📅 *Fecha:* {fecha_legible}\n"
        f"⏰ *Hora:* {hora_legible}\n"
        f"📋 *Procedimiento:* {motivo}\n"
        f"👨‍⚕️ *Profesional:* {doctor}\n\n"
        f"Por favor, responda a este mensaje para *CONFIRMAR* su asistencia.{contacto_linea}\n\n"
        f"¡Le esperamos!"
    )
    return mensaje

def generar_url_whatsapp(telefono: str, mensaje: str, codigo_pais="593") -> str:
    """
    Genera el enlace web oficial de WhatsApp (Nivel 1).
    """
    num_norm = normalizar_numero_whatsapp(telefono, codigo_pais)
    txt_encoded = urllib.parse.quote(mensaje)
    return f"https://api.whatsapp.com/send?phone={num_norm}&text={txt_encoded}"

def enviar_whatsapp_api_background(telefono: str, mensaje: str, config_wa: dict = None) -> dict:
    """
    NIVEL 2: Despacho desatendido en segundo plano sin abrir ventanas de navegador.
    Soporta:
    - 'meta_cloud': WhatsApp Business Cloud API Oficial
    - 'twilio': Twilio Programmable Messaging
    - 'webhook': Gateway HTTP propio (UltraMsg, Evolution API, Baileys, etc.)
    """
    if config_wa is None:
        conf_cli = cargar_datos_clinica()
        config_wa = conf_cli.get("whatsapp", {})

    proveedor = str(config_wa.get("proveedor", "none")).lower().strip()
    cod_pais = config_wa.get("codigo_pais", "593")
    numero = normalizar_numero_whatsapp(telefono, cod_pais)

    if not numero:
        return {"status": "error", "message": "Número de teléfono inválido o vacío."}

    # 1. Meta Cloud API Oficial
    if proveedor == "meta_cloud":
        token = config_wa.get("meta_access_token", "").strip()
        phone_id = config_wa.get("meta_phone_number_id", "").strip()
        if not token or not phone_id:
            return {"status": "fallback", "message": "Meta Cloud API no tiene credenciales completas (Access Token o Phone Number ID faltante)."}

        url = f"https://graph.facebook.com/v19.0/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "text",
            "text": {"body": mensaje}
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=12.0)
            if r.status_code in (200, 201):
                return {"status": "ok", "proveedor": "meta_cloud", "response": r.json()}
            else:
                return {"status": "fallback", "message": f"Error de Meta API ({r.status_code}): {r.text}"}
        except Exception as e:
            return {"status": "fallback", "message": f"Excepción de conexión con Meta API: {e}"}

    # 2. Twilio WhatsApp API
    elif proveedor == "twilio":
        sid = config_wa.get("twilio_account_sid", "").strip()
        auth_token = config_wa.get("twilio_auth_token", "").strip()
        from_num = config_wa.get("twilio_from_number", "").strip()
        if not sid or not auth_token or not from_num:
            return {"status": "fallback", "message": "Twilio no tiene credenciales completas."}

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        data = {
            "From": f"whatsapp:{from_num}" if not from_num.startswith("whatsapp:") else from_num,
            "To": f"whatsapp:+{numero}",
            "Body": mensaje
        }
        try:
            r = requests.post(url, data=data, auth=(sid, auth_token), timeout=12.0)
            if r.status_code in (200, 201):
                return {"status": "ok", "proveedor": "twilio", "response": r.json()}
            else:
                return {"status": "fallback", "message": f"Error de Twilio ({r.status_code}): {r.text}"}
        except Exception as e:
            return {"status": "fallback", "message": f"Excepción de conexión con Twilio: {e}"}

    # 3. Webhook / Gateway Local HTTP (UltraMsg, Evolution API, etc.)
    elif proveedor == "webhook":
        endpoint = config_wa.get("webhook_url", "").strip()
        api_key = config_wa.get("webhook_api_key", "").strip()
        if not endpoint:
            return {"status": "fallback", "message": "Webhook URL no configurada."}

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "phone": numero,
            "number": numero,
            "message": mensaje,
            "text": mensaje
        }
        try:
            r = requests.post(endpoint, headers=headers, json=payload, timeout=12.0)
            if r.status_code in (200, 201, 202):
                return {"status": "ok", "proveedor": "webhook", "response": r.text}
            else:
                return {"status": "fallback", "message": f"Error de Webhook ({r.status_code}): {r.text}"}
        except Exception as e:
            return {"status": "fallback", "message": f"Excepción de conexión con Webhook: {e}"}

    return {"status": "fallback", "message": "Sin proveedor de API de background configurado. Se usará apertura directa."}

def marcar_recordatorio_enviado_db(cita_id: int, metodo="wa_me"):
    """
    Registra en SQLite la trazabilidad del envío de recordatorio.
    """
    try:
        with get_connection() as conn:
            c = conn.cursor()
            c.execute("""
                UPDATE citas_agenda
                SET recordatorio_enviado = 1,
                    recordatorio_enviado_at = datetime('now', 'localtime'),
                    recordatorio_metodo = ?
                WHERE id = ?
            """, (metodo, cita_id))
            conn.commit()
            print(f"[WHATSAPP] Cita #{cita_id} marcada como recordatorio enviado (método: {metodo}).")
    except Exception as e:
        print(f"[WHATSAPP WARN] Error al marcar recordatorio en DB: {e}")

def despachar_recordatorio_cita(cita_id: int, forzar_navegador=False) -> dict:
    """
    Orquestador principal de despacho para una cita:
    1. Obtiene datos de la cita y del paciente.
    2. Valida teléfono.
    3. Si Nivel 2 está configurado y forzar_navegador=False, envía en background.
    4. Si falla o está en modo local, abre WhatsApp Web/Desktop (Nivel 1).
    """
    conf_cli = cargar_datos_clinica()
    config_wa = conf_cli.get("whatsapp", {})
    cod_pais = config_wa.get("codigo_pais", "593")

    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT c.*, p.telefono as tel_paciente, p.nombre as nom_pac_db
            FROM citas_agenda c
            LEFT JOIN pacientes p ON c.paciente_id = p.id
            WHERE c.id = ?
        """, (cita_id,))
        row = c.fetchone()

    if not row:
        return {"status": "error", "message": f"No se encontró la cita #{cita_id}"}

    cita_dict = dict(row)
    tel_candidato = cita_dict.get("telefono") or cita_dict.get("tel_paciente") or ""
    numero = normalizar_numero_whatsapp(tel_candidato, cod_pais)

    if not numero or len(numero) < 8:
        return {
            "status": "error",
            "message": f"El paciente '{cita_dict.get('nombre_paciente')}' no tiene registrado un número telefónico válido para WhatsApp."
        }

    mensaje = generar_mensaje_recordatorio(cita_dict, conf_cli)
    url_wa = generar_url_whatsapp(numero, mensaje, cod_pais)

    # Intento de Nivel 2 (Desatendido por API)
    if not forzar_navegador and config_wa.get("proveedor") in ("meta_cloud", "twilio", "webhook"):
        res_api = enviar_whatsapp_api_background(numero, mensaje, config_wa)
        if res_api.get("status") == "ok":
            marcar_recordatorio_enviado_db(cita_id, metodo=res_api.get("proveedor"))
            return {
                "status": "ok",
                "metodo": "api_background",
                "proveedor": res_api.get("proveedor"),
                "telefono": numero,
                "mensaje": f"Recordatorio enviado exitosamente a {cita_dict.get('nombre_paciente')} en segundo plano.",
                "mensaje_texto": mensaje
            }

    # Nivel 1: Apertura interactiva (100% nativa y gratuita)
    try:
        webbrowser.open(url_wa)
        marcar_recordatorio_enviado_db(cita_id, metodo="wa_me")
        return {
            "status": "ok",
            "metodo": "wa_me",
            "url": url_wa,
            "telefono": numero,
            "mensaje": f"Abriendo chat de WhatsApp para {cita_dict.get('nombre_paciente')} con el recordatorio pre-cargado.",
            "mensaje_texto": mensaje
        }
    except Exception as e_open:
        return {"status": "error", "message": f"Error abriendo WhatsApp: {e_open}"}

def obtener_citas_pendientes_recordatorio(dias_adelanto=1) -> list[dict]:
    """
    Retorna la lista de citas agendadas para dentro de 'dias_adelanto' días (por defecto mañana),
    incluyendo teléfono y estado de notificación.
    """
    conf_cli = cargar_datos_clinica()
    config_wa = conf_cli.get("whatsapp", {})
    cod_pais = config_wa.get("codigo_pais", "593")

    with get_connection() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT c.*, p.telefono as tel_paciente
            FROM citas_agenda c
            LEFT JOIN pacientes p ON c.paciente_id = p.id
            WHERE date(c.fecha_hora_inicio) = date('now', 'localtime', '+' || ? || ' day')
              AND c.estado != 'cancelada'
            ORDER BY c.fecha_hora_inicio ASC
        """, (int(dias_adelanto),))
        filas = c.fetchall()

    resultado = []
    for r in filas:
        d = dict(r)
        tel_raw = d.get("telefono") or d.get("tel_paciente") or ""
        d["telefono_normalizado"] = normalizar_numero_whatsapp(tel_raw, cod_pais)
        d["tiene_telefono"] = bool(d["telefono_normalizado"] and len(d["telefono_normalizado"]) >= 8)
        f_legible, h_legible = formatear_fecha_espanol(d.get("fecha_hora_inicio", ""))
        d["fecha_legible"] = f_legible
        d["hora_legible"] = h_legible
        d["mensaje_preview"] = generar_mensaje_recordatorio(d, conf_cli)
        resultado.append(d)

    return resultado

def despachar_recordatorios_lote_manana(forzar_navegador=False) -> dict:
    """
    Despacha la cola de recordatorios para todos los pacientes con cita mañana.
    """
    citas_manana = obtener_citas_pendientes_recordatorio(dias_adelanto=1)
    if not citas_manana:
        return {
            "status": "ok",
            "total": 0,
            "enviados": 0,
            "fallidos": 0,
            "message": "No hay citas agendadas para el día de mañana."
        }

    enviados = 0
    fallidos = 0
    detalles = []

    for cita in citas_manana:
        cid = cita["id"]
        if not cita["tiene_telefono"]:
            fallidos += 1
            detalles.append({
                "cita_id": cid,
                "paciente": cita.get("nombre_paciente"),
                "status": "error",
                "message": "Sin teléfono registrado"
            })
            continue

        resp = despachar_recordatorio_cita(cid, forzar_navegador=forzar_navegador)
        if resp.get("status") == "ok":
            enviados += 1
            detalles.append({
                "cita_id": cid,
                "paciente": cita.get("nombre_paciente"),
                "status": "ok",
                "metodo": resp.get("metodo")
            })
        else:
            fallidos += 1
            detalles.append({
                "cita_id": cid,
                "paciente": cita.get("nombre_paciente"),
                "status": "error",
                "message": resp.get("message")
            })

    return {
        "status": "ok",
        "total": len(citas_manana),
        "enviados": enviados,
        "fallidos": fallidos,
        "detalles": detalles,
        "message": f"Proceso completado: {enviados} recordatorios procesados, {fallidos} pendientes/sin teléfono."
    }
