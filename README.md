# Herramienta de Riesgo por Cambio Climatico en Puertos

Aplicacion web (Streamlit) para calcular, paso a paso, el riesgo por cambio
climatico en un puerto. Migracion progresiva de la metodologia desarrollada en
MATLAB (carpeta `E:\PDE`).

## Estado actual

- **Paso 1 - Seleccion de puerto**: desplegable con los puertos del Excel real y
  mapa de Espana (folium) con cada puerto como punto, resaltando el seleccionado.

## Estructura

```
E:\PDE\DEMO\
├── app.py                 # Aplicacion Streamlit (interfaz, pasos)
├── requirements.txt       # Dependencias
├── README.md
└── core/
    ├── __init__.py
    └── data_loader.py     # Carga de Excel (equivalente a leer_xls.m)
```

## Datos

El cargador busca los Excel en este orden:

1. `E:\PDE\xls`  -> aqui debe estar el `lista_puertos.xlsx` real.
2. `E:\PDE\DEMO\data` -> respaldo dentro del proyecto.

Si no encuentra `lista_puertos.xlsx`, usa una lista por defecto de Puertos del
Estado (con coordenadas) para que el mapa funcione igualmente.

La deteccion de columnas es flexible (con y sin acentos): busca el nombre del
puerto en columnas tipo `puerto`/`nombre`, la latitud en `lat`/`latitud` y la
longitud en `lon`/`longitud`. Tambien admite coordenadas con coma decimal.

## Instalacion y ejecucion (VSCode / terminal)

```bash
cd E:\PDE\DEMO
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Se abrira en el navegador (por defecto http://localhost:8501).
