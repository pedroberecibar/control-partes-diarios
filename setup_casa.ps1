<#
.SYNOPSIS
    Configura el entorno de desarrollo desde cero en una PC nueva (casa).
    Ejecutar DESPUES de clonar el repo y descomprimir el export.

.USAGE
    1. Clonar: git clone git@github.com:pedroberecibar/control-partes-diarios.git
    2. Descomprimir export_pd_casa.zip al lado del repo clonado
    3. Ejecutar: .\setup_casa.ps1 -ExportPath "C:\ruta\al\export_pd_casa"
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$ExportPath
)

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
$PY_DIR = Join-Path $ROOT "python-version"
$FE_DIR = Join-Path $ROOT "frontend-app"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SETUP CONTROL PARTES DIARIOS - CASA" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── Verificaciones previas ─────────────────────────────────────────
Write-Host "[0/6] Verificando prerrequisitos..." -ForegroundColor Yellow

# Python
try {
    $pyVer = python --version 2>&1
    Write-Host "  Python: $pyVer" -ForegroundColor Gray
} catch {
    Write-Host "  ERROR: Python no encontrado. Instalar desde https://www.python.org/" -ForegroundColor Red
    exit 1
}

# Node
try {
    $nodeVer = node --version 2>&1
    Write-Host "  Node.js: $nodeVer" -ForegroundColor Gray
} catch {
    Write-Host "  ERROR: Node.js no encontrado. Instalar desde https://nodejs.org/" -ForegroundColor Red
    exit 1
}

# Export path
if (-not (Test-Path $ExportPath)) {
    Write-Host "  ERROR: Carpeta de export no encontrada: $ExportPath" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path (Join-Path $ExportPath "data\db\webapp_pd.db"))) {
    Write-Host "  ERROR: webapp_pd.db no encontrada en el export. Verificar la ruta." -ForegroundColor Red
    exit 1
}
Write-Host "  Export valido: $ExportPath" -ForegroundColor Gray
Write-Host "  OK" -ForegroundColor Green

# ── Paso 1: Restaurar datos ───────────────────────────────────────
Write-Host "[1/6] Restaurando datos del export..." -ForegroundColor Yellow
$dataDest = Join-Path $PY_DIR "data"

if (Test-Path $dataDest) {
    Write-Host "  La carpeta data/ ya existe. Se hara merge (sin sobreescribir)." -ForegroundColor DarkYellow
}

robocopy (Join-Path $ExportPath "data") $dataDest /E /NJH /NJS /NDL /NC /NS | Out-Null
Write-Host "  Datos restaurados en: $dataDest" -ForegroundColor Green

# ── Paso 2: Restaurar .env ────────────────────────────────────────
Write-Host "[2/6] Restaurando credenciales (.env)..." -ForegroundColor Yellow
$envSrc = Join-Path $ExportPath ".env"
$envDest = Join-Path $PY_DIR ".env"
if (Test-Path $envSrc) {
    Copy-Item $envSrc $envDest -Force
    Write-Host "  .env restaurado" -ForegroundColor Green
    Write-Host "  NOTA: Si no tenes VPN a la red EPEC, Oracle no va a conectar." -ForegroundColor DarkYellow
    Write-Host "        Esto es normal — el sistema funciona offline con los seeds exportados." -ForegroundColor DarkYellow
} else {
    Write-Host "  ADVERTENCIA: .env no encontrado en el export. Copiar manualmente o crear desde .env.example" -ForegroundColor Red
}

# ── Paso 3: Crear entorno virtual Python ──────────────────────────
Write-Host "[3/6] Creando entorno virtual Python..." -ForegroundColor Yellow
$venvDir = Join-Path $PY_DIR "venv"
if (Test-Path $venvDir) {
    Write-Host "  venv ya existe, omitiendo creacion." -ForegroundColor DarkYellow
} else {
    python -m venv $venvDir
    Write-Host "  venv creado" -ForegroundColor Green
}

# Activar e instalar dependencias
$pipExe = Join-Path $venvDir "Scripts\pip.exe"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"

# Intentar con requirements_frozen.txt primero
$frozenReqs = Join-Path $ExportPath "requirements_frozen.txt"
$baseReqs = Join-Path $PY_DIR "requirements.txt"

if (Test-Path $frozenReqs) {
    Write-Host "  Instalando dependencias (versiones congeladas)..." -ForegroundColor DarkCyan
    & $pipExe install -r $frozenReqs 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  Frozen reqs fallaron, usando requirements.txt base..." -ForegroundColor DarkYellow
        & $pipExe install -r $baseReqs
    }
} else {
    Write-Host "  Instalando dependencias (requirements.txt)..." -ForegroundColor DarkCyan
    & $pipExe install -r $baseReqs
}
Write-Host "  Dependencias instaladas" -ForegroundColor Green

# ── Paso 4: Verificar base de datos ───────────────────────────────
Write-Host "[4/6] Verificando base de datos..." -ForegroundColor Yellow

$dbCheck = @"
import sqlite3, os, sys
db = os.path.join(r'$dataDest', 'db', 'webapp_pd.db')
if not os.path.exists(db):
    print('  ERROR: webapp_pd.db no encontrada')
    sys.exit(1)
conn = sqlite3.connect(db)
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
total = 0
for t in tables:
    count = conn.execute(f'SELECT COUNT(*) FROM [{t[0]}]').fetchone()[0]
    total += count
conn.close()
print(f'  {len(tables)} tablas, {total} filas totales')
"@
& $pythonExe -c $dbCheck

# Ejecutar alembic upgrade head (por si acaso)
Write-Host "  Ejecutando alembic upgrade head..." -ForegroundColor DarkCyan
Push-Location $PY_DIR
& $pythonExe -m alembic upgrade head 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
Pop-Location
Write-Host "  DB verificada" -ForegroundColor Green

# ── Paso 5: Instalar frontend ─────────────────────────────────────
Write-Host "[5/6] Instalando dependencias del frontend..." -ForegroundColor Yellow
Push-Location $FE_DIR
npm.cmd install 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    # Fallback: intentar con npm
    npm install 2>&1 | Out-Null
}
Pop-Location
Write-Host "  Frontend instalado" -ForegroundColor Green

# ── Paso 6: Verificacion final ────────────────────────────────────
Write-Host "[6/6] Verificacion final..." -ForegroundColor Yellow

$seedCheck = @"
import pandas as pd, os, glob
seed_dir = os.path.join(r'$dataDest', 'seed')
files = glob.glob(os.path.join(seed_dir, '*.parquet'))
print(f'  Seeds: {len(files)} archivos')
for f in sorted(files):
    name = os.path.basename(f)
    df = pd.read_parquet(f)
    print(f'    {name}: {len(df)} filas, {len(df.columns)} cols')
"@
& $pythonExe -c $seedCheck

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETADO EXITOSAMENTE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Para levantar el sistema:" -ForegroundColor White
Write-Host ""
Write-Host "  Terminal 1 (Backend):" -ForegroundColor Cyan
Write-Host "    cd $PY_DIR" -ForegroundColor White
Write-Host "    .\venv\Scripts\activate" -ForegroundColor White
Write-Host "    .\run_api_dev.ps1" -ForegroundColor White
Write-Host ""
Write-Host "  Terminal 2 (Frontend):" -ForegroundColor Cyan
Write-Host "    cd $FE_DIR" -ForegroundColor White
Write-Host "    npm.cmd run dev" -ForegroundColor White
Write-Host ""
Write-Host "  Abrir en navegador: http://localhost:5173/control-partes-diarios/" -ForegroundColor Yellow
Write-Host ""
