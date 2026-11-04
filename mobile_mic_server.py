import os
import socket
import threading
import datetime
from pathlib import Path
import qrcode
from PIL import Image
import re
import secrets
import hmac
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
import uvicorn
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from config import MOBILE_SERVER_PORT, BASE_DIR, sanitizar_nombre_carpeta
from database import buscar_pacientes, listar_consultas_paciente, obtener_consulta_por_id

def obtener_o_crear_movil_token() -> str:
    from config import obtener_parametro_boveda, guardar_parametro_boveda
    tok = obtener_parametro_boveda("movil_token")
    if not tok or len(str(tok).strip()) < 16:
        tok = secrets.token_urlsafe(24)
        guardar_parametro_boveda("movil_token", tok)
    return str(tok).strip()

app = FastAPI(title="BIMO Mobile Bridge & Clinical Viewer")

@app.middleware("http")
async def verificar_autenticacion_movil(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        token_esperado = obtener_o_crear_movil_token()
        cookie_t = request.cookies.get("bimo_t", "")
        header_t = request.headers.get("X-Bimo-Token", "")
        query_t = request.query_params.get("t", "")
        present_tok = header_t or cookie_t or query_t
        if not present_tok or not hmac.compare_digest(str(present_tok), str(token_esperado)):
            return JSONResponse({"status": "error", "message": "No autorizado. Dispositivo móvil no emparejado."}, status_code=401)
    return await call_next(request)

_CALLBACK_AUDIO = None
_CALLBACK_TEXTO = None
_SERVIDOR_HILO = None
_ULTIMO_AUDIO_RUTA = "temp_mobile_audio.wav"

RUTA_CERT = BASE_DIR / "bimo_cert.pem"
RUTA_KEY = BASE_DIR / "bimo_key.pem"

def _asegurar_certificados_ssl():
    """
    Genera automáticamente certificados SSL autofirmados locales para habilitar HTTPS.
    HTTPS es OBLIGATORIO en Safari (iOS) y Chrome (Android) para permitir acceso al micrófono
    SIN abrir la cámara de video.
    """
    if os.path.exists(RUTA_CERT) and os.path.exists(RUTA_KEY):
        return

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "bimo.local"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "BIMO Clinical SaaS"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=3650))
        .sign(key, hashes.SHA256())
    )

    with open(RUTA_CERT, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(RUTA_KEY, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))

def obtener_ip_local():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def generar_codigo_qr_url(url: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="#1B365D", back_color="white")
    return img_qr.convert("RGB")


# ==========================================
# WEB APP MÓVIL (HTTPS, solo audio, sin cámara para el dictado)
# La página vive en web_ui/movil.html y usa los recursos locales de web_ui/vendor.
# ==========================================
def _carpeta_web_ui() -> Path:
    import sys
    candidatos = [Path(BASE_DIR) / "web_ui"]
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        candidatos = [Path(getattr(sys, "_MEIPASS", exe_dir)) / "web_ui", exe_dir / "web_ui", exe_dir / "_internal" / "web_ui"] + candidatos
    candidatos.append(Path(__file__).resolve().parent / "web_ui")
    return next((c for c in candidatos if (c / "movil.html").exists()), candidatos[-1])


WEB_UI_DIR = _carpeta_web_ui()


def _pagina_movil(tema: str) -> str:
    html = (WEB_UI_DIR / "movil.html").read_text(encoding="utf-8")
    return html.replace("{{TEMA}}", tema if tema in ("claro", "oscuro", "rosa") else "claro")


