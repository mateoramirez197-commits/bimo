import os
import datetime
import urllib.parse
import webbrowser
from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from database import crear_cita_db, listar_citas_db
from config import BASE_DIR

SCOPES = ['https://www.googleapis.com/auth/calendar']
_CALENDAR_SERVICE = None
_DOCTOR_EMAIL = None

import shutil

def buscar_y_copiar_credentials():
    """
    Busca si el usuario descargó credentials.json o client_secret_*.json en Descargas o Escritorio y lo vincula automáticamente.
    """
    base_cred = os.path.join(BASE_DIR, 'credentials.json')
    if os.path.exists(base_cred):
        return True

    user_home = Path.home()
    for folder in [user_home / "Downloads", user_home / "Desktop", user_home / "Descargas"]:
        if folder.exists():
            for f in list(folder.glob("client_secret_*.json")) + list(folder.glob("*credential*.json")):
                try:
                    shutil.copy(str(f), base_cred)
                    print(f"[CALENDAR] Archivo de credenciales detectado automáticamente y copiado: {f}")
                    return True
                except Exception:
                    pass
    return False

def init_google_calendar(email_doctor=None):
    global _CALENDAR_SERVICE, _DOCTOR_EMAIL
    if email_doctor:
        _DOCTOR_EMAIL = email_doctor

    buscar_y_copiar_credentials()

    creds = None
    token_path = os.path.join(BASE_DIR, 'token.json')
    cred_path = os.path.join(BASE_DIR, 'credentials.json')

    if os.path.exists(token_path):
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        elif os.path.exists(cred_path):
            try:
                flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
                creds = flow.run_local_server(port=0)
                with open(token_path, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"[CALENDAR] Error en flujo OAuth2: {e}")
                creds = None
        else:
            print(f"[CALENDAR] Perfil vinculado a {_DOCTOR_EMAIL or 'Dr. Titular'}. Operando en agenda local y sincronización web.")
            return False

    if creds and creds.valid:
        try:
            _CALENDAR_SERVICE = build('calendar', 'v3', credentials=creds)
            print(f"[CALENDAR] Sincronización oficial activa con Google Calendar de {_DOCTOR_EMAIL or 'doctor'}.")
            return True
        except Exception as e:
            print(f"[CALENDAR] Error al construir cliente de Google Calendar: {e}")
            return False

    return False

def generar_url_evento_google(titulo, fecha_inicio_str, fecha_fin_str=None, detalles=""):
    """
    Genera el enlace oficial de Google Calendar en hora local para abrir el evento en Chrome.
    """
    try:
        dt_inicio = datetime.datetime.fromisoformat(fecha_inicio_str.replace(" ", "T"))
    except Exception:
        dt_inicio = datetime.datetime.now() + datetime.timedelta(days=1)

    if fecha_fin_str:
        try:
            dt_fin = datetime.datetime.fromisoformat(fecha_fin_str.replace(" ", "T"))
        except Exception:
            dt_fin = dt_inicio + datetime.timedelta(hours=1)
    else:
        dt_fin = dt_inicio + datetime.timedelta(hours=1)

    # Formato local (sin 'Z' para respetar la zona horaria del consultorio)
    fmt_local = "%Y%m%dT%H%M%S"
    fmt_inicio = dt_inicio.strftime(fmt_local)
    fmt_fin = dt_fin.strftime(fmt_local)

    params = {
        "action": "TEMPLATE",
        "text": titulo,
        "dates": f"{fmt_inicio}/{fmt_fin}",
        "details": detalles,
        "ctz": "America/Bogota"
    }
    return f"https://calendar.google.com/calendar/render?{urllib.parse.urlencode(params)}"

