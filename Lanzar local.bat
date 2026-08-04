@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV_PY=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [1/3] Creando entorno virtual .venv ...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
)

if not exist "%VENV_PY%" (
  echo [ERROR] No se pudo crear .venv\Scripts\python.exe
  echo Instala Python 3 y vuelve a ejecutar este script.
  pause
  exit /b 1
)

echo [2/3] Instalando/actualizando dependencias en .venv ...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] pip install fallo.
  pause
  exit /b 1
)

echo [3/3] Lanzando Streamlit con:
"%VENV_PY%" -c "import sys; print(sys.executable)"
echo.
"%VENV_PY%" -m streamlit run app.py --server.enableStaticServing true
set "EC=%ERRORLEVEL%"
if not "%EC%"=="0" pause
exit /b %EC%
