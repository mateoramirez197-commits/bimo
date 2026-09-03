import os
import socket
import threading
import datetime
from pathlib import Path
import qrcode
from PIL import Image
import re
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from config import MOBILE_SERVER_PORT, BASE_DIR
from database import buscar_pacientes, listar_consultas_paciente, obtener_consulta_por_id

app = FastAPI(title="BIMO Mobile Bridge & Clinical Viewer")

_CALLBACK_AUDIO = None
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
# WEB APP MÓVIL (HTTPS 100% AUDIO - CERO CÁMARA)
# ==========================================
HTML_MOVIL = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>BIMO Micrófono Clínico</title>
    <style>
        :root {
            --bg-app: #080C14;
            --card-app: #101622;
            --accent-app: #00F5D4;
            --border-app: #1E293B;
            --btn-app: #0284C7;
            --txt-app: #FFFFFF;
            --txt-muted: #94A3B8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
        body {
            background-color: var(--bg-app);
            color: var(--txt-app);
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }
        header {
            background: var(--card-app);
            padding: 16px 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid var(--border-app);
        }
        .brand { font-size: 22px; font-weight: 900; letter-spacing: 2px; }
        .brand span.b { color: #00F5D4; }
        .brand span.i { color: #70D6FF; }
        .brand span.m { color: #FF006E; }
        .brand span.o { color: #FFBE0B; }
        .doc-badge { font-size: 11px; color: #00F5D4; background: rgba(0, 245, 212, 0.1); padding: 4px 10px; border-radius: 12px; font-weight: 700; }

        .main-content {
            flex: 1;
            padding: 24px 16px;
            display: flex;
            flex-direction: column;
            align-items: center;
            overflow-y: auto;
        }

        .tab-content { width: 100%; max-width: 480px; display: none; }
        .tab-content.active { display: flex; flex-direction: column; align-items: center; }

        .mic-wrapper { margin: 40px 0 20px; text-align: center; }
        .btn-mic {
            width: 170px;
            height: 170px;
            border-radius: 50%;
            background: radial-gradient(circle, #1e293b, #0f172a);
            border: 4px solid #00F5D4;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto;
            cursor: pointer;
            box-shadow: 0 10px 30px rgba(0, 245, 212, 0.25);
            transition: all 0.3s ease;
            -webkit-tap-highlight-color: transparent;
        }
        .btn-mic svg { width: 75px; height: 75px; fill: #00F5D4; transition: all 0.3s; }
        .btn-mic.recording {
            background: #FF006E;
            border-color: #ff3388;
            box-shadow: 0 0 45px rgba(255, 0, 110, 0.75);
            animation: pulse 1.3s infinite;
        }
        .btn-mic.recording svg { fill: #ffffff; }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.06); }
            100% { transform: scale(1); }
        }

        .status-pill {
            margin-top: 22px;
            padding: 10px 22px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            background: #161f30;
            border: 1px solid #24324a;
            color: #94a3b8;
            text-align: center;
        }
        .status-pill.recording { background: rgba(255, 0, 110, 0.2); border-color: #FF006E; color: #ff3388; }
        .status-pill.success { background: rgba(0, 245, 212, 0.2); border-color: #00F5D4; color: #00F5D4; }

        .instruction-box {
            background: #161f30;
            border: 1px solid #24324a;
            padding: 16px;
            border-radius: 12px;
            font-size: 12px;
            color: #94a3b8;
            line-height: 1.6;
            max-width: 340px;
            margin-top: 24px;
            text-align: left;
        }

        /* Directorio de Pacientes y Visor de PDF */
        .search-box {
            width: 100%;
            padding: 12px 16px;
            background: #161f30;
            border: 1px solid #24324a;
            border-radius: 10px;
            color: #ffffff;
            font-size: 14px;
            margin-bottom: 16px;
        }
        .patient-card {
            width: 100%;
            background: #161f30;
            border: 1px solid #24324a;
            border-radius: 12px;
            padding: 14px 16px;
            margin-bottom: 12px;
            text-align: left;
        }
        .patient-name { font-size: 16px; font-weight: 700; color: #70d6ff; }
        .patient-meta { font-size: 12px; color: #94a3b8; margin: 4px 0 10px; }
        .btn-view-history {
            background: #3A86FF;
            color: white;
            border: none;
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
        }
        .consultations-list { margin-top: 10px; padding-top: 10px; border-top: 1px solid #24324a; }
        .consultation-item {
            background: #0b0f19;
            padding: 10px 12px;
            border-radius: 8px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .cons-date { font-size: 12px; color: #f8fafc; }
        .btn-open-pdf {
            background: #00F5D4;
            color: #0b0f19;
            text-decoration: none;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 800;
        }

        /* Barra Inferior de Pestañas */
        nav.bottom-nav {
            background: #161f30;
            border-top: 1px solid #24324a;
            display: flex;
            height: 60px;
        }
        .nav-tab {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 600;
            color: #64748b;
            cursor: pointer;
            transition: all 0.2s;
        }
        .nav-tab.active { color: #00F5D4; border-top: 2px solid #00F5D4; }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <span class="b">B</span><span class="i">I</span><span class="m">M</span><span class="o">O</span>
        </div>
        <div class="doc-badge">🔒 Enlace Seguro HTTPS</div>
    </header>

    <div class="main-content">
        <!-- PESTAÑA 1: MICRÓFONO INALÁMBRICO PURO (SIN CÁMARA) -->
        <div id="tabMic" class="tab-content active">
            <div class="mic-wrapper">
                <button id="btnMic" class="btn-mic">
                    <svg viewBox="0 0 24 24">
                        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z"/>
                        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                    </svg>
                </button>
                <div id="statusLabel" class="status-pill">Toca el micrófono para comenzar</div>
            </div>

            <div class="instruction-box">
                🎙️ <strong>Dictado Directo (Solo Micrófono):</strong><br>
                1. Toca el botón verde para iniciar el dictado.<br>
                2. Dicta los hallazgos clínicos o comandos tipo:<br>
                <span style="color:#FFBE0B;">"Bimo, una cita para Mateo Ramírez para el 2 de febrero a las 3 de la tarde"</span>.<br>
                3. Vuelve a tocar el botón rojo para enviar al PC.
            </div>
        </div>

        <!-- PESTAÑA 2: HISTORIAS Y VISOR PDF -->
        <div id="tabPatients" class="tab-content">
            <input type="text" id="inputSearch" class="search-box" placeholder="🔍 Buscar paciente por nombre...">
            <div id="patientsContainer" style="width: 100%;">
                <div style="text-align: center; color: #64748b; margin-top: 30px;">Cargando directorio de pacientes...</div>
            </div>
        </div>

        <!-- PESTAÑA 3: RADIOGRAFÍAS Y FOTOS CLÍNICAS -->
        <div id="tabPhotos" class="tab-content">
            <div class="patient-card" style="margin-bottom: 14px;">
                <label style="font-size: 11px; font-weight: 700; color: #70d6ff; text-transform: uppercase;">1. Seleccionar Paciente:</label>
                <select id="selectPhotoPatient" class="search-box" style="margin-top: 6px; margin-bottom: 12px; background: #0b0f19;" onchange="cargarFotosPacienteSeleccionado()">
                    <option value="">Cargando pacientes...</option>
                </select>

                <label style="font-size: 11px; font-weight: 700; color: #70d6ff; text-transform: uppercase;">2. Tipo de Estudio Clínico:</label>
                <select id="selectPhotoCategory" class="search-box" style="margin-top: 6px; margin-bottom: 12px; background: #0b0f19;">
                    <option value="radiografia_panoramica">Radiografía Panorámica Digital</option>
                    <option value="radiografia_periapical">Radiografía Periapical</option>
                    <option value="foto_intraoral">Fotografía Intraoral (Frontal / Oclusal)</option>
                    <option value="foto_facial">Fotografía Facial / Perfil de Ortodoncia</option>
                    <option value="estudio_modelos">Estudio Cefalométrico / Modelos</option>
                </select>

                <label style="font-size: 11px; font-weight: 700; color: #70d6ff; text-transform: uppercase;">3. Capturar o Seleccionar Imagen:</label>
                <div style="margin-top: 8px;">
                    <input type="file" id="inputPhotoFile" accept="image/*" capture="environment" style="display: none;" onchange="previewSelectedPhoto(this)">
                    <button type="button" class="btn-view-history" style="width: 100%; padding: 12px; font-size: 13px; background: #1b365d; border: 1px dashed #70d6ff; border-radius: 8px;" onclick="document.getElementById('inputPhotoFile').click()">
                        📷 Abrir Cámara o Elegir de Galería
                    </button>
                </div>

                <div id="previewContainer" style="display: none; margin-top: 14px; text-align: center;">
                    <img id="imgPreview" style="max-width: 100%; max-height: 180px; border-radius: 8px; border: 1px solid #38bdf8;" />
                    <p id="lblPreviewInfo" style="font-size: 11px; color: #94a3b8; margin-top: 4px;"></p>
                    <button id="btnUploadPhoto" class="btn-view-history" style="width: 100%; margin-top: 8px; background: #00F5D4; color: #0b0f19; font-weight: 800; font-size: 13px;" onclick="subirFotoClinica()">
                        📤 Subir y Adjuntar a Historia Clínica
                    </button>
                </div>
                <div id="uploadStatus" style="margin-top: 8px; font-size: 12px; text-align: center; color: #70d6ff; font-weight: bold;"></div>
            </div>

            <div style="margin-top: 14px;">
                <h4 style="font-size: 13px; color: #cbd5e1; margin-bottom: 8px;">🖼️ Estudios y Radiografías Adjuntadas</h4>
                <div id="patientPhotosGrid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <div style="grid-column: 1 / -1; text-align: center; color: #64748b; font-size: 12px;">Selecciona un paciente para ver sus estudios.</div>
                </div>
            </div>
        </div>
    </div>

    <nav class="bottom-nav">
        <div id="navMic" class="nav-tab active" onclick="switchTab('mic')">
            <span>🎙️ Dictar</span>
        </div>
        <div id="navPhotos" class="nav-tab" onclick="switchTab('photos')">
            <span>📷 Radiografías</span>
        </div>
        <div id="navPatients" class="nav-tab" onclick="switchTab('patients')">
            <span>📋 Historias</span>
        </div>
    </nav>

    <script>
        let mediaRecorder;
        let audioChunks = [];
        let isRecording = false;

        const btnMic = document.getElementById('btnMic');
        const statusLabel = document.getElementById('statusLabel');

        btnMic.addEventListener('click', async () => {
            if (!isRecording) {
                try {
                    // Solicitud explícita de audio puro (CERO cámara de video)
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
                    
                    // Elegir formato de audio admitido nativamente por el teléfono
                    let mimeType = 'audio/webm';
                    if (!MediaRecorder.isTypeSupported('audio/webm')) {
                        if (MediaRecorder.isTypeSupported('audio/mp4')) {
                            mimeType = 'audio/mp4';
                        } else if (MediaRecorder.isTypeSupported('audio/aac')) {
                            mimeType = 'audio/aac';
                        }
                    }

                    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
                    audioChunks = [];

                    mediaRecorder.ondataavailable = e => {
                        if (e.data && e.data.size > 0) audioChunks.push(e.data);
                    };

                    mediaRecorder.onstop = async () => {
                        statusLabel.textContent = "Transmitiendo audio a Bimo PC...";
                        statusLabel.className = "status-pill";

                        const audioBlob = new Blob(audioChunks, { type: mimeType || 'audio/wav' });
                        const formData = new FormData();
                        formData.append('file', audioBlob, 'mobile_audio.webm');

                        try {
                            const res = await fetch('/api/upload-audio', { method: 'POST', body: formData });
                            const data = await res.json();
                            if (data.ok) {
                                statusLabel.textContent = "✅ Audio procesado en Bimo PC";
                                statusLabel.className = "status-pill success";
                            } else {
                                statusLabel.textContent = "Error al procesar audio";
                            }
                        } catch (err) {
                            statusLabel.textContent = "Error de enlace LAN con el PC";
                        }
                    };

                    mediaRecorder.start();
                    isRecording = true;
                    btnMic.classList.add('recording');
                    statusLabel.textContent = "🔴 Grabando voz... Toca para detener";
                    statusLabel.className = "status-pill recording";

                } catch (err) {
                    statusLabel.textContent = "Acceso al micrófono denegado";
                    alert("Por favor permite el acceso al micrófono en tu navegador móvil.");
                }
            } else {
                mediaRecorder.stop();
                isRecording = false;
                btnMic.classList.remove('recording');
            }
        });

        function switchTab(tab) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.nav-tab').forEach(el => el.classList.remove('active'));

            if (tab === 'mic') {
                document.getElementById('tabMic').classList.add('active');
                document.getElementById('navMic').classList.add('active');
            } else if (tab === 'photos') {
                document.getElementById('tabPhotos').classList.add('active');
                document.getElementById('navPhotos').classList.add('active');
                cargarPacientesSelect();
            } else {
                document.getElementById('tabPatients').classList.add('active');
                document.getElementById('navPatients').classList.add('active');
                cargarPacientes();
            }
        }

        async function cargarPacientesSelect() {
            const sel = document.getElementById('selectPhotoPatient');
            try {
                const res = await fetch('/api/pacientes');
                const pacs = await res.json();
                if (!pacs.length) {
                    sel.innerHTML = '<option value="">No hay pacientes registrados</option>';
                    return;
                }
                sel.innerHTML = pacs.map(p => `<option value="${p.id}">${p.nombre} (${p.edad || 'N/E'}a - ID:${p.id})</option>`).join('');
                cargarFotosPacienteSeleccionado();
            } catch (err) {
                sel.innerHTML = '<option value="">Error al cargar pacientes</option>';
            }
        }

        let archivoFotoSeleccionado = null;

        function previewSelectedPhoto(input) {
            if (input.files && input.files[0]) {
                archivoFotoSeleccionado = input.files[0];
                const reader = new FileReader();
                reader.onload = function(e) {
                    document.getElementById('imgPreview').src = e.target.result;
                    document.getElementById('lblPreviewInfo').innerText = archivoFotoSeleccionado.name + ' (' + Math.round(archivoFotoSeleccionado.size / 1024) + ' KB)';
                    document.getElementById('previewContainer').style.display = 'block';
                    document.getElementById('uploadStatus').innerText = '';
                };
                reader.readAsDataURL(archivoFotoSeleccionado);
            }
        }

        async function subirFotoClinica() {
            if (!archivoFotoSeleccionado) {
                alert('Por favor selecciona o toma una fotografía primero.');
                return;
            }
            const pacId = document.getElementById('selectPhotoPatient').value;
            if (!pacId) {
                alert('Por favor selecciona un paciente.');
                return;
            }
            const cat = document.getElementById('selectPhotoCategory').value;
            const btn = document.getElementById('btnUploadPhoto');
            const statusDiv = document.getElementById('uploadStatus');

            btn.disabled = true;
            btn.innerText = '⏳ Subiendo y adjuntando al PDF...';
            statusDiv.innerText = 'Procesando imagen clínica...';

            const formData = new FormData();
            formData.append('file', archivoFotoSeleccionado);
            formData.append('paciente_id', pacId);
            formData.append('categoria', cat);

            try {
                const res = await fetch('/api/upload-foto', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (data.ok) {
                    statusDiv.innerText = '✅ ¡Estudio adjuntado exitosamente al expediente!';
                    statusDiv.style.color = '#00F5D4';
                    document.getElementById('previewContainer').style.display = 'none';
                    archivoFotoSeleccionado = null;
                    document.getElementById('inputPhotoFile').value = '';
                    cargarFotosPacienteSeleccionado();
                } else {
                    statusDiv.innerText = '❌ ' + (data.error || 'Error al subir imagen');
                    statusDiv.style.color = '#ef4444';
                }
            } catch (err) {
                statusDiv.innerText = '❌ Error de conexión con el servidor BIMO.';
                statusDiv.style.color = '#ef4444';
            } finally {
                btn.disabled = false;
                btn.innerText = '📤 Subir y Adjuntar a Historia Clínica';
            }
        }

        async function cargarFotosPacienteSeleccionado() {
            const pacId = document.getElementById('selectPhotoPatient').value;
            const grid = document.getElementById('patientPhotosGrid');
            if (!pacId) {
                grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:#64748b;font-size:12px;">Selecciona un paciente.</div>';
                return;
            }
            grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:#94a3b8;font-size:11px;">Cargando fotos...</div>';
            try {
                const res = await fetch('/api/fotos/' + pacId);
                const fotos = await res.json();
                if (!fotos.length) {
                    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;color:#64748b;font-size:12px;">No hay radiografías ni fotos adjuntadas aún.</div>';
                    return;
                }
                grid.innerHTML = fotos.map(f => `
                    <div style="background:#0b0f19;border:1px solid #24324a;border-radius:8px;padding:8px;text-align:center;">
                        <a href="${f.url}" target="_blank">
                            <img src="${f.url}" style="width:100%;height:100px;object-fit:cover;border-radius:6px;border:1px solid #1e293b;" />
                        </a>
                        <div style="font-size:10px;font-weight:bold;color:#70d6ff;margin-top:4px;">${f.categoria.replace('_', ' ').toUpperCase()}</div>
                        <div style="font-size:9px;color:#94a3b8;">${f.fecha_subida.split(' ')[0]}</div>
                    </div>
                `).join('');
            } catch (err) {
                grid.innerHTML = '<div style="grid-column:1/-1;color:#ef4444;font-size:11px;text-align:center;">Error al cargar fotos.</div>';
            }
        }

        async function cargarPacientes(query = '') {
            const container = document.getElementById('patientsContainer');
            try {
                const res = await fetch('/api/pacientes?q=' + encodeURIComponent(query));
                const pacientes = await res.json();

                if (!pacientes.length) {
                    container.innerHTML = '<div style="text-align:center;color:#64748b;margin-top:30px;">No hay pacientes registrados.</div>';
                    return;
                }

                container.innerHTML = pacientes.map(p => `
                    <div class="patient-card">
                        <div class="patient-name">${p.nombre}</div>
                        <div class="patient-meta">Cédula: ${p.documento || 'N/E'} | Edad: ${p.edad || 'N/E'} años</div>
                        <button class="btn-view-history" onclick="toggleConsultas(${p.id})">📂 Ver Consultas (${p.total_consultas || 0})</button>
                        <div id="consultas_${p.id}" class="consultations-list" style="display:none;"></div>
                    </div>
                `).join('');
            } catch (err) {
                container.innerHTML = '<div style="color:#ef4444;text-align:center;">Error al cargar directorio.</div>';
            }
        }

        document.getElementById('inputSearch').addEventListener('input', (e) => {
            cargarPacientes(e.target.value);
        });

        async function toggleConsultas(pacienteId) {
            const listDiv = document.getElementById('consultas_' + pacienteId);
            if (listDiv.style.display === 'none') {
                listDiv.innerHTML = '<div style="font-size:11px;color:#94a3b8;">Cargando consultas...</div>';
                listDiv.style.display = 'block';
                try {
                    const res = await fetch('/api/consultas/' + pacienteId);
                    const consultas = await res.json();
                    if (!consultas.length) {
                        listDiv.innerHTML = '<div style="font-size:11px;color:#64748b;">Sin consultas registradas.</div>';
                        return;
                    }
                    listDiv.innerHTML = consultas.map(c => `
                        <div class="consultation-item">
                            <div class="cons-date">🗓️ ${c.fecha_hora.split(' ')[0]}</div>
                            <div style="display:flex;gap:6px;">
                                ${c.ruta_pdf ? `
                                    <a class="btn-open-pdf" href="/api/pdf/${c.id}" target="_blank">📄 Ver</a>
                                    <a class="btn-open-pdf" href="/api/pdf/${c.id}" download style="background:#2563eb;color:#ffffff;">📥 Descargar</a>
                                ` : '<span style="font-size:10px;color:#64748b;">Sin PDF</span>'}
                            </div>
                        </div>
                    `).join('');
                } catch (err) {
                    listDiv.innerHTML = '<div style="color:#ef4444;font-size:11px;">Error al cargar consultas.</div>';
                }
            } else {
                listDiv.style.display = 'none';
            }
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def serve_mobile_app():
    from config import obtener_tema_activo_dict
    t = obtener_tema_activo_dict()
    logo_cols = t.get("logo_colors", [t.get("aqua", "#00F5D4"), t.get("azul_pastel", "#70D6FF"), t.get("fucsia", "#FF006E"), t.get("amarillo", "#FFBE0B")])
    css_override = f"""
    <style id="theme-override">
        :root {{
            --bg-app: {t['bg_dark']};
            --card-app: {t['card_dark']};
            --accent-app: {t['aqua']};
            --border-app: {t['border']};
            --btn-app: {t['azul_acero']};
            --txt-app: {t['text_primary']};
            --txt-muted: {t['text_muted']};
            --logo-b: {logo_cols[0]};
            --logo-i: {logo_cols[1]};
            --logo-m: {logo_cols[2]};
            --logo-o: {logo_cols[3]};
        }}
        .brand .b {{ color: var(--logo-b) !important; }}
        .brand .i {{ color: var(--logo-i) !important; }}
        .brand .m {{ color: var(--logo-m) !important; }}
        .brand .o {{ color: var(--logo-o) !important; }}
    </style>
    """
    html_custom = HTML_MOVIL.replace("</head>", f"{css_override}\n</head>")
    return HTMLResponse(content=html_custom)

@app.post("/api/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        with open(_ULTIMO_AUDIO_RUTA, "wb") as f:
            f.write(contents)

        if _CALLBACK_AUDIO:
            threading.Thread(target=_CALLBACK_AUDIO, args=(_ULTIMO_AUDIO_RUTA,)).start()

        return JSONResponse({"ok": True, "message": "Audio recibido en Bimo PC."})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@app.get("/api/pacientes")
async def api_listar_pacientes(q: str = ""):
    return buscar_pacientes(q)

@app.get("/api/consultas/{paciente_id}")
async def api_consultas_paciente(paciente_id: int):
    return listar_consultas_paciente(paciente_id)

@app.get("/api/pdf/{consulta_id}")
async def api_obtener_pdf_consulta(consulta_id: int):
    consulta = obtener_consulta_por_id(consulta_id)
    if not consulta or not consulta.get("ruta_pdf"):
        raise HTTPException(status_code=404, detail="Historia clínica no encontrada")
    
    ruta_pdf = consulta["ruta_pdf"]
    if not os.path.exists(ruta_pdf):
        raise HTTPException(status_code=404, detail="Archivo físico PDF no encontrado en el servidor")

    return FileResponse(
        ruta_pdf,
        media_type="application/pdf",
        filename=os.path.basename(ruta_pdf)
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
        from generador_pdf import BASE_DIR, crear_historia_clinica
        import json

        paciente = obtener_paciente_por_id(paciente_id)
        if not paciente:
            raise HTTPException(status_code=404, detail="Paciente no encontrado")

        nom_limpio = re.sub(r'[^a-zA-Z0-9_]', '', paciente.get('nombre', '').replace(' ', '_')) or "Paciente"
        edad_num = int(paciente.get('edad') or 18)
        cat_edad = "Pacientes_Pediatricos" if edad_num < 18 else "Pacientes_Adultos"
        
        carpeta_paciente = os.path.join(
            BASE_DIR, "Pacientes", cat_edad,
            f"{nom_limpio}_{edad_num}_anos_ID{paciente_id}",
            "Fotos_Radiografias"
        )
        os.makedirs(carpeta_paciente, exist_ok=True)

        ext = os.path.splitext(file.filename)[1] or ".jpg"
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        nom_archivo = f"{categoria}_{ts}{ext}"
        ruta_destino = os.path.join(carpeta_paciente, nom_archivo)

        contents = await file.read()
        with open(ruta_destino, "wb") as f_out:
            f_out.write(contents)

        foto_id = guardar_foto_paciente_db(
            paciente_id=paciente_id,
            ruta_archivo=ruta_destino,
            categoria=categoria,
            descripcion=descripcion
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
    with get_connection() as conn:
        c = conn.cursor()
        c.execute("SELECT ruta_archivo FROM fotos_pacientes WHERE id = ?", (foto_id,))
        row = c.fetchone()
        if not row or not os.path.exists(row["ruta_archivo"]):
            raise HTTPException(status_code=404, detail="Archivo fotográfico no encontrado")
        return FileResponse(row["ruta_archivo"])

def iniciar_servidor_movil(callback_audio=None):
    global _CALLBACK_AUDIO, _SERVIDOR_HILO
    _CALLBACK_AUDIO = callback_audio

    _asegurar_certificados_ssl()
    ip = obtener_ip_local()
    url_movil = f"https://{ip}:{MOBILE_SERVER_PORT}"

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
        print(f"[MOBILE BRIDGE] Servidor HTTPS seguro iniciado en LAN: {url_movil}")

    return url_movil
