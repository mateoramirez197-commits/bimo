# Arquitectura Técnica del Sistema BIMO
*Asistente Clínico Inteligente de Odontología (SaaS Odontológico)*

Este documento detalla la estructura completa, responsabilidades modulares y flujo de datos del proyecto **BIMO**. Todo archivo en la raíz y subcarpetas cuenta con una función específica dentro del ecosistema clínico.

---

## 1. Estructura Exhaustiva de Archivos y Directorios

```text
Bimo_Project/
│
├── web_ui/                          # Frontend Moderno Quirúrgico (HTML5, Tailwind CSS, JS)
│   └── index.html                   # Suite Clínica SPA de alta definición (Titanio Quirúrgico & Blanco Instrumental)
│
├── tests/                           # Suite de Verificación, Pruebas de Estrés y Telemetría
│   ├── test_ui_integrity.py         # Verificación automatizada de IDs, modales y sintaxis JS
│   ├── test_pdf_speed_and_refresh.py # Verificación de generación de PDFs a 0.3s y sincronización de menús
│   ├── test_pin_and_google_calendar.py # Verificación de seguridad de PIN y Google Calendar authuser
│   ├── test_pacientes_pdf_structure.py # Control de carpetas y aislamiento anti-sobrescritura
│   ├── test_dictation_isolated.py   # Pruebas de hardware de audio y transcripción Whisper
│   ├── test_stress_1hour.py         # Suite completa de estrés continuo de 1 hora
│   ├── test_endurance_shift.py      # Pruebas de resistencia para jornada médica extendida
│   └── reports/                     # Reportes estructurados de telemetría y rendimiento (.json)
│
├── ui/                              # Interfaz Gráfica Auxiliar (CustomTkinter)
│   ├── desktop_floating_widget.py   # Widget flotante Always-on-Desk tipo isla dinámica
│   ├── animations.py                # Interpolación y curvas de animación visual
│   ├── app.py                       # Ventana principal clásica (fallback)
│   ├── dictation_view.py            # Panel de dictado clásico
│   ├── patients_view.py             # Directorio de pacientes clásico
│   └── ...                          # Componentes gráficos de soporte
│
├── assets/                          # Recursos multimedia estáticos
│   ├── bimo_icon.ico                # Icono oficial de aplicación para Windows
│   ├── bimo_icon.png                # Isotipo en alta resolución
│   ├── MaterialIcons-Regular.ttf    # Fuente de iconografía del sistema
│   ├── ortodoncia/                  # Diagramas anatómicos de referencia ortodóncica
│   └── sounds/                      # Efectos auditivos clínicos
│
├── Pacientes/                       # Almacenamiento local seguro de Historias Clínicas (PDFs)
│   ├── Pacientes_Adultos/           # Expedientes MSP Formulario 033 para pacientes adultos (>=18 años)
│   └── Pacientes_Pediatricos/       # Expedientes MSP Formulario 033 para pacientes pediátricos (<18 años)
│
├── Reportes_Excel_CSV/              # Exportaciones contables y estadísticas
│   ├── *.xlsx                       # Libros completos de Excel multi-pestaña
│   └── *.csv                        # Tablas estructuradas codificadas en UTF-8 con BOM
│
├── ai_engine.py                     # Motor de IA Clínica (Faster-Whisper + Groq LLaMA 3.3 70B)
├── api_server.py                    # Servidor REST FastAPI local para integraciones
├── audio_feedback.py                # Reproductor de retroalimentación sonora no bloqueante
├── auth.py                          # Seguridad: Hasheo PBKDF2/Argon2, validación de PIN y sesiones
├── calendar_sync.py                 # Sincronización bidireccional con Google Calendar y archivos .ics
├── config.py                        # Constantes globales, temas visuales y rutas unificadas
├── database.py                      # Capa relacional SQLite (bimo.db) en modo WAL y auto-sanación
├── desktop_app.py                   # Orquestador PyWebView, puente bidireccional BimoBridge y ventana DWM
├── export_excel.py                  # Generador de reportes contables y clínicos en Excel y CSV
├── generador_pdf.py                 # Generador ultra-rápido de Historias Clínicas (MSP 033) a 0.3s
├── license_manager.py               # Validación criptográfica RSA de licencia comercial ligada a HWID
├── main.py                          # Punto de entrada universal de la aplicación BIMO Pro
├── mobile_mic_server.py             # Servidor HTTPS y WebSockets en red local para smartphone por QR
├── startup_manager.py               # Registro en arranque automático de Windows (HKCU Run)
├── updater.py                       # Gestor de verificación de versiones y actualizaciones automáticas
├── voice_assistant.py               # Síntesis neural Edge-TTS/SAPI con timeout y fallback no bloqueante
├── wake_word_listener.py            # Detección de palabra clave "Bimo" con watchdog acelerado
├── whatsapp_service.py              # Envío automatizado de recordatorios por WhatsApp
├── widget_runner.py                 # Lanzador desacoplado para widget flotante de escritorio
│
├── base_odontograma.png             # Plantilla odontológica vectorial de alta resolución (1664x2560)
├── mascaras_odontograma.npz         # Máscaras booleanas serializadas para coloreado inmediato (0.01s)
├── vocabulario_aprendido.json       # Léxico fonético odontológico y ecuatoriano aprendido
├── clinica.json                     # Información y configuración del consultorio dental
├── requirements.txt                 # Dependencias oficiales de Python
├── .env.example                     # Plantilla de variables de entorno
├── .gitignore                       # Blindaje de seguridad (ignora llaves, bimo.db y PDFs clínicos)
│
├── build_exe.py                     # Compilador maestro de la distribución autónoma dist/BIMO_Pro
├── crear_setup_exe.py               # Constructor del instalador universal comercial Setup_BIMO_Pro.exe
├── installer_gui_wizard.py          # Asistente gráfico de instalación para el usuario final
├── uninstaller_gui.py               # Asistente gráfico de desinstalación limpia de Windows
├── generar_icono_bot.py             # Generador de icono vectorizado
├── ejecutar_bimo.bat                # Lanzador rápido de Windows sin consola negra
├── INSTALAR_BIMO.bat                # Instalador desatendido para despliegue por terminal
└── setup_instalador.py              # Script de configuración de entorno y carpetas
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
