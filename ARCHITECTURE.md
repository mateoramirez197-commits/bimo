# Arquitectura Técnica del Sistema BIMO
*Asistente Clínico Inteligente de Odontología (SaaS Odontológico)*

Este documento detalla la estructura completa, responsabilidades modulares y flujo de datos del proyecto **BIMO**. Todo archivo en la raíz y subcarpetas cuenta con una función específica dentro del ecosistema clínico.

---

## 1. Estructura Exhaustiva de Archivos y Directorios

```text
Bimo_Project/
│
├── web_ui/                          # Frontend Moderno (HTML5, Tailwind CSS, JS)
│   └── index.html                   # Aplicación Web Monopágina (SPA) de alta definición con diseño dark glassmorphism
│
├── ui/                              # Interfaz Gráfica Clásica Auxiliar (CustomTkinter)
│   ├── agenda_view.py               # Vista de calendario y citas en modo clásico
│   ├── animations.py                # Interpolación y curvas de animación visual
│   ├── app.py                       # Ventana principal de CustomTkinter (fallback de escritorio)
│   ├── calendar_widget.py           # Widget de calendario interactivo para selección de fechas
│   ├── correction_modal.py          # Modal de corrección manual de datos dictados
│   ├── desktop_floating_widget.py   # Widget flotante Always-on-Desk tipo isla dinámica
│   ├── dictation_view.py            # Panel de control de dictado y estado de IA
│   ├── login_view.py                # Pantalla de acceso por PIN numérico
│   ├── logo_widget.py               # Renderizado del isotipo vectorial con animación
│   ├── mobile_view.py               # Modal de emparejamiento con smartphone y código QR
│   ├── patients_view.py             # Directorio y tabla de búsqueda de pacientes
│   ├── payment_modal.py             # Modal interactivo de cobros, abonos y saldos
│   ├── pdf_preview_modal.py         # Visor integrado de PDF para modo clásico
│   └── settings_view.py             # Panel de configuración de clínica y claves API
│
├── assets/                          # Recursos multimedia estáticos
│   ├── MaterialIcons-Regular.ttf    # Fuente de iconografía del sistema
│   ├── ortodoncia/                  # Diagramas anatómicos de referencia ortodóncica
│   └── sounds/                      # Efectos auditivos (chimes de inicio, fin y confirmación)
│
├── Pacientes/                       # Almacenamiento local seguro de Historias Clínicas (PDFs)
│   ├── Pacientes_Adultos/           # Expedientes MSP Formulario 033 para pacientes adultos
│   └── Pacientes_Pediatricos/       # Expedientes MSP Formulario 033 para pacientes pediátricos
│
├── Reportes_Excel_CSV/              # Exportaciones contables y estadísticas
│   ├── *.xlsx                       # Libros completos de Excel multi-pestaña (OpenPyXL)
│   └── *.csv                        # Tablas estructuradas codificadas en UTF-8 con BOM
│
├── ai_engine.py                     # Motor de Inteligencia Artificial (Whisper + Groq LLM + Formulario 033)
├── api_server.py                    # Servidor REST FastAPI local para integraciones externas
├── audio_feedback.py                # Reproductor de retroalimentación sonora no bloqueante
├── auth.py                          # Seguridad: Hasheo PBKDF2/Argon2, validación de PIN maestro y sesiones
├── calendar_sync.py                 # Sincronización bidireccional con Google Calendar y generación de archivos .ics
├── config.py                        # Constantes globales, temas visuales y gestión de la bóveda (bimo.vault)
├── database.py                      # Capa de datos relacional SQLite (bimo.db) con modo WAL y aislamiento de homónimos
├── desktop_app.py                   # Orquestador PyWebView (Edge WebView2), puente JavaScript-Python (BimoBridge) y ventana DWM
├── export_excel.py                  # Generador de reportes contables y clínicos en Excel y CSV
├── generador_pdf.py                 # Generador de Historias Clínicas Oficiales (MSP 033) con odontograma vectorial anatómico
├── license_manager.py               # Validación criptográfica RSA de licencia comercial ligada al Hardware ID (HWID)
├── main.py                          # Punto de entrada universal de la aplicación (inicia BD, servicios y UI moderna)
├── mobile_mic_server.py             # Servidor HTTPS y WebSockets en red local para smartphone con micrófono y fotos
├── startup_manager.py               # Registro en el sistema de arranque automático de Windows (HKCU Run)
├── updater.py                       # Gestor de verificación de versiones y actualizaciones automáticas
├── voice_assistant.py               # Síntesis de voz neural en español (Edge-TTS / SAPI) para asistente manos libres
├── wake_word_listener.py            # Escucha continua en memoria RAM para detección de palabra clave ("Hey Bimo")
├── whatsapp_service.py              # Envío automatizado de recordatorios y confirmaciones por WhatsApp
├── widget_runner.py                 # Lanzador de proceso desacoplado para el widget flotante de escritorio
│
├── .env.example                     # Plantilla de variables de entorno para API keys
├── .gitignore                       # Filtro de control de versiones (protege base de datos, licencias y datos médicos)
├── base_odontograma.png             # Plantilla odontológica vectorial de alta resolución (1664x2560)
├── bimo.db                          # Base de datos local SQLite en modo WAL
├── bimo.lic                         # Archivo de licencia comercial firmado con RSA
├── bimo.vault                       # Bóveda cifrada simétrica AES-256 (Fernet) para credenciales clínicas
├── bimo_agenda.ics                  # Archivo de exportación de calendario en formato estándar iCalendar
├── bimo_cert.pem                    # Certificado SSL x509 para el servidor local HTTPS
├── bimo_key.pem                     # Clave privada SSL para el servidor local HTTPS
├── calendar_profile.json            # Tokens y estado de autenticación OAuth de Google Calendar
├── clinica.json                     # Información y configuración del consultorio dental
├── requirements.txt                 # Lista de dependencias de Python requeridas
│
├── BIMO_Pro.spec                    # Especificación de compilación comercial con PyInstaller
├── build_exe.py                     # Script Python para compilar el ejecutable de producción BIMO_Pro.exe
├── compilar_exe.bat                 # Acceso rápido en Windows para compilar a ejecutable
├── crear_instalador.py              # Generador del instalador empaquetado final
├── crear_instalador.bat             # Acceso rápido para generar el instalador
├── ejecutar_bimo.bat                # Lanzador directo de BIMO para Windows sin consola
├── setup_instalador.py              # Script de configuración inicial post-instalación y creación de accesos directos
└── BIMO_Pro_Mac.command             # Lanzador nativo ejecutable de doble clic para macOS
```