def _pagina_aviso(titulo: str, texto: str, status_code: int = 401) -> HTMLResponse:
    """Aviso (no emparejado / código inválido) con el mismo estilo de vidrio, sin recursos externos."""
    return HTMLResponse(
        "<!DOCTYPE html><html lang='es'><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0, viewport-fit=cover'><title>BIMO</title>"
        "<style>body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px;box-sizing:border-box;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#0b0b12;text-align:center;"
        "background:radial-gradient(40% 30% at 15% 15%,rgba(120,170,255,.6),transparent 70%),"
        "radial-gradient(40% 30% at 85% 30%,rgba(196,160,255,.55),transparent 70%),"
        "radial-gradient(45% 30% at 55% 90%,rgba(255,190,160,.55),transparent 70%),#e8edf7}"
        ".card{max-width:380px;padding:28px 24px;border-radius:28px;background:rgba(255,255,255,.35);"
        "-webkit-backdrop-filter:blur(30px) saturate(200%);backdrop-filter:blur(30px) saturate(200%);"
        "border:1px solid rgba(255,255,255,.7);box-shadow:inset 0 1px 0 #fff,0 18px 50px rgba(40,55,100,.18)}"
        "h2{margin:0 0 10px;font-size:22px;letter-spacing:-.02em}p{margin:0;color:#5b6070;line-height:1.55;font-size:15px}</style>"
        f"</head><body><div class='card'><h2>{titulo}</h2><p>{texto}</p></div></body></html>",
        status_code=status_code,
    )


CATEGORIAS_PERMITIDAS = (
    "radiografia", "fotografia", "intraoral", "perfil", "panoramica", "otro",
    # Tipos que ofrece la app del celular (antes se guardaban como "otro")
    "radiografia_panoramica", "radiografia_periapical", "foto_intraoral", "foto_facial", "estudio_modelos",
)
EXTS_AUDIO = (".webm", ".m4a", ".mp4", ".aac", ".ogg", ".wav")
EXTS_PERMITIDAS = (".jpg", ".jpeg", ".png", ".webp", ".heic", ".pdf")
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB

from fastapi.staticfiles import StaticFiles  # noqa: E402
if (WEB_UI_DIR / "vendor").is_dir():
    app.mount("/vendor", StaticFiles(directory=str(WEB_UI_DIR / "vendor")), name="vendor")


@app.get("/", response_class=HTMLResponse)
@app.get("/mobile", response_class=HTMLResponse)
async def serve_mobile_app(request: Request, t: str = ""):
    token_esperado = obtener_o_crear_movil_token()
    if t:
        if hmac.compare_digest(str(t).strip(), str(token_esperado).strip()):
            # Mostrar la app en esta misma respuesta (sin redirección) y guardar el emparejamiento.
            # SameSite=Lax: con "strict" el navegador no enviaba la cookie en la redirección cuando el
            # enlace venía de la cámara / lector de QR, y la primera vez salía "Celular no emparejado".
            from config import obtener_tema_guardado
            resp = HTMLResponse(content=_pagina_movil(obtener_tema_guardado()))
            resp.set_cookie(key="bimo_t", value=str(t).strip(), httponly=True, secure=True, samesite="lax", max_age=86400 * 30)
            return resp
        else:
            return _pagina_aviso(
                "Código no válido",
                "El código de emparejamiento es inválido o expiró. Escanea de nuevo el código QR desde BIMO en tu computadora.",
            )

    cookie_t = request.cookies.get("bimo_t", "")
    if not cookie_t or not hmac.compare_digest(str(cookie_t).strip(), str(token_esperado).strip()):
        return _pagina_aviso(
            "Celular no emparejado",
            "Para dictar y consultar pacientes desde tu celular, abre BIMO en tu computadora, ve a Celular y escanea el código QR.",
        )

    # El celular usa el mismo tema que la PC (Claro / Oscuro / Rosa)
    from config import obtener_tema_guardado
    return HTMLResponse(content=_pagina_movil(obtener_tema_guardado()))

