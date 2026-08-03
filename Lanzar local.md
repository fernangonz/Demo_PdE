# Lanzar DEMO en local (siempre con .venv)

## Forma recomendada

Doble clic en **`Lanzar local.bat`** (o ejecuta `.\Lanzar local.ps1` en PowerShell).

Eso:
1. Crea `.venv` si no existe
2. Instala `requirements.txt` en ese venv
3. Arranca con: `.venv\Scripts\python.exe -m streamlit run app.py`

## Manual (equivalente)

```powershell
cd E:\PDE\DEMO
.\.venv\Scripts\python.exe -m streamlit run app.py
```

**No uses** solo `streamlit run app.py`: en este equipo `where streamlit` apunta a Miniconda (`...\miniconda3\Scripts\streamlit.exe`), que **no** es el `.venv` y puede faltar `python-docx` / `mammoth`.