def exportar_calendario_ics(ruta_salida=None):
    """
    Exporta todas las citas a un archivo .ics estándar para sincronización universal con Google Calendar y Outlook.
    """
    if not ruta_salida:
        ruta_salida = BASE_DIR / "bimo_agenda.ics"

    citas = listar_citas_db(limite=100)
    lineas = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BIMO Dental Software//ES",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Agenda Clinica BIMO",
        "X-WR-TIMEZONE:America/Bogota"
    ]
    fmt = "%Y%m%dT%H%M%S"
    for c in citas:
        f_ini = c.get('fecha_hora_inicio', '').replace(' ', 'T')
        try:
            dt_ini = datetime.datetime.fromisoformat(f_ini)
        except Exception:
            continue
        dt_fin = dt_ini + datetime.timedelta(hours=1)
        cid = c.get('id', 1)
        pac = c.get('nombre_paciente', 'Paciente')
        desc = c.get('descripcion', 'Consulta Odontológica')
        lineas.extend([
            "BEGIN:VEVENT",
            f"UID:bimo_{cid}_{dt_ini.strftime('%Y%m%d')}@bimo.local",
            f"DTSTAMP:{datetime.datetime.now().strftime(fmt)}",
            f"DTSTART:{dt_ini.strftime(fmt)}",
            f"DTEND:{dt_fin.strftime(fmt)}",
            f"SUMMARY:BIMO: {pac} - {desc}",
            f"DESCRIPTION:Paciente: {pac} | Procedimiento: {desc}",
            "STATUS:CONFIRMED",
            "END:VEVENT"
        ])
    lineas.append("END:VCALENDAR")
    with open(ruta_salida, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))
    return str(ruta_salida)

def agendar_cita(nombre_paciente, telefono, fecha_hora_inicio, fecha_hora_fin=None, descripcion="Consulta Odontológica", paciente_id=None, abrir_en_navegador=True, duracion_minutos=30, **kwargs):
    """
    Agenda una cita en SQLite, actualiza el archivo .ics y abre la ventana oficial de Google Calendar
    con el evento precargado para que el usuario confirme y guarde con un solo clic.
    """
    # 0. Calcular fecha fin si no se especifica
    try:
        dt_inicio = datetime.datetime.fromisoformat(fecha_hora_inicio.replace(" ", "T"))
    except Exception:
        dt_inicio = datetime.datetime.now() + datetime.timedelta(days=1)

    if not fecha_hora_fin:
        dt_fin = dt_inicio + datetime.timedelta(minutes=duracion_minutos or 30)
        fecha_hora_fin = dt_fin.strftime("%Y-%m-%d %H:%M:%S")
    else:
        try:
            dt_fin = datetime.datetime.fromisoformat(fecha_hora_fin.replace(" ", "T"))
        except Exception:
            dt_fin = dt_inicio + datetime.timedelta(minutes=duracion_minutos or 30)

    # 1. Guardar en SQLite
    cita_id = crear_cita_db(
        nombre_paciente=nombre_paciente,
        telefono=telefono,
        fecha_hora_inicio=fecha_hora_inicio,
        fecha_hora_fin=fecha_hora_fin,
        descripcion=descripcion,
        paciente_id=paciente_id,
        google_event_id=None
    )

    # 2. Actualizar archivo iCalendar (.ics) local
    exportar_calendario_ics()

    # 3. Generar URL de inserción para Google Calendar
    titulo_evento = f"BIMO: {nombre_paciente} - {descripcion}"
    detalles_evento = f"Paciente: {nombre_paciente}\nTeléfono: {telefono}\nTratamiento: {descripcion}\nSoftware Clínico BIMO"
    url_gcal = generar_url_evento_google(titulo_evento, fecha_hora_inicio, fecha_hora_fin, detalles_evento)

    # 4. Sincronizar silenciosamente vía Google Calendar API si hay credenciales autorizadas
    google_event_id = None
    if _CALENDAR_SERVICE:
        try:
            try:
                dt_inicio = datetime.datetime.fromisoformat(fecha_hora_inicio.replace(" ", "T"))
            except Exception:
                dt_inicio = datetime.datetime.now() + datetime.timedelta(days=1)

            if fecha_hora_fin:
                try:
                    dt_fin = datetime.datetime.fromisoformat(fecha_hora_fin.replace(" ", "T"))
                except Exception:
                    dt_fin = dt_inicio + datetime.timedelta(hours=1)
            else:
                dt_fin = dt_inicio + datetime.timedelta(hours=1)

            evento = {
                'summary': titulo_evento,
                'description': detalles_evento,
                'start': {'dateTime': dt_inicio.isoformat(), 'timeZone': 'America/Bogota'},
                'end': {'dateTime': dt_fin.isoformat(), 'timeZone': 'America/Bogota'},
            }
            evento_creado = _CALENDAR_SERVICE.events().insert(calendarId='primary', body=evento).execute()
            google_event_id = evento_creado.get('id')
            print(f"[CALENDAR] Cita sincronizada silenciosamente vía API en Google Calendar: {google_event_id}")
        except Exception as e:
            print(f"[CALENDAR] Error sincronizando con Google Calendar API: {e}")

    # Solo si el usuario explícitamente solicita abrir el navegador visible
    if abrir_en_navegador and url_gcal:
        try:
            webbrowser.open(url_gcal)
        except Exception as e:
            pass

    return {
        "cita_id": cita_id,
        "google_event_id": google_event_id,
        "url_gcal": url_gcal
    }

