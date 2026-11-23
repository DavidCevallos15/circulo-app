$ErrorActionPreference = 'Stop'
$previousDirectory = Get-Location
try {
    Set-Location -LiteralPath $PSScriptRoot
    Write-Host "Circulo - Preparando tu app local..." -ForegroundColor Green
    $venvPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $venvPython)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            & py -3 -m venv .venv
        } elseif (Get-Command python -ErrorAction SilentlyContinue) {
            & python -m venv .venv
        } else { throw 'Instala Python 3.10 o posterior desde python.org y vuelve a abrir iniciar.cmd.' }
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear el entorno de Python.' }
    }
    $stampFile = Join-Path $PSScriptRoot '.venv\circulo-requirements.sha256'
    $requirementsHash = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot 'requirements.txt') -Algorithm SHA256).Hash
    $installedHash = if (Test-Path -LiteralPath $stampFile) { (Get-Content -LiteralPath $stampFile -Raw).Trim() } else { '' }
    if ($installedHash -ne $requirementsHash) {
        & $venvPython -m pip install -r requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias de Python.' }
        & $venvPython -m playwright install chromium
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo instalar Chromium. Revisa tu conexion y vuelve a intentar.' }
        Set-Content -LiteralPath $stampFile -Value $requirementsHash
    }
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'dist\index.html'))) {
        if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Para compilar la web instala Node.js 20.19+ o 22.12+. El ZIP distribuido incluye la web compilada.' }
        & npm.cmd ci --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'No se pudieron instalar las dependencias web.' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'No se pudo compilar la web.' }
    }
    Write-Host "Abriendo http://127.0.0.1:8765 - Mantén esta ventana abierta. Ctrl+C para salir." -ForegroundColor Green
    & $venvPython -m runner.server
    if ($LASTEXITCODE -ne 0) { throw 'La app se ha cerrado con un error. Revisa el mensaje anterior.' }
} finally { Set-Location -LiteralPath $previousDirectory }
