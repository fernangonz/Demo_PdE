#Requires -Version 5.1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "[1/3] Creando entorno virtual .venv ..."
    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3 -m venv .venv
    } else {
        python -m venv .venv
    }
}

if (-not (Test-Path $venvPy)) {
    Write-Error "No se pudo crear .venv\Scripts\python.exe. Instala Python 3 y reintenta."
    exit 1
}

Write-Host "[2/3] Instalando/actualizando dependencias en .venv ..."
& $venvPy -m pip install -r requirements.txt

Write-Host "[3/3] Lanzando Streamlit con:"
& $venvPy -c "import sys; print(sys.executable)"
Write-Host ""
& $venvPy -m streamlit run app.py
exit $LASTEXITCODE
