# Script de arranque del API en modo desarrollo.
# Observa cambios tanto en api/ como en src/ (motor analítico) para que --reload
# tome cambios sin necesidad de reiniciar manualmente.
#
# Uso: .\run_api_dev.ps1
Set-Location $PSScriptRoot
uvicorn api.main:app `
    --reload `
    --reload-dir api `
    --reload-dir src `
    --port 8000 `
    --log-level info
