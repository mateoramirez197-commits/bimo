@echo off
setlocal enabledelayedexpansion
title BIMO Pro
cd /d "%~dp0"

:: 1. Si existe main.py (código fuente actualizado), ejecutar directamente con Python
if exist "main.py" (
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
    where python >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        start "" python main.py
        exit /b 0
    )
)

:: 2. Respaldo: distribución binaria compilada BIMO_Pro.exe
if exist "BIMO_Pro.exe" (
    start "" "BIMO_Pro.exe"
    exit /b 0
)
if exist "dist\BIMO_Pro\BIMO_Pro.exe" (
    start "" "dist\BIMO_Pro\BIMO_Pro.exe"
    exit /b 0
)

echo ========================================================
echo [ERROR] No se encontro Python ni el ejecutable de BIMO Pro.
echo ========================================================
pause
exit /b 1
