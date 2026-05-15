<#
.SYNOPSIS
    Exporta todos los datos locales del proyecto para llevar a casa.
    Ejecutar DESPUES de detener API y frontend.
.NOTES
    Generado: 2026-05-15
#>

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
$EXPORT_DIR = Join-Path (Split-Path $ROOT -Parent) "export_pd_casa"
$DATA_SRC = Join-Path $ROOT "python-version\data"
$ZIP_PATH = Join-Path (Split-Path $ROOT -Parent) "export_pd_casa.zip"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  EXPORT CONTROL PARTES DIARIOS - CASA" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── Paso 1: Verificar que API/frontend no estan corriendo ──────────
Write-Host "[1/6] Verificando que no hay procesos activos..." -ForegroundColor Yellow
$uvicornProcs = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*uvicorn*" }
$nodeProcs = Get-Process -Name "node" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*vite*" }
if ($uvicornProcs -or $nodeProcs) {
    Write-Host "  ADVERTENCIA: Parece que uvicorn o vite siguen corriendo." -ForegroundColor Red
    Write-Host "  Se recomienda detenerlos antes de exportar (Ctrl+C en sus terminales)." -ForegroundColor Red
    $resp = Read-Host "  Continuar de todas formas? (s/n)"
    if ($resp -ne "s") { exit 1 }
}
Write-Host "  OK" -ForegroundColor Green

# ── Paso 2: WAL Checkpoint ─────────────────────────────────────────
Write-Host "[2/6] Ejecutando WAL checkpoint en SQLite..." -ForegroundColor Yellow
$pyScript = @"
import sqlite3, os
db = os.path.join(r'$DATA_SRC', 'db', 'webapp_pd.db')
conn = sqlite3.connect(db)
result = conn.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
conn.close()
print(f'  Checkpoint: busy={result[0]}, log={result[1]}, checkpointed={result[2]}')
"@
& "$ROOT\python-version\venv\Scripts\python.exe" -c $pyScript
Write-Host "  OK" -ForegroundColor Green

