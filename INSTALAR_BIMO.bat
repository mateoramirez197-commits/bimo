@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title BIMO Pro - Instalador y Configurador Autom†tico
cd /d "%~dp0"
color 0B

echo =====================================================================
echo           BIMO PRO - INSTALADOR AUTOMµTICO DE SISTEMA
echo =====================================================================
echo.
echo Verificando entorno de ejecuci¢n en este equipo...
echo.

:: 1. Detectar si Python est† instalado
set "PYTHON_EXEC="
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    set "PYTHON_EXEC=python"
) else (
    where py >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        set "PYTHON_EXEC=py"
    )
)

if "%PYTHON_EXEC%"=="" (
    echo =====================================================================
    echo [ALERTA] No se detect¢ Python instalado en este equipo.
    echo =====================================================================
    echo Para que BIMO funcione necesitas instalar Python (versi¢n 3.10 o superior).
    echo.
    echo PASOS:
    echo 1. Se abrir† la p†gina oficial de descarga: https://www.python.org/downloads/
    echo 2. Descarga el instalador de Windows (Windows installer 64-bit).
    echo 3. [CRUCIAL]: En la primera pantalla del instalador de Python, marca la casilla:
    echo.
    echo         [X] "Add python.exe to PATH"
    echo.
    echo 4. Haz clic en "Install Now".
    echo 5. Una vez instalado, regresa a esta carpeta y abre nuevamente este archivo.
    echo =====================================================================
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python detectado en el sistema:
"%PYTHON_EXEC%" --version
echo.

:: 2. Actualizar pip
echo ---------------------------------------------------------------------
echo [PASO 1/3] Actualizando gestor de paquetes pip...
echo ---------------------------------------------------------------------
"%PYTHON_EXEC%" -m pip install --upgrade pip --quiet
echo [OK] Pip actualizado.
echo.

:: 3. Instalar librer°as de requirements.txt
echo ---------------------------------------------------------------------
echo [PASO 2/3] Instalando librer°as de IA, Reconocimiento de Voz y UI...
echo (Esto puede tardar unos minutos en la primera instalaci¢n)
echo ---------------------------------------------------------------------
"%PYTHON_EXEC%" -m pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo.
    echo [ADVERTENCIA] Algunas librer°as mostraron avisos, continuando con la inicializaci¢n...
)
echo [OK] Librer°as instaladas con Çxito.
echo.

:: 4. Configurar base de datos, licencia permanente y acceso directo
echo ---------------------------------------------------------------------
echo [PASO 3/3] Configurando base de datos, licencia HWID y acceso directo...
echo ---------------------------------------------------------------------
"%PYTHON_EXEC%" setup_instalador.py
echo.

echo =====================================================================
echo       ≠INSTALACI‡N COMPLETADA EXITOSAMENTE!
echo =====================================================================
echo.
echo Se ha generado el acceso directo 'BIMO Pro' en el Escritorio.
echo Puedes iniciar BIMO en cualquier momento desde ese acceso directo
echo o ejecutando 'ejecutar_bimo.bat'.
echo.
set /p INICIAR="®Deseas iniciar BIMO Pro ahora mismo? (S/N): "
if /i "%INICIAR%"=="S" (
    echo Iniciando BIMO Pro...
    start "" ejecutar_bimo.bat
)
exit /b 0
