@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

echo ==========================================
echo Publicar DEMO (codigo + excels + indicadores)
echo Repositorio: fernangonz/Demo_PdE
echo ==========================================
echo.

git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Esta carpeta no es un repositorio git.
  pause
  exit /b 1
)

echo [1/4] Agregando cambios...
git add .

set "MSG=%~1"
if "%MSG%"=="" set "MSG=update demo"

echo [2/4] Commit: %MSG%
git commit -m "%MSG%" >nul 2>nul
if errorlevel 1 (
  echo No habia cambios para commitear.
)

echo [3/4] Subiendo a GitHub...
git rev-parse --abbrev-ref "@{upstream}" >nul 2>nul
if errorlevel 1 (
  git push -u origin HEAD
) else (
  git push
)
if errorlevel 1 (
  echo [ERROR] No se pudo hacer push. Revisa credenciales o conexion.
  pause
  exit /b 1
)

echo.
echo [4/4] Listo. Streamlit se actualiza en 1-3 minutos.
echo URL: https://demo-pde.streamlit.app
echo.
pause