@app.post("/api/upload-audio")
@app.post("/api/procesar_audio")
async def procesar_audio_o_texto(request: Request):
    temp_path = None
    try:
        content_type = request.headers.get("content-type", "")
        texto = None
        uploaded_file = None

        if "application/json" in content_type:
            try:
                data = await request.json()
                if isinstance(data, dict):
                    texto = data.get("texto") or data.get("text")
            except Exception:
                pass
        elif "multipart/form-data" in content_type:
            form = await request.form()
            uploaded_file = form.get("file") or form.get("audio")
            texto = form.get("texto") or form.get("text")

        if texto and str(texto).strip():
            texto_limpio = str(texto).strip()
            resultado = None
            if _CALLBACK_TEXTO:
                try:
                    resultado = _CALLBACK_TEXTO(texto_limpio)
                except Exception as e_cb:
                    print(f"[MOBILE SERVER ERROR] callback_texto: {e_cb}")
                    return JSONResponse({"ok": False, "error": str(e_cb)}, status_code=500)
            return JSONResponse({"ok": True, "message": "Texto recibido y procesado en Bimo PC.", "resultado": resultado})

        if uploaded_file and hasattr(uploaded_file, "read"):
            contents = await uploaded_file.read()
            if len(contents) > MAX_UPLOAD_BYTES:
                return JSONResponse({"ok": False, "error": "El archivo de audio excede el límite permitido de 25 MB."}, status_code=400)

            ext_audio = os.path.splitext(getattr(uploaded_file, "filename", "") or "")[1].lower()
            if ext_audio not in EXTS_AUDIO:
                ext_audio = ".webm"
            fd, temp_path = tempfile.mkstemp(prefix="bimo_mobile_", suffix=ext_audio)
            with os.fdopen(fd, "wb") as f_out:
                f_out.write(contents)

            if _CALLBACK_AUDIO:
                threading.Thread(target=_CALLBACK_AUDIO, args=(temp_path,), daemon=True).start()
            elif _CALLBACK_TEXTO:
                def _transcribir_y_procesar(path_audio):
                    try:
                        from ai_engine import transcribir_audio
                        txt = transcribir_audio(path_audio)
                        if txt and txt.strip():
                            _CALLBACK_TEXTO(txt)
                    except Exception as e_tx:
                        print(f"[MOBILE SERVER ERROR] transcribir: {e_tx}")
                    finally:
                        if path_audio and os.path.exists(path_audio):
                            try:
                                os.remove(path_audio)
                            except Exception:
                                pass
                threading.Thread(target=_transcribir_y_procesar, args=(temp_path,), daemon=True).start()

            return JSONResponse({"ok": True, "message": "Audio recibido en Bimo PC."})

        return JSONResponse({"ok": False, "error": "No se recibió archivo de audio ni texto válido."}, status_code=400)
    except Exception as e:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/pacientes")
async def api_listar_pacientes(q: str = ""):
    return buscar_pacientes(q)

@app.post("/api/paciente/telefono")
async def api_actualizar_telefono_paciente(request: Request):
    try:
        from database import actualizar_telefono_paciente_y_expediente
        datos = await request.json()
        paciente_id = datos.get("paciente_id")
        nuevo_telefono = datos.get("telefono", "")
        res = actualizar_telefono_paciente_y_expediente(paciente_id, nuevo_telefono, regenerar_pdf=True)
        return JSONResponse(res)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/paciente/{paciente_id}/contacto")