# ── Paso 3: Crear directorio de export ─────────────────────────────
Write-Host "[3/6] Creando directorio de export..." -ForegroundColor Yellow
if (Test-Path $EXPORT_DIR) {
    Write-Host "  Limpiando export anterior..." -ForegroundColor DarkYellow
    Remove-Item $EXPORT_DIR -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $EXPORT_DIR | Out-Null
Write-Host "  Directorio: $EXPORT_DIR" -ForegroundColor Green

# ── Paso 4: Copiar archivos ───────────────────────────────────────
Write-Host "[4/6] Copiando datos..." -ForegroundColor Yellow

# 4a. Carpeta data completa (excluyendo el JSON gigante de georeferenciacion)
Write-Host "  Copiando data/db/ (base de datos SQLite)..." -ForegroundColor DarkCyan
$dbDest = Join-Path $EXPORT_DIR "data\db"
New-Item -ItemType Directory -Force -Path $dbDest | Out-Null
Copy-Item "$DATA_SRC\db\webapp_pd.db" "$dbDest\webapp_pd.db"
$dbSize = [math]::Round((Get-Item "$dbDest\webapp_pd.db").Length / 1MB, 1)
Write-Host "    webapp_pd.db: ${dbSize} MB" -ForegroundColor Gray

Write-Host "  Copiando data/seed/ (seeds Oracle)..." -ForegroundColor DarkCyan
robocopy "$DATA_SRC\seed" "$EXPORT_DIR\data\seed" /E /NJH /NJS /NDL /NC /NS | Out-Null
$seedCount = (Get-ChildItem "$EXPORT_DIR\data\seed" -File).Count
Write-Host "    $seedCount archivos copiados" -ForegroundColor Gray

Write-Host "  Copiando data/master/ (maestros)..." -ForegroundColor DarkCyan
robocopy "$DATA_SRC\master" "$EXPORT_DIR\data\master" /E /NJH /NJS /NDL /NC /NS | Out-Null

Write-Host "  Copiando data/dim/ (dimensiones BI)..." -ForegroundColor DarkCyan
robocopy "$DATA_SRC\dim" "$EXPORT_DIR\data\dim" /E /NJH /NJS /NDL /NC /NS | Out-Null

Write-Host "  Copiando data/gold/ (fact tables)..." -ForegroundColor DarkCyan
robocopy "$DATA_SRC\gold" "$EXPORT_DIR\data\gold" /E /NJH /NJS /NDL /NC /NS | Out-Null

Write-Host "  Copiando data/stage/ (staging)..." -ForegroundColor DarkCyan
robocopy "$DATA_SRC\stage" "$EXPORT_DIR\data\stage" /E /NJH /NJS /NDL /NC /NS | Out-Null

Write-Host "  Copiando data/input/ (excels originales)..." -ForegroundColor DarkCyan
robocopy "$DATA_SRC\input" "$EXPORT_DIR\data\input" /E /NJH /NJS /NDL /NC /NS | Out-Null

Write-Host "  Copiando data/uploads/ (archivos subidos)..." -ForegroundColor DarkCyan
robocopy "$DATA_SRC\uploads" "$EXPORT_DIR\data\uploads" /E /NJH /NJS /NDL /NC /NS | Out-Null

Write-Host "  Copiando data/logs/ (logs pipeline)..." -ForegroundColor DarkCyan
robocopy "$DATA_SRC\logs" "$EXPORT_DIR\data\logs" /E /NJH /NJS /NDL /NC /NS | Out-Null

# Crear carpeta vacia para que el layout este completo
# (ensure_layout() las crea, pero por si acaso)

# 4b. Archivos de configuracion
Write-Host "  Copiando archivos de configuracion..." -ForegroundColor DarkCyan
Copy-Item "$ROOT\python-version\.env" "$EXPORT_DIR\.env"
Copy-Item "$ROOT\python-version\requirements_frozen.txt" "$EXPORT_DIR\requirements_frozen.txt"
Write-Host "  OK" -ForegroundColor Green

# ── Paso 5: Comprimir ─────────────────────────────────────────────
Write-Host "[5/6] Comprimiendo..." -ForegroundColor Yellow
if (Test-Path $ZIP_PATH) { Remove-Item $ZIP_PATH -Force }

# Intentar con 7-Zip primero (mucho mas rapido)
$sevenZip = "C:\Program Files\7-Zip\7z.exe"
if (Test-Path $sevenZip) {
    Write-Host "  Usando 7-Zip (compresion rapida)..." -ForegroundColor DarkCyan
    & $sevenZip a -tzip $ZIP_PATH "$EXPORT_DIR\*" -mx=3 -bso0 -bsp1
} else {
    Write-Host "  Usando Compress-Archive (puede tardar unos minutos)..." -ForegroundColor DarkCyan
    Compress-Archive -Path "$EXPORT_DIR\*" -DestinationPath $ZIP_PATH -Force
}
$zipSize = [math]::Round((Get-Item $ZIP_PATH).Length / 1MB, 1)
Write-Host "  ZIP creado: $ZIP_PATH (${zipSize} MB)" -ForegroundColor Green

# ── Paso 6: Verificacion ──────────────────────────────────────────
Write-Host "[6/6] Verificando integridad..." -ForegroundColor Yellow

$checkScript = @"
import sqlite3, os
db = os.path.join(r'$EXPORT_DIR', 'data', 'db', 'webapp_pd.db')
conn = sqlite3.connect(db)
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
print(f'  Tablas en DB: {len(tables)}')
for t in tables:
    count = conn.execute(f'SELECT COUNT(*) FROM [{t[0]}]').fetchone()[0]
    print(f'    {t[0]}: {count} filas')
conn.close()
"@
& "$ROOT\python-version\venv\Scripts\python.exe" -c $checkScript

$parquetCount = (Get-ChildItem "$EXPORT_DIR\data" -Recurse -Filter "*.parquet").Count
Write-Host "  Archivos .parquet en export: $parquetCount" -ForegroundColor Gray

$totalSize = [math]::Round((Get-ChildItem $EXPORT_DIR -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
Write-Host "  Tamano total del export (sin comprimir): ${totalSize} MB" -ForegroundColor Gray

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  EXPORT COMPLETADO EXITOSAMENTE" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Archivos generados:" -ForegroundColor White
Write-Host "  Carpeta: $EXPORT_DIR" -ForegroundColor White
Write-Host "  ZIP:     $ZIP_PATH (${zipSize} MB)" -ForegroundColor White
Write-Host ""
Write-Host "Proximo paso: copiar el ZIP a un pendrive o subirlo a la nube." -ForegroundColor Yellow
Write-Host ""