def eliminar_cita(nombre_paciente=None, cita_id=None, fecha=None):
    """
    Elimina o cancela citas por dictado en SQLite y las borra también de Google Calendar.
    """
    from database import cancelar_o_eliminar_cita_db
    citas_borradas = cancelar_o_eliminar_cita_db(nombre_paciente=nombre_paciente, cita_id=cita_id, fecha=fecha)
    
    # Borrar también en Google Calendar si existía el evento en la API
    if _CALENDAR_SERVICE:
        for c in citas_borradas:
            gid = c.get('google_event_id')
            if gid:
                try:
                    _CALENDAR_SERVICE.events().delete(calendarId='primary', eventId=gid).execute()
                    print(f"[CALENDAR] Evento {gid} eliminado de Google Calendar.")
                except Exception as e:
                    print(f"[CALENDAR] Error al borrar evento en Google: {e}")

    # Actualizar archivo iCalendar
    exportar_calendario_ics()
    return citas_borradas

def reprogramar_cita(nombre_paciente, nueva_fecha_hora_inicio, nueva_fecha_hora_fin=None, nuevo_motivo="Consulta Odontológica", paciente_id=None, abrir_en_navegador=True):
    """
    Elimina la cita previa del paciente de la base de datos y Google Calendar,
    y agenda la nueva cita en la fecha solicitada, garantizando que la cita previa sea borrada.
    """
    from database import cancelar_o_eliminar_cita_db
    citas_borradas = cancelar_o_eliminar_cita_db(nombre_paciente=nombre_paciente)
    print(f"[CALENDAR REPROGRAMAR] {len(citas_borradas)} cita(s) previas eliminadas para {nombre_paciente}")

    if _CALENDAR_SERVICE:
        for c in citas_borradas:
            gid = c.get("google_event_id")
            if gid:
                try:
                    _CALENDAR_SERVICE.events().delete(calendarId='primary', eventId=gid).execute()
                except Exception:
                    pass

    return agendar_cita(
        nombre_paciente=nombre_paciente,
        telefono="",
        fecha_hora_inicio=nueva_fecha_hora_inicio,
        fecha_hora_fin=nueva_fecha_hora_fin,
        descripcion=nuevo_motivo,
        paciente_id=paciente_id,
        abrir_en_navegador=abrir_en_navegador
    )

def obtener_citas(limite=50):
    return listar_citas_db(limite=limite)

def forzar_sincronizacion_calendar():
    """Limpia tokens locales corruptos y reinicia el flujo de autenticación OAuth2."""
    global _CALENDAR_SERVICE
    for f in ['token.json', 'token.pickle']:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
    _CALENDAR_SERVICE = None
    return init_google_calendar()

def desvincular_calendar():
    """Elimina tokens de Google Calendar para operar exclusivamente en agenda local."""
    global _CALENDAR_SERVICE
    for f in ['token.json', 'token.pickle']:
        if os.path.exists(f):
            try:
                os.remove(f)
            except Exception:
                pass
    _CALENDAR_SERVICE = None
    print("[CALENDAR] Google Calendar desvinculado con éxito. Operando en agenda local.")
    return True