---

## 2. Descripción Funcional por Componente

### A. Núcleo de la Aplicación y Presentación
- **`main.py`**: Es el orquestador principal. Inicializa SQLite, purga datos residuales de prueba, valida la licencia comercial, comprueba actualizaciones e inicia la interfaz moderna basada en WebView2 (con fallback automático a CustomTkinter si es necesario).
- **`desktop_app.py`**: Controla la ventana nativa mediante PyWebView. Aplica atributos nativos de Desktop Window Manager (DWM) en Windows para esquinas redondeadas, redimensionamiento nativo (`WS_THICKFRAME`), control estricto de maximizado que respeta la barra de tareas de Windows (`MaximizedBounds` ligado al `WorkingArea`), y expone la clase `BimoBridge` para comunicar la UI web con el backend en Python.
- **`web_ui/index.html`**: Frontend unificado y responsivo. Contiene la barra superior personalizada frameless con controles de ventana estilizados, paneles de captura de dictado en tiempo real, agenda con vista semanal y mensual, directorio deslizable de pacientes, visor integrado de PDFs clínicos y centro de sincronización móvil.

### B. Inteligencia Artificial, Audio y Voz
- **`ai_engine.py`**: Procesa la voz con Faster-Whisper, aplica normalización fonética de números clínicos y dientes, y utiliza modelos LLM a través de Groq API para estructurar automáticamente el Formulario 033 del Ministerio de Salud Pública (MSP).
- **`wake_word_listener.py`**: Escucha activa en segundo plano a 44100Hz con búfer circular en memoria para reconocer comandos como "Bimo, agenda una cita..." de manera no intrusiva.
- **`voice_assistant.py`**: Provee retroalimentación por voz neural usando Edge-TTS (o SAPI local como respaldo) para confirmar citas y acciones al usuario.
- **`audio_feedback.py`**: Emite chimes auditivos claros e instantáneos al iniciar dictado, finalizar grabación o confirmar una operación exitosa.

### C. Persistencia y Generación de Documentos
- **`database.py`**: Gestiona las tablas de pacientes, historias clínicas, consultas, citas de agenda y finanzas. Incluye aislamiento estricto de homónimos (no sobrescribe pacientes con mismo nombre si la edad difiere por más de 3 años o tienen cédulas distintas).
- **`generador_pdf.py`**: Genera expedientes clínicos de 2 páginas (odontología general) o 3 páginas (ortodoncia) con ReportLab, dibujando la anatomía dental completa del odontograma en alta resolución sobre `base_odontograma.png`.
- **`export_excel.py`**: Exporta los registros a archivos `.xlsx` y `.csv` multi-hoja con métricas financieras y clínicas.
- **`calendar_sync.py`**: Mantiene sincronizada la agenda local con Google Calendar mediante OAuth2 y exporta a formato `.ics`.
- **`whatsapp_service.py`**: Genera y despacha recordatorios de citas automáticas para el día siguiente con plantillas personalizables.

### D. Conectividad Móvil y Seguridad
- **`mobile_mic_server.py`**: Levanta un servidor web HTTPS seguro en la red local y genera un código QR para que cualquier smartphone funcione como micrófono inalámbrico o cámara clínica.
- **`auth.py`**: Gestiona el PIN de acceso maestro (`1234`), hash seguro de contraseñas y sesiones activas.
- **`license_manager.py`**: Protege la aplicación contra copias no autorizadas ligándola a la firma criptográfica del hardware (HWID).
- **`config.py`**: Almacena de forma segura las credenciales en `bimo.vault` con cifrado AES-256 Fernet.
