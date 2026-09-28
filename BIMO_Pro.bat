@echo off
setlocal enabledelayedexpansion
title BIMO Pro
cd /d "%~dp0"

:: 1. Si existe la distribución binaria compilada BIMO_Pro.exe, lanzarla directamente sin consola
if exist "dist\BIMO_Pro\BIMO_Pro.exe" (
    start "" "dist\BIMO_Pro\BIMO_Pro.exe"
    exit /b 0
)
if exist "BIMO_Pro.exe" (
    start "" "BIMO_Pro.exe"
    exit /b 0
)

:: 2. Priorizar pythonw.exe (ejecución 100% gráfica sin ventana de consola CMD)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
    exit /b 0
)
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" main.py
    exit /b 0
)

where pythonw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pythonw main.py
    exit /b 0
)

:: 3. Fallback con entorno virtual local
if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" main.py
    exit /b 0
)
if exist "venv\Scripts\python.exe" (
    start "" "venv\Scripts\python.exe" main.py
    exit /b 0
)

:: 4. Fallback con Python general
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" python main.py
    exit /b 0
)

echo ========================================================
echo [ERROR] No se encontro Python ni el ejecutable de BIMO Pro.
echo Por favor asegurese de tener instalado Python o el ejecutable compilado.
echo ========================================================
pause
exit /b 1
