# 🏥 BIMO - Asistente Clínico Inteligente (SaaS Odontológico)

BIMO es una plataforma integral de escritorio y móvil diseñada para clínicas odontológicas y ortodóncicas. Automatiza la captura del historial clínico mediante voz en tiempo real, digitalización anatómica del odontograma en alta definición, control financiero de cobros y abonos, y sincronización de citas con Google Calendar.

---

## 🌟 Características Principales

- **Interfaz Moderna de Alta Fidelidad:** Ventana personalizada sin bordes rígidos con controles estilizados, esquinas redondeadas DWM, y maximizado inteligente que respeta la barra de tareas de Windows.
- **Dictado Clínico Neuronal:** Transcripción mediante Faster-Whisper y estructuración semántica con Groq API.
- **Escucha Activa de Fondo (*Hands-Free*):** Detección de palabra clave "Bimo" para agendamiento y reprogramación de citas.
- **Odontograma Visual Anatómico Digitalizado:** Mapeo anatómico en formato FDI con cobertura dental morfológica completa en 4 colores:
  - 🔴 Rojo: Patología activa (caries, fracturas, dolor, movilidad).
  - 🔵 Azul: Tratamientos y restauraciones previas en buen estado.
  - ⚫ Gris: Piezas ausentes o exodoncias.
  - ⚪ Natural: Estructura sana.
- **Historias Clínicas en PDF Oficiales (MSP Formulario 033):**
  - **General (2 páginas):** Odontograma visual, resumen, y Consentimiento Informado General con firmas en la Página 2.
  - **Ortodoncia (3 páginas):** Ficha Especializada de Ortodoncia, relaciones oclusales (Angle), análisis cefalométrico y evolución clínica dinámica.
- **Control de Cuentas y Pagos:** Registro de costo, abono y saldo pendiente con recálculo dinámico en modal interactivo.
- **Aislamiento Estricto de Pacientes y Homónimos:** Diferenciación automática de pacientes con nombres similares basándose en edad y documento de identidad.
- **Exportación Contable:** Generación de reportes ejecutivos en Excel multi-pestaña (`.xlsx`) y `.csv` codificado en UTF-8-BOM en la carpeta `Reportes_Excel_CSV/`.
- **App Móvil PWA:** Servidor HTTPS local y WebSockets para dictado y consulta de expedientes desde el smartphone.

---

## 🚀 Requisitos e Instalación

1. **Python 3.10+** (Recomendado 3.11 - 3.14 en Windows).
2. Clonar el repositorio:
   ```bash
   git clone https://github.com/tu-usuario/BIMO.git
   cd BIMO
   ```
3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
4. Configurar variables de entorno:
   ```bash
   cp .env.example .env
   ```
   Ingresa tu API Key de Groq en `.env` o dentro del panel de ajustes de la aplicación.
5. Iniciar la aplicación:
   ```bash
   python main.py
   ```
   *O en Windows mediante el acceso directo:*
   ```bash
   ejecutar_bimo.bat
   ```

---

## 🔒 Privacidad y Seguridad Clínica

- BIMO implementa separación estricta entre la lógica de procesamiento y los datos confidenciales de los pacientes.
- Los expedientes clínicos, bases de datos locales (`bimo.db`) y bóvedas de claves (`bimo.vault`) están estrictamente ignorados por el control de versiones para cumplir con normativas de privacidad médica.
