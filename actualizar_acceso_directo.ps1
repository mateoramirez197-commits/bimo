# PowerShell script para actualizar o verificar el acceso directo de BIMO Pro en el Escritorio
param (
    [ValidateSet("dev", "prod", "bat", "pyw")]
    [string]$Modo = "dev"
)

$wsh = New-Object -ComObject WScript.Shell
$desktop = [System.IO.Path]::Combine([System.Environment]::GetFolderPath("Desktop"), "BIMO Pro.lnk")
$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path $desktop)) {
    $desktop = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop", "BIMO Pro.lnk")
}

$icoPath = Join-Path $baseDir "assets\bimo_icon.ico"

if ($Modo -eq "dev") {
    $target = Join-Path $baseDir "ejecutar_bimo_dev.bat"
    $desc = "BIMO Pro - Pruebas en Codigo Fuente Python"
} elseif ($Modo -eq "prod") {
    $target = Join-Path $baseDir "dist\BIMO_Pro\BIMO_Pro.exe"
    $desc = "BIMO Pro - Version Compilada Ejecutable"
} elseif ($Modo -eq "pyw") {
    # Lanza main.py con pythonw directamente: sin ventana CMD intermedia
    $target = (Get-Command pythonw -ErrorAction Stop).Source
    $argumentos = "`"$(Join-Path $baseDir "main.py")`""
    $desc = "BIMO Pro - Copiloto Odontologico Inteligente"
} else {
    $target = Join-Path $baseDir "ejecutar_bimo.bat"
    $desc = "BIMO Pro - Copiloto Odontologico Inteligente"
}

Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "   ACTUALIZADOR DE ACCESO DIRECTO - BIMO PRO ($Modo)" -ForegroundColor Cyan
Write-Host "=========================================================" -ForegroundColor Cyan
Write-Host "Acceso Directo: $desktop"
Write-Host "Nuevo Destino:  $target"
Write-Host "Directorio:     $baseDir"

$sc = $wsh.CreateShortcut($desktop)
$sc.TargetPath = $target
$sc.Arguments = if ($argumentos) { $argumentos } else { "" }
$sc.WorkingDirectory = $baseDir
$sc.Description = $desc
if (Test-Path $icoPath) {
    $sc.IconLocation = "$icoPath,0"
}
$sc.Save()

Write-Host "`n[OK] Acceso directo actualizado exitosamente en el Escritorio." -ForegroundColor Green