async def api_contacto_paciente(paciente_id: int):
    """Datos para escribirle o llamar al paciente desde el celular: WhatsApp con recordatorio listo y llamada."""
    import urllib.parse
    from database import obtener_paciente_por_id, get_connection
    from config import cargar_datos_clinica
    from whatsapp_service import normalizar_numero_whatsapp, generar_mensaje_recordatorio, formatear_fecha_espanol

    paciente = obtener_paciente_por_id(paciente_id)
    if not paciente:
        raise HTTPException(status_code=404, detail="Paciente no encontrado")
    conf = cargar_datos_clinica()
    cod_pais = str((conf.get("whatsapp") or {}).get("codigo_pais") or "593")

    # Próxima cita del paciente (para que el mensaje sea el recordatorio)
    cita = None
    with get_connection() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT * FROM citas_agenda
               WHERE estado != 'cancelada' AND fecha_hora_inicio >= ?
                 AND (paciente_id = ? OR (paciente_id IS NULL AND nombre_paciente = ?))
               ORDER BY fecha_hora_inicio ASC LIMIT 1""",
            (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), paciente_id, paciente.get("nombre", "")),
        )
        fila = c.fetchone()
        cita = dict(fila) if fila else None

    telefono = str(paciente.get("telefono") or "").strip()
    if (not telefono or telefono.lower() == "no especificado") and cita:
        telefono = str(cita.get("telefono") or "").strip()
    if telefono.lower() == "no especificado":
        telefono = ""

    if cita:
        mensaje = generar_mensaje_recordatorio(cita, conf)
        fecha_legible, hora_legible = formatear_fecha_espanol(cita.get("fecha_hora_inicio") or "")
        cita_info = {"fecha": fecha_legible, "hora": hora_legible, "motivo": cita.get("descripcion") or "Consulta odontológica"}
    else:
        clinica = conf.get("nombre_clinica") or "Clínica Dental BIMO"
        mensaje = f"¡Hola {paciente.get('nombre', '')}! Le saludamos cordialmente de *{clinica}*."
        cita_info = None

    numero = normalizar_numero_whatsapp(telefono, cod_pais) if telefono else ""
    return {
        "nombre": paciente.get("nombre", ""),
        "telefono": telefono,
        "whatsapp_url": f"https://wa.me/{numero}?text={urllib.parse.quote(mensaje)}" if numero else "",
        "llamar_url": f"tel:+{numero}" if numero else "",
        "mensaje": mensaje,
        "cita": cita_info,
    }


@app.get("/api/consultas/{paciente_id}")
async def api_consultas_paciente(paciente_id: int):
    return listar_consultas_paciente(paciente_id)

@app.get("/api/pdf/{consulta_id}")
async def api_obtener_pdf_consulta(consulta_id: int):
    consulta = obtener_consulta_por_id(consulta_id)
    if not consulta or not consulta.get("ruta_pdf"):
        raise HTTPException(status_code=404, detail="Historia clínica no encontrada")
    
    ruta_pdf = consulta["ruta_pdf"]
    real_pdf = os.path.realpath(str(ruta_pdf))
    from config import RUTA_PACIENTES
    real_pac = os.path.realpath(str(RUTA_PACIENTES))
    if not os.path.exists(real_pdf) or not (real_pdf.startswith(real_pac + os.sep) or real_pdf == real_pac):
        raise HTTPException(status_code=404, detail="Archivo físico PDF no encontrado o no accesible")

    return FileResponse(
        real_pdf,
        media_type="application/pdf",
        filename=os.path.basename(real_pdf)
    )

@app.post("/api/upload-foto")
async def upload_foto_clinica(
    file: UploadFile = File(...),
    paciente_id: int = Form(...),
    categoria: str = Form("radiografia"),
    descripcion: str = Form("")
):
    try:
        from database import obtener_paciente_por_id, guardar_foto_paciente_db, obtener_consulta_del_dia, actualizar_consulta_existente
        from config import RUTA_PACIENTES
        from generador_pdf import crear_historia_clinica
        import json

        # 1. Sanitizar y validar categoría
        cat_clean = re.sub(r'[^a-zA-Z0-9_]', '', str(categoria).lower().strip())
        if cat_clean not in CATEGORIAS_PERMITIDAS:
            cat_clean = "otro"

        # 2. Validar extensión permitida
        nom_orig = file.filename or "archivo.jpg"
        ext = os.path.splitext(nom_orig)[1].lower()
        if ext not in EXTS_PERMITIDAS:
            return JSONResponse({"ok": False, "error": f"Extensión '{ext}' no permitida. Formatos válidos: {', '.join(EXTS_PERMITIDAS)}"}, status_code=400)

        # 3. Validar tamaño de archivo
        contents = await file.read()
        if len(contents) > MAX_UPLOAD_BYTES:
            return JSONResponse({"ok": False, "error": "El archivo excede el tamaño máximo permitido de 25 MB."}, status_code=400)

        paciente = obtener_paciente_por_id(paciente_id)
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        nom_limpio = sanitizar_nombre_carpeta(paciente.get('nombre', ''))
        edad_num = int(paciente.get('edad') or 18)
        cat_edad = "Pacientes_Pediatricos" if edad_num < 18 else "Pacientes_Adultos"
        
        carpeta_paciente = os.path.join(
            str(RUTA_PACIENTES), cat_edad,
            f"{nom_limpio}_{edad_num}_anos_ID{paciente_id}",
            "Fotos_Radiografias"
        )

        # 4. Blindaje contra Path Traversal: asegurar que carpeta_paciente está dentro de RUTA_PACIENTES
        real_base = os.path.realpath(str(RUTA_PACIENTES))
        real_dir = os.path.realpath(carpeta_paciente)
        if not (real_dir.startswith(real_base + os.sep) or real_dir == real_base):
            return JSONResponse({"ok": False, "error": "Ruta de almacenamiento inválida."}, status_code=400)

        os.makedirs(carpeta_paciente, exist_ok=True)

        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nom_archivo = f"{cat_clean}_{ts}{ext}"
        ruta_destino = os.path.join(carpeta_paciente, nom_archivo)

        real_dest = os.path.realpath(ruta_destino)
        if not real_dest.startswith(real_dir + os.sep):
            return JSONResponse({"ok": False, "error": "Intento de escritura fuera de la carpeta del paciente."}, status_code=400)

        with open(ruta_destino, "wb") as f_out:
            f_out.write(contents)

        desc_clean = str(descripcion or "").strip()[:500]

        foto_id = guardar_foto_paciente_db(
            paciente_id=paciente_id,
            ruta_archivo=ruta_destino,
            categoria=cat_clean,
            descripcion=desc_clean
        )

        # Regenerar automáticamente el PDF de hoy para incrustar la nueva foto en la Página 3
        cons_hoy = obtener_consulta_del_dia(paciente_id)
        if cons_hoy:
            try:
                datos_json = json.loads(cons_hoy.get("json_clinico", "{}"))
                nueva_ruta_pdf = crear_historia_clinica(datos_json, paciente_id=paciente_id)
                actualizar_consulta_existente(cons_hoy["id"], datos_json, ruta_pdf=nueva_ruta_pdf)
                print(f"[FOTO INTEGRADA] PDF de {paciente.get('nombre')} actualizado con nueva foto/radiografía en Página 3.")
            except Exception as e_pdf:
                print(f"[REGEN PDF ERROR] {e_pdf}")

        return JSONResponse({
            "ok": True,
            "foto_id": foto_id,
            "mensaje": "Estudio fotográfico / radiográfico adjuntado con éxito al expediente.",
            "ruta": ruta_destino
        })
    except HTTPException:
        raise
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/fotos/{paciente_id}")
async def api_fotos_paciente(paciente_id: int):
    from database import listar_fotos_paciente
    fotos = listar_fotos_paciente(paciente_id)
    res = []
    for f in fotos:
        res.append({
            "id": f["id"],
            "categoria": f.get("categoria", "radiografia"),
            "descripcion": f.get("descripcion", ""),
            "fecha_subida": str(f.get("fecha_subida", "")),
            "url": f"/api/foto-archivo/{f['id']}"
        })
    return res

@app.get("/api/foto-archivo/{foto_id}")
async def api_obtener_archivo_foto(foto_id: int):
    from database import get_connection
    from config import RUTA_PACIENTES
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT ruta_archivo FROM fotos_pacientes WHERE id = ?", (foto_id,))
        row = c.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Archivo fotográfico no encontrado")
        real_foto = os.path.realpath(str(row["ruta_archivo"]))
        real_pac = os.path.realpath(str(RUTA_PACIENTES))
        if not os.path.exists(real_foto) or not (real_foto.startswith(real_pac + os.sep) or real_foto == real_pac):
            raise HTTPException(status_code=404, detail="Archivo fotográfico no encontrado o no accesible")
        return FileResponse(real_foto)

def iniciar_servidor_movil(callback_audio=None, callback_texto=None):
    global _CALLBACK_AUDIO, _CALLBACK_TEXTO, _SERVIDOR_HILO
    _CALLBACK_AUDIO = callback_audio
    _CALLBACK_TEXTO = callback_texto

    _asegurar_certificados_ssl()
    ip = obtener_ip_local()
    tok = obtener_o_crear_movil_token()
    url_movil = f"https://{ip}:{MOBILE_SERVER_PORT}/?t={tok}"

    if _SERVIDOR_HILO is None or not _SERVIDOR_HILO.is_alive():
        def run():
            uvicorn.run(
                app, 
                host="0.0.0.0", 
                port=MOBILE_SERVER_PORT,
                ssl_keyfile=str(RUTA_KEY),
                ssl_certfile=str(RUTA_CERT),
                log_level="warning"
            )
        
        _SERVIDOR_HILO = threading.Thread(target=run, daemon=True)
        _SERVIDOR_HILO.start()
        print(f"[MOBILE BRIDGE] Servidor HTTPS seguro iniciado en LAN con emparejamiento: {url_movil}")

    return url_movil
