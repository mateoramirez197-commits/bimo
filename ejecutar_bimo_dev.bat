@echo off
setlocal
title BIMO Pro - CODIGO FUENTE (PRUEBAS)
cd /d "%~dp0"
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist "venv\Scripts\python.exe" set "PY=venv\Scripts\python.exe"
if not defined PY set "PY=python"

echo =========================================================
echo   BIMO PRO - MODO DESARROLLO (EJECUTANDO CODIGO FUENTE)
echo =========================================================
echo Interprete: %PY%
echo Carpeta:    %CD%
echo.

"%PY%" main.py
if errorlevel 1 (
    echo.
    echo [ERROR] La aplicacion se cerro con codigo de error %ERRORLEVEL%.
    pause
)
