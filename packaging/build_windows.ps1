<#
.SYNOPSIS
  Genera el paquete portable de Círculo para Windows. El usuario final no necesita Python, Node ni descargas.

.DESCRIPTION
  1. Compila la web (dist/) si falta o si se usa -RebuildWeb.
  2. Crea un entorno de compilación aislado (.build-venv).
  3. Instala Chromium dentro del paquete Playwright (PLAYWRIGHT_BROWSERS_PATH=0) para incluirlo en el binario.
  4. Empaqueta con PyInstaller en modo carpeta (arranque rápido).
  5. Firma Circulo.exe con Authenticode cuando hay un certificado configurado por variables de entorno.
  6. Genera release/Circulo-<versión>-win64.zip y release/SHA256SUMS.txt.

  Variables de entorno para firmar (nunca se guardan en el repositorio):
    CIRCULO_SIGN_THUMBPRINT     Huella SHA1 del certificado de firma de código instalado en el almacén de Windows (recomendado).
    CIRCULO_SIGN_PFX            Ruta a un archivo .pfx (alternativa).
    CIRCULO_SIGN_PFX_PASSWORD   Contraseña del .pfx.
    CIRCULO_TIMESTAMP_URL       Servidor RFC 3161. Por defecto http://timestamp.digicert.com

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -RebuildWeb
  powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1 -RequireSignature
#>
param(
    [switch]$RebuildWeb,
    [switch]$RequireSignature
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$buildVenv = Join-Path $root '.build-venv'
$buildPython = Join-Path $buildVenv 'Scripts\python.exe'
$pyiRoot = Join-Path $root 'build\pyinstaller'
$releaseDir = Join-Path $root 'release'

function Invoke-Step {
    param([string]$Description, [scriptblock]$Command)
    Write-Host "› $Description" -ForegroundColor Green
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Falló: $Description (código $LASTEXITCODE)" }
}

function Get-AppVersion {
    $package = Get-Content -LiteralPath (Join-Path $root 'package.json') -Raw | ConvertFrom-Json
    if (-not $package.version) { throw 'package.json no define "version".' }
    return $package.version
}

function Find-SignTool {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $kits = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    if (Test-Path -LiteralPath $kits) {
        $candidate = Get-ChildItem -LiteralPath $kits -Recurse -Filter signtool.exe -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -match '\\x64\\' } |
            Sort-Object FullName -Descending |
            Select-Object -First 1
        if ($candidate) { return $candidate.FullName }
    }
    return $null
}

function Invoke-CodeSigning {
    param([string]$Executable)
    $thumbprint = $env:CIRCULO_SIGN_THUMBPRINT
    $pfx = $env:CIRCULO_SIGN_PFX
    if (-not $thumbprint -and -not $pfx) {
        if ($RequireSignature) { throw 'Se pidió firma obligatoria pero no hay CIRCULO_SIGN_THUMBPRINT ni CIRCULO_SIGN_PFX.' }
        Write-Warning 'Binario SIN firmar: Windows SmartScreen mostrará una advertencia a los usuarios. Configura un certificado para distribuir.'
        return
    }
    $signTool = Find-SignTool
    if (-not $signTool) { throw 'No se encontró signtool.exe. Instala el Windows SDK (componente "Signing Tools").' }
    $timestamp = if ($env:CIRCULO_TIMESTAMP_URL) { $env:CIRCULO_TIMESTAMP_URL } else { 'http://timestamp.digicert.com' }
    $arguments = @('sign', '/fd', 'SHA256', '/tr', $timestamp, '/td', 'SHA256', '/d', 'Círculo')
    if ($thumbprint) {
        $arguments += @('/sha1', $thumbprint)
    } else {
        if (-not (Test-Path -LiteralPath $pfx)) { throw "No existe el certificado PFX indicado en CIRCULO_SIGN_PFX." }
        $arguments += @('/f', $pfx)
        if ($env:CIRCULO_SIGN_PFX_PASSWORD) { $arguments += @('/p', $env:CIRCULO_SIGN_PFX_PASSWORD) }
    }
    Invoke-Step 'Firmando Circulo.exe (Authenticode SHA-256)' { & $signTool @arguments $Executable }
    $signature = Get-AuthenticodeSignature -LiteralPath $Executable
    if ($signature.Status -ne 'Valid') { throw "La firma no es válida: $($signature.Status) $($signature.StatusMessage)" }
    Write-Host "  Firma válida · $($signature.SignerCertificate.Subject)" -ForegroundColor Green
}

$previousBrowsersPath = $env:PLAYWRIGHT_BROWSERS_PATH
Push-Location -LiteralPath $root
try {
    $version = Get-AppVersion
    Write-Host "Círculo $version · empaquetado portable para Windows" -ForegroundColor Green

    if ($RebuildWeb -or -not (Test-Path -LiteralPath (Join-Path $root 'dist\index.html'))) {
        if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Se necesita Node.js 20.19+ para compilar la web.' }
        Invoke-Step 'Instalando dependencias web' { & npm.cmd ci --no-audit --no-fund }
        Invoke-Step 'Compilando la web' { & npm.cmd run build }
    }

    if (-not (Test-Path -LiteralPath $buildPython)) {
        if (Get-Command py -ErrorAction SilentlyContinue) {
            Invoke-Step 'Creando entorno de compilación' { & py -3 -m venv $buildVenv }
        } else {
            Invoke-Step 'Creando entorno de compilación' { & python -m venv $buildVenv }
        }
    }
    Invoke-Step 'Instalando dependencias de ejecución y empaquetado' {
        & $buildPython -m pip install --disable-pip-version-check -r (Join-Path $root 'requirements.txt') -r (Join-Path $PSScriptRoot 'requirements-build.txt')
    }

    # Chromium se instala dentro del paquete playwright para que PyInstaller lo incluya.
    $env:PLAYWRIGHT_BROWSERS_PATH = '0'
    Invoke-Step 'Incluyendo Chromium en el paquete' { & $buildPython -m playwright install chromium }

    Invoke-Step 'Empaquetando con PyInstaller' {
        & $buildPython -m PyInstaller --noconfirm --clean --onedir --console `
            --name Circulo `
            --paths $root `
            --add-data ("{0};dist" -f (Join-Path $root 'dist')) `
            --collect-all playwright `
            --distpath (Join-Path $pyiRoot 'dist') `
            --workpath (Join-Path $pyiRoot 'work') `
            --specpath $pyiRoot `
            (Join-Path $PSScriptRoot 'circulo_launcher.py')
    }

    $appDir = Join-Path $pyiRoot 'dist\Circulo'
    $exe = Join-Path $appDir 'Circulo.exe'
    if (-not (Test-Path -LiteralPath $exe)) { throw 'PyInstaller no generó Circulo.exe.' }
    Invoke-CodeSigning -Executable $exe

    New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
    $zipPath = Join-Path $releaseDir "Circulo-$version-win64.zip"
    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Write-Host '› Comprimiendo paquete portable' -ForegroundColor Green
    Compress-Archive -Path $appDir -DestinationPath $zipPath -CompressionLevel Optimal

    $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $exeHash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash.ToLowerInvariant()
    $sums = @("$hash  $(Split-Path -Leaf $zipPath)", "$exeHash  Circulo/Circulo.exe")
    Set-Content -LiteralPath (Join-Path $releaseDir 'SHA256SUMS.txt') -Value $sums -Encoding ascii

    Write-Host "Listo: $zipPath" -ForegroundColor Green
    Write-Host "SHA-256: $hash"
} finally {
    $env:PLAYWRIGHT_BROWSERS_PATH = $previousBrowsersPath
    Pop-Location
}
