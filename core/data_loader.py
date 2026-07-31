"""Carga de datos de la herramienta de riesgo por cambio climatico en puertos.

Replica en Python la logica de `leer_xls.m` / `ejecutor.m`: localiza los Excel
y los lee de forma flexible (detectando columnas por nombre, con y sin acentos,
como hace el codigo MATLAB original).

Carpetas de busqueda (ver ``core/fuentes_datos.py``):
  - E:\\PDE\\DEMO\\data_modelos   -> Excel de modelos e indicadores
  - E:\\PDE\\DEMO\\data_secciones -> Excel de secciones generales

Si no se encuentra el Excel de puertos, se usa una lista por defecto
con los principales puertos del sistema portuario espanol (Puertos del Estado),
de modo que el mapa funcione igualmente.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pandas as pd

from dataclasses import dataclass

from core.fuentes_datos import FUENTES, FuenteExcel, candidatos_archivo, fuente, nombre_archivo_display

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIR_DATOS_MODELOS = RAIZ_PROYECTO / "data_modelos"
DIR_DATOS_SECCIONES = RAIZ_PROYECTO / "data_secciones"
DIR_PREGUNTAR_IMPACTOS = RAIZ_PROYECTO / "Preguntar_impactos"
ARCHIVO_PREGUNTAR_IMPACTOS = "Preguntar_si_se_calculan.xlsx"

# Carpetas donde se buscan los Excel (firma de caché y búsquedas auxiliares).
DATA_DIRS: list[Path] = [
    DIR_DATOS_MODELOS,
    DIR_DATOS_SECCIONES,
]


def directorio_fuente(f: FuenteExcel) -> Path:
    """Carpeta asignada a la fuente según ``tipo_carpeta`` en fuentes_datos."""
    if f.tipo_carpeta == "modelos":
        return DIR_DATOS_MODELOS
    return DIR_DATOS_SECCIONES


def directorios_datos_display() -> str:
    return f"{DIR_DATOS_MODELOS} · {DIR_DATOS_SECCIONES}"


@dataclass(frozen=True)
class AuditoriaFuenteExcel:
    fuente_id: str
    seccion: str
    archivo: str
    carpeta: Path
    encontrado: bool
    ruta: Path | None = None


def intentar_resolver_ruta(
    f: FuenteExcel,
    data_dirs: list[Path] | None = None,
) -> Path | None:
    """Localiza el Excel de una fuente o devuelve None si no existe."""
    dirs = data_dirs or [directorio_fuente(f)]
    for candidato in candidatos_archivo(f):
        ruta = localizar_excel(candidato, dirs, parcial=True)
        if ruta is not None:
            return ruta
    return None


def auditar_fuentes_excel() -> list[AuditoriaFuenteExcel]:
    """Comprueba que todos los Excel registrados existen en su carpeta."""
    resultados: list[AuditoriaFuenteExcel] = []
    for f in FUENTES:
        carpeta = directorio_fuente(f)
        ruta = intentar_resolver_ruta(f, [carpeta])
        resultados.append(AuditoriaFuenteExcel(
            fuente_id=f.id,
            seccion=f.seccion,
            archivo=nombre_archivo_display(f),
            carpeta=carpeta,
            encontrado=ruta is not None,
            ruta=ruta,
        ))
    return resultados


def fuentes_excel_faltantes() -> list[AuditoriaFuenteExcel]:
    return [a for a in auditar_fuentes_excel() if not a.encontrado]


def firma_cache_excel(data_dirs: list[Path] | None = None) -> str:
    """Firma de los Excel en disco (mtime + tamaño). Invalida caché al actualizar archivos."""
    dirs = data_dirs or [*DATA_DIRS, DIR_PREGUNTAR_IMPACTOS]
    partes: list[str] = []
    for data_dir in dirs:
        if not data_dir.is_dir():
            continue
        for ext in ("*.xlsx", "*.xls"):
            for ruta in sorted(data_dir.rglob(ext)):
                # Ignorar bloqueos temporales de Excel (~$...).
                if ruta.name.startswith("~$"):
                    continue
                try:
                    stat = ruta.stat()
                    rel = ruta.relative_to(data_dir).as_posix()
                    partes.append(f"{rel}:{stat.st_mtime_ns}:{stat.st_size}")
                except OSError:
                    partes.append(f"{ruta.name}:error")
    return "|".join(partes)


# ---------------------------------------------------------------------------
# Lista por defecto: puertos de interes general del Estado (con coordenadas).
# Solo se usa si NO se encuentra el Excel real, y para completar coordenadas
# que falten en el Excel.
# ---------------------------------------------------------------------------
PUERTOS_DEFECTO: list[dict] = [
    {"puerto": "A Coruna", "autoridad_portuaria": "A Coruna", "lat": 43.366, "lon": -8.396},
    {"puerto": "Aviles", "autoridad_portuaria": "Aviles", "lat": 43.567, "lon": -5.933},
    {"puerto": "Gijon", "autoridad_portuaria": "Gijon", "lat": 43.560, "lon": -5.700},
    {"puerto": "Santander", "autoridad_portuaria": "Santander", "lat": 43.461, "lon": -3.800},
    {"puerto": "Bilbao", "autoridad_portuaria": "Bilbao", "lat": 43.350, "lon": -3.033},
    {"puerto": "Pasaia", "autoridad_portuaria": "Pasaia", "lat": 43.330, "lon": -1.917},
    {"puerto": "Ferrol", "autoridad_portuaria": "Ferrol-San Cibrao", "lat": 43.483, "lon": -8.250},
    {"puerto": "Vigo", "autoridad_portuaria": "Vigo", "lat": 42.233, "lon": -8.717},
    {"puerto": "Marin-Pontevedra", "autoridad_portuaria": "Marin y Ria de Pontevedra", "lat": 42.400, "lon": -8.700},
    {"puerto": "Vilagarcia", "autoridad_portuaria": "Vilagarcia", "lat": 42.600, "lon": -8.767},
    {"puerto": "Huelva", "autoridad_portuaria": "Huelva", "lat": 37.150, "lon": -6.833},
    {"puerto": "Sevilla", "autoridad_portuaria": "Sevilla", "lat": 37.333, "lon": -6.000},
    {"puerto": "Cadiz", "autoridad_portuaria": "Bahia de Cadiz", "lat": 36.533, "lon": -6.283},
    {"puerto": "Algeciras", "autoridad_portuaria": "Bahia de Algeciras", "lat": 36.133, "lon": -5.436},
    {"puerto": "Tarifa", "autoridad_portuaria": "Bahia de Algeciras", "lat": 36.008, "lon": -5.603},
    {"puerto": "Malaga", "autoridad_portuaria": "Malaga", "lat": 36.717, "lon": -4.417},
    {"puerto": "Motril", "autoridad_portuaria": "Motril", "lat": 36.717, "lon": -3.533},
    {"puerto": "Almeria", "autoridad_portuaria": "Almeria", "lat": 36.833, "lon": -2.467},
    {"puerto": "Carboneras", "autoridad_portuaria": "Almeria", "lat": 36.983, "lon": -1.900},
    {"puerto": "Cartagena", "autoridad_portuaria": "Cartagena", "lat": 37.583, "lon": -0.983},
    {"puerto": "Alicante", "autoridad_portuaria": "Alicante", "lat": 38.333, "lon": -0.483},
    {"puerto": "Valencia", "autoridad_portuaria": "Valencia", "lat": 39.450, "lon": -0.317},
    {"puerto": "Sagunto", "autoridad_portuaria": "Valencia", "lat": 39.633, "lon": -0.217},
    {"puerto": "Castellon", "autoridad_portuaria": "Castellon", "lat": 39.967, "lon": -0.017},
    {"puerto": "Tarragona", "autoridad_portuaria": "Tarragona", "lat": 41.100, "lon": 1.217},
    {"puerto": "Barcelona", "autoridad_portuaria": "Barcelona", "lat": 41.350, "lon": 2.167},
    {"puerto": "Palma de Mallorca", "autoridad_portuaria": "Baleares", "lat": 39.567, "lon": 2.633},
    {"puerto": "Alcudia", "autoridad_portuaria": "Baleares", "lat": 39.833, "lon": 3.133},
    {"puerto": "Mao", "autoridad_portuaria": "Baleares", "lat": 39.883, "lon": 4.283},
    {"puerto": "Eivissa", "autoridad_portuaria": "Baleares", "lat": 38.900, "lon": 1.433},
    {"puerto": "Las Palmas", "autoridad_portuaria": "Las Palmas", "lat": 28.150, "lon": -15.417},
    {"puerto": "Santa Cruz de Tenerife", "autoridad_portuaria": "S.C. de Tenerife", "lat": 28.483, "lon": -16.233},
    {"puerto": "Ceuta", "autoridad_portuaria": "Ceuta", "lat": 35.892, "lon": -5.317},
    {"puerto": "Melilla", "autoridad_portuaria": "Melilla", "lat": 35.293, "lon": -2.933},
]


def _normalizar(texto: object) -> str:
    """Minusculas sin acentos ni espacios sobrantes (equivale a `normalizar` en MATLAB)."""
    s = str(texto).strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s)


def _a_numero(valor: object) -> float | None:
    """Convierte a float admitiendo coma decimal espanola y texto con simbolos.

    Ejemplos validos: 43.366 | "43,366" | "-8,396 W" | "  2.167 "
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    s = str(valor).strip()
    if s == "":
        return None

    # Detectar hemisferio por sufijo (W/S -> negativo)
    signo = -1.0 if re.search(r"[wsWS]\s*$", s) else 1.0

    # Quedarnos con digitos, signos, comas y puntos
    s = re.sub(r"[^0-9,\.\-]", "", s)
    if s in ("", "-", ".", ","):
        return None

    # Si hay coma y punto, asumimos que la coma es separador de miles -> quitarla.
    # Si solo hay coma, es separador decimal -> convertir a punto.
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        return float(s) * (abs(signo) if signo > 0 else signo)
    except ValueError:
        return None


def _buscar_columna(columnas: list[str], *patrones: str) -> str | None:
    """Devuelve la primera columna cuyo encabezado coincide (exacto o parcial) con un patron."""
    norm = {col: _normalizar(col) for col in columnas}
    # 1) coincidencia exacta
    for patron in patrones:
        p = _normalizar(patron)
        for col, n in norm.items():
            if n == p:
                return col
    # 2) coincidencia parcial
    for patron in patrones:
        p = _normalizar(patron)
        for col, n in norm.items():
            if p in n:
                return col
    return None


def localizar_excel(
    nombre: str,
    data_dirs: list[Path] = DATA_DIRS,
    parcial: bool = False,
) -> Path | None:
    """Busca `nombre.xlsx`/`.xls` en las carpetas de datos (recursivo, por orden).

    Si `parcial` es True, tambien acepta archivos cuyo nombre *contenga* el
    patron (util cuando el archivo real lleva sufijos, p. ej. `..._all`).
    """
    objetivo = _normalizar(nombre)
    for data_dir in data_dirs:
        if not data_dir.exists():
            continue
        # Coincidencia directa primero
        for ext in (".xlsx", ".xls"):
            directo = data_dir / f"{nombre}{ext}"
            if directo.exists():
                return directo
        # Busqueda recursiva (exacta) por si esta en una subcarpeta
        for ext in ("*.xlsx", "*.xls"):
            for ruta in data_dir.rglob(ext):
                if _normalizar(ruta.stem) == objetivo:
                    return ruta
    # Segunda pasada: coincidencia parcial (solo si se pide)
    if parcial:
        for data_dir in data_dirs:
            if not data_dir.exists():
                continue
            for ext in ("*.xlsx", "*.xls"):
                for ruta in data_dir.rglob(ext):
                    if objetivo in _normalizar(ruta.stem):
                        return ruta
    return None


def _resolver_ruta(f: FuenteExcel, data_dirs: list[Path] | None = None) -> Path:
    """Localiza el Excel de una fuente registrada en ``core/fuentes_datos.py``."""
    dirs = data_dirs or [directorio_fuente(f)]
    ruta = intentar_resolver_ruta(f, dirs)
    if ruta is not None:
        return ruta
    carpeta = dirs[0]
    raise FileNotFoundError(
        f"No se encontro '{nombre_archivo_display(f)}' en: {carpeta}"
    )


def _elegir_hoja(hojas: list[str], preferida: str | None = None) -> str:
    """Elige la hoja más afín a ``preferida`` (admite nombres truncados en Excel)."""
    if not hojas:
        raise ValueError("El archivo no tiene hojas.")
    if preferida:
        pref = _normalizar(preferida).replace("_", " ")

        def puntaje(nombre_hoja: str) -> int:
            n = _normalizar(nombre_hoja).replace("_", " ")
            score = 0
            if pref in n or n in pref:
                score += 100
            for tok in pref.split():
                if len(tok) > 2 and tok in n:
                    score += 1
            return score

        mejor = max(hojas, key=puntaje)
        if puntaje(mejor) > 0:
            return mejor
    for h in hojas:
        nh = _normalizar(h)
        if "relacion" in nh and "impacto" in nh:
            return h
    return hojas[0]


def _hoja_excluida(nombre_hoja: str, patrones: tuple[str, ...]) -> bool:
    """True si la hoja coincide con algún patrón de exclusión (normalizado)."""
    n = _normalizar(nombre_hoja)
    for patron in patrones:
        p = _normalizar(patron)
        if n == p or p in n:
            return True
    if "listrelacion" in n and "impactos" in n and "indicador" in n:
        return True
    return False


def _resolver_coordenadas_puertos(columnas: list[str]) -> tuple[str | None, str | None]:
    """Resuelve columnas lat/lon; en Lista_de_puertos X=latitud e y=longitud."""
    norm = {col: _normalizar(col) for col in columnas}
    cols_x = [col for col, n in norm.items() if n == "x"]
    cols_y = [col for col, n in norm.items() if n == "y"]
    if len(cols_x) == 1 and len(cols_y) == 1:
        return cols_x[0], cols_y[0]

    col_lat = _buscar_columna(columnas, "lat", "latitud", "latitude", "coord y")
    col_lon = _buscar_columna(columnas, "lon", "lng", "longitud", "longitude", "coord x")
    return col_lat, col_lon


def cargar_lista_puertos(data_dirs: list[Path] = DATA_DIRS) -> tuple[pd.DataFrame, dict]:
    """Carga la lista de puertos desde el Excel real (o lista por defecto).

    Returns
    -------
    (df, info)
        df: DataFrame con columnas normalizadas ['puerto', 'lat', 'lon', ...].
        info: dict con metadatos para mostrar en la interfaz:
              {'origen': 'excel'|'defecto', 'ruta': str|None,
               'columnas_originales': list, 'mapeo': dict}
    """
    meta = fuente("puertos")
    try:
        ruta = _resolver_ruta(meta, data_dirs)
    except FileNotFoundError:
        df = pd.DataFrame(PUERTOS_DEFECTO)
        info = {
            "origen": "defecto",
            "ruta": None,
            "columnas_originales": [],
            "mapeo": {},
            "fuente": meta.id,
        }
        return df, info

    bruto = pd.read_excel(ruta)
    bruto.columns = [str(c).strip() for c in bruto.columns]
    columnas = list(bruto.columns)

    col_nombre = _buscar_columna(
        columnas,
        "puertos del estado",
        "puerto del estado",
        "puerto",
        "nombre",
        "nombre puerto",
        "port",
        "denominacion",
    )
    col_lat, col_lon = _resolver_coordenadas_puertos(columnas)
    col_ap = _buscar_columna(columnas, "autoridad portuaria", "autoridad", "ap")
    col_coord = _buscar_columna(columnas, "coordenadas", "coordenada", "latlon", "lat/lon")
    # Columnas ya formateadas en grados sexagesimales (p. ej. `43° 21' 00" N`).
    col_lat_grados = _buscar_columna(
        columnas,
        "latitud grados",
        "lat grados",
        "latitud (grados)",
        "lat (grados)",
        "grados latitud",
    )
    col_lon_grados = _buscar_columna(
        columnas,
        "longitud grados",
        "lon grados",
        "longitud (grados)",
        "lon (grados)",
        "grados longitud",
    )

    if col_nombre is None:
        col_nombre = columnas[0]

    salida = pd.DataFrame()
    salida["puerto"] = bruto[col_nombre].astype(str).str.strip()

    if col_lat is not None:
        salida["lat"] = bruto[col_lat].map(_a_numero)
    if col_lon is not None:
        salida["lon"] = bruto[col_lon].map(_a_numero)

    # Caso: una unica columna "coordenadas" con "lat, lon"
    if (col_lat is None or col_lon is None) and col_coord is not None:
        partes = bruto[col_coord].astype(str).str.split(r"[;,/]", n=1, expand=True)
        if partes.shape[1] == 2:
            if "lat" not in salida:
                salida["lat"] = partes[0].map(_a_numero)
            if "lon" not in salida:
                salida["lon"] = partes[1].map(_a_numero)

    if "lat" not in salida:
        salida["lat"] = pd.NA
    if "lon" not in salida:
        salida["lon"] = pd.NA

    if col_ap is not None:
        salida["autoridad_portuaria"] = bruto[col_ap].astype(str).str.strip()

    if col_lat_grados is not None:
        salida["lat_grados"] = bruto[col_lat_grados].astype(str).str.strip()
    if col_lon_grados is not None:
        salida["lon_grados"] = bruto[col_lon_grados].astype(str).str.strip()

    # Conservar el resto de columnas originales por si son utiles mas adelante.
    usadas = {col_nombre, col_lat, col_lon, col_ap, col_coord, col_lat_grados, col_lon_grados}
    for col in columnas:
        if col not in usadas and col not in salida.columns:
            salida[col] = bruto[col].values

    salida = _completar_coordenadas(salida)

    info = {
        "origen": "excel",
        "ruta": str(ruta),
        "fuente": meta.id,
        "columnas_originales": columnas,
        "mapeo": {
            "puerto": col_nombre,
            "lat": col_lat or col_coord,
            "lon": col_lon or col_coord,
            "autoridad_portuaria": col_ap,
            "lat_grados": col_lat_grados,
            "lon_grados": col_lon_grados,
        },
    }
    return salida, info


# ---------------------------------------------------------------------------
# Inventario de matriz de impactos: lista unica de modos de fallo / parada.
# Equivalente a `lista_modos_fallo.m` (MATLAB).
# ---------------------------------------------------------------------------

# Encabezados que identifican la columna de modos (normalizados, sin acentos).
_PATRONES_MODO = ("modos de fallo", "modos de parada", "modo de fallo", "modo de parada")

# Valores que se descartan al leer un modo.
_VACIOS = {"", "nan", "none", "<missing>", "na", "n/a"}

# Textos que NO son impactos (descripciones coladas). Se comparan normalizados
# (minusculas, sin acentos). Añade aquí los que quieras excluir.
_EXCLUIR_MODOS = {
    "considerado como un porcentaje del fallo de la zona de atarque y amarre",
}

# ---------------------------------------------------------------------------
# Correcciones ortograficas de los textos de impacto.
# Se aplican sobre el texto en MINUSCULAS (antes de capitalizar).
# Cada entrada es (patron_regex, reemplazo). Anade aqui nuevas correcciones.
# ---------------------------------------------------------------------------
_CORRECCIONES: list[tuple[str, str]] = [
    # "...asociado a los el de la obra de..." -> "...asociado a los de la obra de..."
    (r"\blos el de\b", "los de"),
    # Errores tipograficos frecuentes (dobles letras, etc.)
    (r"\basociaado\b", "asociado"),
]


def _corregir_texto(texto: str) -> str:
    """Aplica las correcciones ortograficas definidas en `_CORRECCIONES`."""
    for patron, reemplazo in _CORRECCIONES:
        texto = re.sub(patron, reemplazo, texto)
    return re.sub(r"\s+", " ", texto).strip()


def _capitalizar(texto: str) -> str:
    """Pone en mayuscula solo la primera letra del impacto (resto sin cambios)."""
    return texto[:1].upper() + texto[1:] if texto else texto


def _localizar_columna_modo(
    raw: pd.DataFrame, max_filas: int = 20
) -> tuple[int | None, int | None]:
    """Busca en las primeras filas la columna de 'modos de fallo / parada'.

    Devuelve (indice_columna, fila_encabezado) o (None, None) si no se encuentra.
    """
    n_filas = min(max_filas, len(raw))
    for r in range(n_filas):
        for c, celda in enumerate(raw.iloc[r]):
            texto = _normalizar(celda)
            if any(p in texto for p in _PATRONES_MODO):
                return c, r
    return None, None


def _texto_modo(valor: object) -> str | None:
    """Limpia, corrige y capitaliza el texto de un impacto.

    Pasos: minusculas + espacios normalizados -> correcciones ortograficas
    (`_CORRECCIONES`) -> primera letra en mayuscula. Conserva los acentos y
    descarta vacios/nan.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = re.sub(r"\s+", " ", str(valor).strip().lower())
    if texto in _VACIOS:
        return None
    texto = _corregir_texto(texto)
    if _normalizar(texto) in _EXCLUIR_MODOS:
        return None
    return _capitalizar(texto)


def lista_modos_fallo(
    data_dirs: list[Path] = DATA_DIRS,
    ordenar: bool = True,
) -> tuple[list[str], dict]:
    """Lista unica de modos de fallo / modos de parada del inventario de impactos.

    Replica `lista_modos_fallo.m`: recorre todas las hojas del Excel, localiza en
    cada una la columna 'Modos de fallo / Modos de parada' y recopila sus valores.

    Parameters
    ----------
    nombre : nombre (sin extension) del Excel del inventario de impactos.
    ordenar : si True (por defecto) devuelve la lista unica ordenada alfabeticamente,
        igual que el resultado efectivo del MATLAB original; si False conserva el
        orden de aparicion.

    Returns
    -------
    (modos, info)
        modos: lista de modos unicos (en minuscula).
        info: metadatos {'ruta', 'hojas_leidas', 'hojas_sin_columna', 'total'}.
    """
    ruta = _resolver_ruta(fuente("impactos"), data_dirs)

    hojas = pd.read_excel(ruta, sheet_name=None, header=None)

    modos: list[str] = []
    hojas_leidas: list[str] = []
    hojas_sin_columna: list[str] = []

    for nombre_hoja, raw in hojas.items():
        if raw is None or raw.empty:
            continue
        col_modo, fila_header = _localizar_columna_modo(raw)
        if col_modo is None:
            hojas_sin_columna.append(nombre_hoja)
            continue
        hojas_leidas.append(nombre_hoja)
        for valor in raw.iloc[fila_header + 1:, col_modo]:
            texto = _texto_modo(valor)
            if texto is not None:
                modos.append(texto)

    # Eliminar duplicados conservando el orden de aparicion.
    modos_unicos = list(dict.fromkeys(modos))
    if ordenar:
        modos_unicos = sorted(modos_unicos)

    info = {
        "ruta": str(ruta),
        "hojas_leidas": hojas_leidas,
        "hojas_sin_columna": hojas_sin_columna,
        "total": len(modos_unicos),
    }
    return modos_unicos, info


# ---------------------------------------------------------------------------
# Tabla de relacion Impactos - Indicadores (a partir de las hojas LIST ASSETS).
# Recorre las hojas con (B1)...(B13-B20), asocia por correspondencia (las celdas
# combinadas se rellenan hacia abajo) el Estado limite, el Modo de fallo/parada y
# el Activo fisico u Operacional de cada fila.
# ---------------------------------------------------------------------------

# Orden de los tipos de impacto (estado limite): ELO, ELS, ELU; el resto al final.
_ORDEN_ESTADO = {"elo": 0, "els": 1, "elu": 2}


def _clave_dedup(*partes: object) -> str:
    """Clave normalizada para deduplicar (minusculas, sin acentos, corregida)."""
    trozos = []
    for p in partes:
        if p is None or (isinstance(p, float) and pd.isna(p)):
            trozos.append("")
        else:
            trozos.append(_corregir_texto(_normalizar(p)))
    return "|".join(trozos)


def _valor_limpio(valor: object) -> str | None:
    """Devuelve el texto limpio de una celda o None si es vacia/ruido."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    s = re.sub(r"\s+", " ", str(valor).strip())
    if s == "" or s.lower() in ("nan", "none", "false", "true", "<missing>", "-"):
        return None
    return s


def _inferir_variable_climatica(modo: str, mapa: dict[str, str] | None = None) -> str | None:
    """Infiere la variable climatica a partir del modo de fallo / parada.

    Usa primero el mapa del Excel `ImpactosvsIndicadores` (si existe) y, si no hay
    coincidencia, aplica reglas por palabras clave (como en la tabla de referencia).
    """
    if not modo:
        return None
    clave = _normalizar(modo)
    if mapa and clave in mapa:
        return mapa[clave]

    t = clave

    # Corriente
    if "corriente" in t:
        return "Corriente"
    # Visibilidad
    if "visibilidad" in t:
        return "Visibilidad"
    # Precipitación
    if "precipitacion" in t:
        return "Precipitación"
    # Viento (antes que oleaje en textos ambiguos)
    if "viento" in t:
        return "Viento"
    # Inundación
    if "inundacion" in t:
        return "Inundación costera"
    # Temperatura
    if "temperatura" in t or "costes energeticos" in t or "energeticos" in t:
        return "Temperatura"
    # Oleaje / agitación / rebase
    if any(p in t for p in ("oleaje", "agitacion", "rebase")):
        return "Oleaje"
    # Carga hidráulica: Oleaje vs Nivel del mar según el detalle
    if "carga hidraulica" in t:
        if any(p in t for p in ("amarre", "hundimiento", "berma")):
            return "Nivel del mar"
        if any(p in t for p in ("espaldon", "banqueta", "tronco", "morro", "vuelco", "abrigo")):
            return "Oleaje"
        return "Nivel del mar"
    # Nivel del mar / calado / francobordo
    if any(p in t for p in (
        "calado", "estanqueidad", "balizamiento", "senalizacion",
        "profundidad operativa", "nivel del mar", "francobordo",
    )):
        return "Nivel del mar"

    return None


def cargar_mapa_modo_variable(
    nombre: str = "ImpactosvsIndicadores",
    data_dirs: list[Path] = DATA_DIRS,
) -> dict[str, str]:
    """Carga mapa modo de fallo -> variable climatica desde Excel (si existe).

    Busca columnas tipo 'Modo de fallo' / 'Motivo de parada' y 'Variable'.
    Devuelve dict {modo_normalizado: variable}.
    """
    ruta = localizar_excel(nombre, data_dirs, parcial=True)
    if ruta is None:
        return {}

    try:
        raw = pd.read_excel(ruta, header=None)
    except Exception:
        return {}

    col_modo, col_var, fila_header = None, None, None
    for r in range(min(20, len(raw))):
        for c, val in enumerate(raw.iloc[r]):
            n = _normalizar(val)
            if not n:
                continue
            if col_modo is None and (
                "modo de fallo" in n or "modos de fallo" in n
                or "motivo de parada" in n or "modos de parada" in n
            ):
                col_modo = c
                fila_header = r
            if col_var is None and n == "variable":
                col_var = c
        if col_modo is not None and col_var is not None:
            break

    if col_modo is None or col_var is None:
        # Intentar con cabecera en fila 0 y nombres de columna estándar
        df = pd.read_excel(ruta)
        df.columns = [str(c).strip() for c in df.columns]
        col_m = _buscar_columna(list(df.columns), "modo de fallo", "motivo de parada", "modos de fallo")
        col_v = _buscar_columna(list(df.columns), "variable")
        if col_m and col_v:
            mapa: dict[str, str] = {}
            for _, fila in df.iterrows():
                modo = _valor_limpio(fila[col_m])
                var = _valor_limpio(fila[col_v])
                if modo and var:
                    mapa[_normalizar(modo)] = var
            return mapa
        return {}

    mapa = {}
    for valor_modo, valor_var in zip(
        raw.iloc[fila_header + 1:, col_modo],
        raw.iloc[fila_header + 1:, col_var],
    ):
        modo = _valor_limpio(valor_modo)
        var = _valor_limpio(valor_var)
        if modo and var:
            mapa[_normalizar(modo)] = var
    return mapa


COLUMNAS_RELACION_IMPACTOS: tuple[str, ...] = (
    "Nº",
    "Tipo de impacto",
    "Modos de fallo / Modos de parada",
    "Variable",
    "Activo físico u Operacional",
    "Tipo activo/servicio",
)

HOJA_LISTA_IMPACTOS_INDICADOR = "ListRelacion impactos-indicador"


def _renombrar_columnas_relacion_impactos(df: pd.DataFrame) -> pd.DataFrame:
    renombres: dict[str, str] = {}
    for i, col in enumerate(df.columns):
        n = _normalizar(col)
        if i == 0 and n in ("no", "n", "num", "nº", "n°"):
            renombres[col] = "Nº"
        elif "tipo de impacto" in n:
            renombres[col] = "Tipo de impacto"
        elif "modos de fallo" in n or "modos de parada" in n:
            renombres[col] = "Modos de fallo / Modos de parada"
        elif n == "variable":
            renombres[col] = "Variable"
        elif "activo" in n and "operacional" in n:
            renombres[col] = "Activo físico u Operacional"
        elif "tipo activo" in n or "tipo servicio" in n:
            renombres[col] = "Tipo activo/servicio"
    return df.rename(columns=renombres)


def _limpiar_tabla_relacion_impactos(df: pd.DataFrame, *, origen: str) -> pd.DataFrame:
    df = df.dropna(how="all").reset_index(drop=True)
    faltan = [c for c in COLUMNAS_RELACION_IMPACTOS if c not in df.columns]
    if faltan:
        raise ValueError(
            f"Faltan columnas en {origen}: {faltan}. "
            f"Columnas detectadas: {list(df.columns)}"
        )

    df = df[list(COLUMNAS_RELACION_IMPACTOS)].copy()
    df["Nº"] = pd.to_numeric(df["Nº"], errors="coerce")
    df = df.dropna(subset=["Nº"])
    df["Nº"] = df["Nº"].astype(int)

    for col in COLUMNAS_RELACION_IMPACTOS[1:]:
        df[col] = df[col].map(
            lambda x: None if pd.isna(x) or str(x).strip() in ("", "nan") else str(x).strip()
        )
    return df.reset_index(drop=True)


def relacion_impactos_desde_lista_master(lista: pd.DataFrame) -> pd.DataFrame:
    """Matriz IM (paso 4) a partir de la hoja maestra ListRelacion impactos-indicador."""
    if lista is None or lista.empty:
        return pd.DataFrame(columns=list(COLUMNAS_RELACION_IMPACTOS))
    df = _renombrar_columnas_relacion_impactos(lista.copy())
    return _limpiar_tabla_relacion_impactos(
        df,
        origen=HOJA_LISTA_IMPACTOS_INDICADOR,
    )


def _hoja_lista_impactos_indicador(hojas: dict[str, pd.DataFrame]) -> tuple[str, pd.DataFrame] | None:
    for nombre_hoja, raw in hojas.items():
        if _normalizar(nombre_hoja).startswith("listrelacion impactos"):
            return nombre_hoja, raw
    return None


def cargar_relacion_impactos_indicadores(
    data_dirs: list[Path] = DATA_DIRS,
) -> tuple[pd.DataFrame, dict]:
    """Carga la matriz impacto–activo desde ListRelacion impactos-indicador (Excel umbrales)."""
    meta_umb = fuente("umbrales")
    ruta = _resolver_ruta(meta_umb, data_dirs)

    hojas_raw = pd.read_excel(ruta, sheet_name=None, header=None)
    if not hojas_raw:
        raise ValueError(f"El archivo {ruta} no tiene hojas.")

    encontrada = _hoja_lista_impactos_indicador(hojas_raw)
    if encontrada is None:
        raise ValueError(
            f"No se encontró la hoja «{HOJA_LISTA_IMPACTOS_INDICADOR}» en {ruta.name}."
        )
    nombre_hoja, raw = encontrada
    lista = _leer_hoja_umbrales(raw)
    if lista.empty:
        raise ValueError(
            f"La hoja «{nombre_hoja}» de {ruta.name} no tiene filas con Nº válido."
        )

    df = relacion_impactos_desde_lista_master(lista)
    info = {
        "ruta": str(ruta),
        "hoja": nombre_hoja,
        "total": len(df),
        "origen": "lista_master_umbrales",
        "fuente": fuente("relacion_ivc").id,
    }
    return df, info


def tabla_impactos_indicadores(
    data_dirs: list[Path] = DATA_DIRS,
) -> tuple[pd.DataFrame, dict]:
    """Carga la relación impactos–variables climáticas desde su Excel dedicado."""
    return cargar_relacion_impactos_indicadores(data_dirs)


def _tabla_relacion_desde_inventario(
    nombre: str = "Inventario_matriz_impactos_all",
    data_dirs: list[Path] = DATA_DIRS,
) -> tuple[pd.DataFrame, dict]:
    """Construye la tabla desde Inventario_matriz_impactos_all (legado, no usado en UI)."""
    ruta = localizar_excel(nombre, data_dirs, parcial=True)
    if ruta is None:
        raise FileNotFoundError(
            f"No se encontro '{nombre}.xlsx' en: " + ", ".join(str(d) for d in data_dirs)
        )

    hojas = pd.read_excel(ruta, sheet_name=None, header=None)
    mapa_variable = cargar_mapa_modo_variable()

    registros: list[dict] = []
    hojas_procesadas: list[str] = []

    for nombre_hoja, raw in hojas.items():
        # Solo las hojas de activos: las que llevan "(B1)", "(B2)", ... "(B13-B20)".
        if not re.search(r"\(\s*b\d", nombre_hoja, re.IGNORECASE):
            continue
        if raw is None or raw.empty:
            continue

        # Localizar la fila de cabecera (la que tiene "estado limite" y "modos de fallo").
        fila_header = None
        for r in range(min(25, len(raw))):
            fila = [_normalizar(x) for x in raw.iloc[r]]
            tiene_estado = any("estado limite" in c for c in fila)
            tiene_modo = any(("modos de fallo" in c) or ("modos de parada" in c) for c in fila)
            if tiene_estado and tiene_modo:
                fila_header = r
                break
        if fila_header is None:
            continue

        def _buscar(fila_idx: int, *patrones: str) -> int | None:
            if fila_idx >= len(raw):
                return None
            for c, val in enumerate(raw.iloc[fila_idx]):
                n = _normalizar(val)
                if n and any(p in n for p in patrones):
                    return c
            return None

        col_estado = _buscar(fila_header, "estado limite")
        col_modo = _buscar(fila_header, "modos de fallo", "modos de parada")

        # "Activo fisico" / "Operacional" pueden estar en la cabecera o en la fila siguiente.
        # (Comparar con None: un indice de columna puede ser 0, que es "falsy".)
        col_activo = _buscar(fila_header, "activo fisico")
        if col_activo is None:
            col_activo = _buscar(fila_header + 1, "activo fisico")
        col_oper = _buscar(fila_header, "operacional")
        if col_oper is None:
            col_oper = _buscar(fila_header + 1, "operacional")

        # Si la fila siguiente es subcabecera (activo fisico / operacional), los datos empiezan despues.
        sub = [_normalizar(x) for x in raw.iloc[fila_header + 1]] if fila_header + 1 < len(raw) else []
        es_subcabecera = any(("activo fisico" in c) or ("operacional" in c) for c in sub)
        inicio = fila_header + 2 if es_subcabecera else fila_header + 1

        datos = raw.iloc[inicio:].reset_index(drop=True)
        n = len(datos)
        if n == 0:
            continue

        def _col(idx: int | None) -> list:
            return datos[idx].tolist() if idx is not None and idx < datos.shape[1] else [None] * n

        estados = _col(col_estado)
        modos = _col(col_modo)
        activos_fis = _col(col_activo)
        opers = _col(col_oper)

        # Coalescer activo fisico / operacional por fila (antes de rellenar hacia abajo).
        valores_activo, tipos_activo = [], []
        for af, op in zip(activos_fis, opers):
            af_l, op_l = _valor_limpio(af), _valor_limpio(op)
            if af_l is not None:
                valores_activo.append(af_l)
                tipos_activo.append("Activo físico")
            elif op_l is not None:
                valores_activo.append(op_l)
                tipos_activo.append("Operacional (servicios)")
            else:
                valores_activo.append(None)
                tipos_activo.append(None)

        # Rellenar hacia abajo (celdas combinadas) estado, activo y modo de fallo.
        # El modo tambien puede venir combinado (valor solo en la fila superior),
        # por eso se rellena igual que el estado: el primer registro de cada bloque
        # trae su propio valor, asi que el ffill estandar es correcto.
        s_estado = pd.Series([_valor_limpio(v) for v in estados]).ffill()
        s_activo = pd.Series(valores_activo).ffill()
        s_tipo = pd.Series(tipos_activo).ffill()
        s_modo = pd.Series([_valor_limpio(v) for v in modos]).ffill()

        for i in range(n):
            modo = s_modo.iloc[i]
            estado = s_estado.iloc[i]
            if modo is None or estado is None:
                continue
            if _normalizar(modo) in _EXCLUIR_MODOS:
                continue
            variable = _inferir_variable_climatica(modo, mapa_variable)
            registros.append({
                "Tipo de impacto": estado,
                "Modos de fallo / Modos de parada": modo,
                "Variable": variable or "",
                "Activo físico u Operacional": s_activo.iloc[i],
                "Tipo activo/servicio": s_tipo.iloc[i],
            })

        hojas_procesadas.append(nombre_hoja)

    df = pd.DataFrame(
        registros,
        columns=[
            "Tipo de impacto",
            "Modos de fallo / Modos de parada",
            "Variable",
            "Activo físico u Operacional",
            "Tipo activo/servicio",
        ],
    )

    if not df.empty:
        # Deduplicado inteligente: clave normalizada (tipo + modo + activo),
        # conservando la primera aparicion pero mostrando el texto original.
        claves = df.apply(
            lambda f: _clave_dedup(
                f["Tipo de impacto"],
                f["Modos de fallo / Modos de parada"],
                f["Activo físico u Operacional"],
            ),
            axis=1,
        )
        df = df[~claves.duplicated(keep="first")].copy()

        # Orden por defecto: Tipo de impacto en orden ELO, ELS, ELU (resto al final).
        df["_ord"] = df["Tipo de impacto"].map(
            lambda t: _ORDEN_ESTADO.get(_normalizar(t), 99)
        )
        df = df.sort_values("_ord", kind="stable").drop(columns="_ord").reset_index(drop=True)
        df.insert(0, "Nº", range(1, len(df) + 1))

    info = {
        "ruta": str(ruta),
        "hojas_procesadas": hojas_procesadas,
        "total": len(df),
    }
    return df, info


# ---------------------------------------------------------------------------
# Datos de clima: escenarios y horizontes (anios) por variable climatica.
# Equivalente a `leer_xls.m` + `leer_escenarios.m` (MATLAB), pero detectando
# automaticamente la fila de cabeceras y las columnas de clima (en vez de fijar
# las columnas 5-19 como el MATLAB original).
# ---------------------------------------------------------------------------

# Año entre parentesis, p. ej. "... (2050)".
_RE_ANIO_PAREN = re.compile(r"\((\d+)\)")
# Escenario SSP, p. ej. "SSP1-2.6", "SSP5-8.5" (admite espacios).
_RE_SSP = re.compile(r"SSP\s*\d\s*-\s*\d\.\d", re.IGNORECASE)


# Correcciones ortograficas de meses (clave en minusculas -> valor correcto).
_CORRECCIONES_MES = {"semptiembre": "septiembre"}


def _corregir_mes(valor: object) -> object:
    """Corrige errores ortograficos del mes conservando la mayuscula inicial."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return valor
    s = str(valor).strip()
    correccion = _CORRECCIONES_MES.get(s.lower())
    if correccion is None:
        return valor
    return correccion.capitalize() if s[:1].isupper() else correccion


def _parse_cabecera_clima(valor: object) -> tuple[int | None, str | None]:
    """Extrae (anio, escenario) de una cabecera de Datos_clima.

    - anio: numero entre parentesis, p. ej. "(2050)" -> 2050.
    - escenario: "Histórico" o el codigo SSP (p. ej. "SSP1-2.6"); None si no aplica.
    """
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None, None
    texto = str(valor)

    m_anio = _RE_ANIO_PAREN.search(texto)
    anio = int(m_anio.group(1)) if m_anio else None

    if re.search(r"hist", texto, re.IGNORECASE):
        escenario = "Histórico"
    else:
        m_ssp = _RE_SSP.search(texto)
        escenario = re.sub(r"\s+", "", m_ssp.group(0)).upper() if m_ssp else None

    return anio, escenario


def _detectar_clima(raw: pd.DataFrame, max_filas: int = 20) -> tuple[int | None, list[dict]]:
    """Localiza la fila de cabeceras y las columnas de clima de una hoja.

    Devuelve (fila_header, columnas) donde `columnas` es una lista de dicts
    {'col', 'anio', 'escenario', 'texto'}. La fila de cabeceras es aquella con
    mas celdas que parsean a un escenario/anio.
    """
    mejor_fila, mejor_cols = None, []
    for r in range(min(max_filas, len(raw))):
        cols: list[dict] = []
        for c, celda in enumerate(raw.iloc[r]):
            anio, escenario = _parse_cabecera_clima(celda)
            if anio is not None or escenario is not None:
                cols.append({"col": c, "anio": anio, "escenario": escenario, "texto": str(celda)})
        if len(cols) > len(mejor_cols):
            mejor_fila, mejor_cols = r, cols
    return mejor_fila, mejor_cols


def cargar_datos_clima(
    data_dirs: list[Path] = DATA_DIRS,
) -> dict:
    """Carga el Excel de indicadores climáticos (una hoja por variable)."""
    meta = fuente("clima")
    ruta = _resolver_ruta(meta, data_dirs)

    hojas = pd.read_excel(ruta, sheet_name=None, header=None)

    por_variable: dict[str, dict] = {}
    escenarios_glob: set[str] = set()
    anios_glob: set[int] = set()

    for nombre_hoja, raw in hojas.items():
        if raw is None or raw.empty:
            continue

        fila_header, cols_clima = _detectar_clima(raw)
        if fila_header is None:
            # Sin columnas de clima reconocibles: guardamos la hoja tal cual.
            df_hoja = raw.copy()
            por_variable[nombre_hoja] = {
                "df": df_hoja,
                "fila_header": 0,
                "columnas_clima": [],
                "columnas_meta": list(df_hoja.columns),
                "escenarios": [],
                "anios": [],
            }
            continue

        # Construir DataFrame con las cabeceras detectadas.
        encabezados = raw.iloc[fila_header].tolist()
        nombres_col = [
            str(h).strip() if pd.notna(h) else f"col_{i}"
            for i, h in enumerate(encabezados)
        ]
        df_hoja = raw.iloc[fila_header + 1:].copy()
        df_hoja.columns = nombres_col
        df_hoja = df_hoja.reset_index(drop=True).dropna(how="all")

        # Correccion ortografica global de la columna Mes.
        if "Mes" in df_hoja.columns:
            df_hoja["Mes"] = df_hoja["Mes"].map(_corregir_mes)

        columnas_clima = []
        for cc in cols_clima:
            nombre_col = nombres_col[cc["col"]]
            columnas_clima.append({
                "columna": nombre_col,
                "anio": cc["anio"],
                "escenario": cc["escenario"],
                "texto": cc["texto"],
            })
            if cc["escenario"]:
                escenarios_glob.add(cc["escenario"])
            if cc["anio"]:
                anios_glob.add(cc["anio"])

        cols_clima_nombres = {c["columna"] for c in columnas_clima}
        columnas_meta = [c for c in nombres_col if c not in cols_clima_nombres]

        por_variable[nombre_hoja] = {
            "df": df_hoja,
            "fila_header": fila_header,
            "columnas_clima": columnas_clima,
            "columnas_meta": columnas_meta,
            "escenarios": sorted({c["escenario"] for c in columnas_clima if c["escenario"]}),
            "anios": sorted({c["anio"] for c in columnas_clima if c["anio"]}),
        }

    return {
        "ruta": str(ruta),
        "fuente": meta.id,
        "variables": list(por_variable.keys()),
        "escenarios": sorted(escenarios_glob),
        "anios": sorted(anios_glob),
        "por_variable": por_variable,
    }


def construir_resumen_clima(info: dict) -> pd.DataFrame:
    """Combina todas las variables en una tabla "larga" (tidy).

    Convierte las columnas de proyeccion (escenario x anio) en filas, de modo que
    el resumen incluye TODAS las variables, escenarios, horizontes y percentiles.

    Columnas: Variable, Indicador, Descripción, Mes, Percentil, Escenario, Año,
    Valor, Lon, Lat (las que existan).
    """
    frames: list[pd.DataFrame] = []
    for variable, v in info["por_variable"].items():
        cols_clima = v["columnas_clima"]
        if not cols_clima:
            continue
        df = v["df"]
        meta_cols = [c for c in v["columnas_meta"] if c in df.columns]
        mapa = {c["columna"]: (c["escenario"], c["anio"]) for c in cols_clima}

        largo = df.melt(
            id_vars=meta_cols,
            value_vars=list(mapa.keys()),
            var_name="_col",
            value_name="Valor",
        )
        largo["Escenario"] = largo["_col"].map(lambda x: mapa[x][0])
        largo["Año"] = largo["_col"].map(lambda x: mapa[x][1])
        largo = largo.drop(columns=["_col"])
        largo.insert(0, "Variable", variable)
        frames.append(largo)

    if not frames:
        return pd.DataFrame()

    resumen = pd.concat(frames, ignore_index=True)

    # Ordenar columnas de forma legible; el resto se anade al final.
    preferidas = [
        "Variable", "Indicador", "Descripción", "Mes", "Percentil",
        "Escenario", "Año", "Valor", "Lon", "Lat",
    ]
    columnas = [c for c in preferidas if c in resumen.columns]
    columnas += [c for c in resumen.columns if c not in columnas]
    return resumen[columnas]


def resumen_unicos_clima(info: dict) -> pd.DataFrame:
    """Resumen compacto: valores unicos por campo categorico (dimensiones).

    Incluye SOLO: Variable, Indicador, Descripción, Mes, Percentil, Escenario, Año.
    NO incluye 'Valor' ni las coordenadas 'Lon'/'Lat'.

    Returns
    -------
    DataFrame con columnas ['Campo', 'Nº únicos', 'Valores'] (texto compacto).
    """
    def unicos(seq) -> list:
        salida = []
        vistos = set()
        for v in seq:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                continue
            s = str(v).strip()
            if s == "" or s.lower() in ("nan", "none"):
                continue
            if s not in vistos:
                vistos.add(s)
                salida.append(s)
        return salida

    # Variables = hojas con datos de clima (si no hay, todas).
    variables = [v for v, d in info["por_variable"].items() if d["columnas_clima"]]
    if not variables:
        variables = list(info["por_variable"].keys())

    def limpiar_meses(valores) -> list:
        # Quita el "-" (no es un mes) y corrige "semptiembre" -> "septiembre".
        salida = []
        for v in valores:
            s = str(v).strip()
            if s in ("-", ""):
                continue
            if s.lower() == "semptiembre":
                s = "Septiembre" if s[:1].isupper() else "septiembre"
            salida.append(s)
        return list(dict.fromkeys(salida))

    # Campos descriptivos que se acumulan de cada hoja.
    campos_meta = ["Mes", "Percentil"]
    acumulado = {campo: [] for campo in campos_meta}
    for d in info["por_variable"].values():
        df = d["df"]
        for campo in campos_meta:
            if campo in df.columns:
                acumulado[campo].extend(df[campo].tolist())

    pares = [
        ("Variable", unicos(variables)),
        ("Mes", limpiar_meses(unicos(acumulado["Mes"]))),
        ("Percentil", unicos(acumulado["Percentil"])),
        ("Escenario", unicos(info.get("escenarios", []))),
        ("Año", unicos(str(a) for a in info.get("anios", []))),
    ]

    return pd.DataFrame({
        "Campo": [campo for campo, _ in pares],
        "Valores": [", ".join(vals) for _, vals in pares],
    })


def leer_escenarios(
    hoja: str = "Oleaje",
    data_dirs: list[Path] = DATA_DIRS,
) -> tuple[list[int], list[str]]:
    """Devuelve (anios, escenarios) de una hoja (equivalente a `leer_escenarios.m`).

    Por defecto usa la hoja 'Oleaje', como el MATLAB original; si no existe, usa
    la primera hoja con columnas de clima.
    """
    info = cargar_datos_clima(data_dirs)
    variable = info["por_variable"].get(hoja)
    if variable is None:
        # Buscar la primera hoja que tenga escenarios/anios.
        for v in info["por_variable"].values():
            if v["escenarios"] or v["anios"]:
                variable = v
                break
    if variable is None:
        return [], []
    return variable["anios"], variable["escenarios"]


def _limpiar_columnas_preguntar_impactos(columnas: list) -> list[str]:
    """Normaliza cabeceras; renombra Unnamed/vacías a «Descripción»."""
    usados: dict[str, int] = {}
    salida: list[str] = []
    for i, raw in enumerate(columnas):
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            nombre = "Descripción"
        else:
            nombre = str(raw).strip()
            if not nombre or nombre.lower().startswith("unnamed"):
                nombre = "Descripción"
        if nombre in usados:
            usados[nombre] += 1
            nombre = f"{nombre}_{usados[nombre]}"
        else:
            usados[nombre] = 0
        salida.append(nombre)
    return salida


def cargar_preguntar_impactos(
    data_dirs: list[Path] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Carga el Excel de impactos a preguntar / marcar para cálculo.

    Busca ``Preguntar_si_se_calculan.xlsx`` en ``Preguntar_impactos/`` (raíz del
    proyecto) y, si no está, en las carpetas de datos habituales.
    """
    dirs = list(data_dirs) if data_dirs is not None else [
        DIR_PREGUNTAR_IMPACTOS,
        DIR_DATOS_MODELOS,
        DIR_DATOS_SECCIONES,
    ]
    ruta = localizar_excel("Preguntar_si_se_calculan", dirs, parcial=True)
    if ruta is None:
        ruta_directa = DIR_PREGUNTAR_IMPACTOS / ARCHIVO_PREGUNTAR_IMPACTOS
        raise FileNotFoundError(
            f"No se encontró '{ARCHIVO_PREGUNTAR_IMPACTOS}' en: "
            + ", ".join(str(d) for d in dirs)
            + f" (esperado: {ruta_directa})"
        )

    hojas = pd.read_excel(ruta, sheet_name=None)
    nombre_hoja = next(iter(hojas))
    bruto = hojas[nombre_hoja]
    df = bruto.dropna(how="all").copy().reset_index(drop=True)
    df.columns = _limpiar_columnas_preguntar_impactos(list(df.columns))

    col_activo = _buscar_columna(
        list(df.columns),
        "activo fisico u operacional",
        "activo físico u operacional",
        "activo fisico",
        "activo",
    )
    if col_activo is not None:
        df[col_activo] = df[col_activo].ffill()
        df[col_activo] = df[col_activo].map(
            lambda v: str(v).strip()
            if v is not None and not (isinstance(v, float) and pd.isna(v))
            else v
        )

    info = {
        "ruta": str(ruta),
        "hoja": nombre_hoja,
        "total": len(df),
        "columnas": list(df.columns),
        "fuente": "preguntar_impactos",
    }
    return df, info


def cargar_configuracion_puerto(
    data_dirs: list[Path] = DATA_DIRS,
) -> tuple[pd.DataFrame, dict]:
    """Carga el Excel de configuración del puerto (UO, activos, servicios)."""
    meta = fuente("config_puerto")
    ruta = _resolver_ruta(meta, data_dirs)

    hojas = pd.read_excel(ruta, sheet_name=None, header=None)
    por_hoja: dict[str, pd.DataFrame] = {}
    for nombre_hoja, raw in hojas.items():
        df = _leer_hoja_umbrales(raw)
        if not df.empty:
            por_hoja[nombre_hoja] = df

    if not por_hoja:
        return pd.DataFrame(), {
            "ruta": str(ruta),
            "hoja": next(iter(hojas), ""),
            "hojas": [],
            "por_hoja": {},
            "totales": {},
            "total": 0,
        }

    hoja_principal = next(iter(por_hoja))
    info = {
        "ruta": str(ruta),
        "hoja": hoja_principal,
        "hojas": list(por_hoja.keys()),
        "por_hoja": por_hoja,
        "totales": {h: len(df) for h, df in por_hoja.items()},
        "total": len(por_hoja[hoja_principal]),
        "fuente": meta.id,
    }
    return por_hoja[hoja_principal], info


def cargar_relacion_modelos_activos_indicadores(
    data_dirs: list[Path] = DATA_DIRS,
) -> tuple[pd.DataFrame, dict]:
    """Carga percentiles e indicadores fijos por modelo / activo / modo de fallo."""
    meta = fuente("relacion_modelos")
    try:
        ruta = _resolver_ruta(meta, data_dirs)
    except FileNotFoundError:
        return pd.DataFrame(), {
            "ruta": "",
            "origen": "ausente",
            "total": 0,
            "fuente": meta.id,
        }

    hojas = pd.read_excel(ruta, sheet_name=None)
    nombre_hoja = _elegir_hoja(list(hojas.keys()), preferida="Relación")
    bruto = hojas[nombre_hoja]
    bruto.columns = [str(c).strip() for c in bruto.columns]
    df = bruto.dropna(how="all").copy()

    info = {
        "ruta": str(ruta),
        "hoja": nombre_hoja,
        "origen": "excel",
        "total": len(df),
        "fuente": meta.id,
        "columnas": list(df.columns),
    }
    return df, info


def _completar_coordenadas(df: pd.DataFrame) -> pd.DataFrame:
    """Rellena lat/lon que falten cruzando por nombre con la lista por defecto."""
    ref = {_normalizar(p["puerto"]): (p["lat"], p["lon"]) for p in PUERTOS_DEFECTO}
    for i, fila in df.iterrows():
        falta_lat = pd.isna(fila.get("lat"))
        falta_lon = pd.isna(fila.get("lon"))
        if falta_lat or falta_lon:
            clave = _normalizar(fila["puerto"])
            if clave in ref:
                lat, lon = ref[clave]
                if falta_lat:
                    df.at[i, "lat"] = lat
                if falta_lon:
                    df.at[i, "lon"] = lon
    return df


# ---------------------------------------------------------------------------
# Umbrales y curvas de daño vs activos (Excel multi-hoja, esquema flexible).
# ---------------------------------------------------------------------------

_HOJAS_EXCLUIR_UMBRALES = fuente("umbrales").hojas_excluir


def _hoja_umbrales_excluida(nombre_hoja: str, patrones: tuple[str, ...] | None = None) -> bool:
    """True si la hoja no debe cargarse (ListRelacion…, CONTAR, variantes)."""
    return _hoja_excluida(nombre_hoja, patrones or _HOJAS_EXCLUIR_UMBRALES)


def _detectar_fila_cabecera_umbrales(raw: pd.DataFrame, max_filas: int = 15) -> int:
    """Primera fila con al menos dos celdas no vacías."""
    for r in range(min(max_filas, len(raw))):
        if raw.iloc[r].notna().sum() >= 2:
            return r
    return 0


def _nombre_columna_umbrales(valor: object, indice: int) -> str:
    """Normaliza encabezados (p. ej. No -> Nº) conservando el resto tal cual."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return f"col_{indice}"
    nombre = str(valor).strip()
    if not nombre or nombre.lower() in ("nan", "none"):
        return f"col_{indice}"
    if _normalizar(nombre) in ("no", "n", "num", "nº", "n°"):
        return "Nº"
    return nombre


def _leer_hoja_umbrales(raw: pd.DataFrame) -> pd.DataFrame:
    """Lee una hoja con cabecera auto-detectada; admite filas/columnas variables."""
    if raw is None or raw.empty:
        return pd.DataFrame()

    fila_header = _detectar_fila_cabecera_umbrales(raw)
    encabezados_raw = raw.iloc[fila_header].tolist()

    encabezados: list[str] = []
    usados: dict[str, int] = {}
    for i, h in enumerate(encabezados_raw):
        nombre = _nombre_columna_umbrales(h, i)
        if nombre in usados:
            usados[nombre] += 1
            nombre = f"{nombre}_{usados[nombre]}"
        else:
            usados[nombre] = 0
        encabezados.append(nombre)

    df = raw.iloc[fila_header + 1:].copy().reset_index(drop=True)
    n_cols = df.shape[1]
    while len(encabezados) < n_cols:
        encabezados.append(f"col_{len(encabezados)}")
    df.columns = encabezados[:n_cols]
    df = df.dropna(how="all")

    # Solo quitar columnas sin nombre (col_N) totalmente vacías; conservar
    # encabezados del Excel aunque aún no tengan valores (umbrales futuros).
    vacias = []
    for c in df.columns:
        if str(c).startswith("col_"):
            serie = df[c]
            if serie.isna().all() or serie.astype(str).str.strip().isin(("", "nan", "None")).all():
                vacias.append(c)
    if vacias:
        df = df.drop(columns=vacias)

    if "Nº" in df.columns:
        df["Nº"] = pd.to_numeric(df["Nº"], errors="coerce")
        df = df.dropna(subset=["Nº"])
        df["Nº"] = df["Nº"].astype(int)

    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# Hoja de "Unidad de medida": asocia cada modo de fallo/parada con su unidad
# (m, m/s, mm, °C, km...). El nombre real en el Excel es "UnidadMedida", pero
# admitimos variantes ("Unidad Medida", "Unidad de Medida", "Unidad_Medida"...)
# igual que hacemos con las columnas de puertos: detección tolerante a
# mayúsculas, acentos, espacios y guiones bajos.
# ---------------------------------------------------------------------------

COLUMNAS_UNIDAD_MEDIDA: tuple[str, ...] = (
    "Modos de fallo / Modos de parada",
    "Unidad de medida",
)


def _es_hoja_unidad_medida(nombre_hoja: str) -> bool:
    """True si el nombre de la hoja se refiere a la unidad de medida (tolerante)."""
    n = _normalizar(nombre_hoja).replace("_", " ")
    return "unidad" in n and "medida" in n


def _leer_hoja_unidad_medida(raw: pd.DataFrame) -> pd.DataFrame:
    """Normaliza la hoja de unidades a ['Modos de fallo / Modos de parada', 'Unidad de medida'].

    El Excel trae encabezados escuetos ("Fallo", "UM"); los detectamos de forma
    flexible (por nombre, con y sin acentos) como en `cargar_lista_puertos`.
    """
    df = _leer_hoja_umbrales(raw)
    if df.empty:
        return pd.DataFrame(columns=list(COLUMNAS_UNIDAD_MEDIDA))

    columnas = list(df.columns)
    col_fallo = _buscar_columna(
        columnas,
        "modos de fallo / modos de parada",
        "modos de fallo",
        "modos de parada",
        "modo de fallo",
        "modo de parada",
        "fallo",
        "modo",
    )
    col_um = _buscar_columna(
        columnas,
        "unidad de medida",
        "unidad medida",
        "unidad",
        "um",
        "u.m.",
        "u. m.",
    )
    if col_fallo is None:
        col_fallo = columnas[0]
    if col_um is None:
        # La unidad suele ser la segunda columna con datos.
        restantes = [c for c in columnas if c != col_fallo]
        col_um = restantes[0] if restantes else None

    salida = pd.DataFrame()
    salida["Modos de fallo / Modos de parada"] = df[col_fallo].map(_valor_limpio)
    salida["Unidad de medida"] = (
        df[col_um].map(_valor_limpio) if col_um is not None else None
    )
    salida = salida.dropna(subset=["Modos de fallo / Modos de parada"])
    return salida.reset_index(drop=True)


def _mapa_unidad_medida(df_um: pd.DataFrame) -> dict[str, str]:
    """Diccionario {modo_de_fallo_normalizado: unidad} a partir de la hoja de unidades."""
    mapa: dict[str, str] = {}
    if df_um is None or df_um.empty:
        return mapa
    for _, fila in df_um.iterrows():
        # `_valor_limpio` descarta vacíos y NaN (evita guardar "nan" como unidad).
        modo = _valor_limpio(fila.get("Modos de fallo / Modos de parada"))
        unidad = _valor_limpio(fila.get("Unidad de medida"))
        if modo and unidad:
            mapa[_normalizar(modo)] = unidad
    return mapa


def cargar_unidad_medida(
    data_dirs: list[Path] = DATA_DIRS,
) -> tuple[pd.DataFrame, dict]:
    """Carga la hoja de unidades de medida del Excel de umbrales (detección tolerante).

    Returns
    -------
    (df, info)
        df: DataFrame ['Modos de fallo / Modos de parada', 'Unidad de medida'].
        info: {'ruta', 'hoja', 'total', 'fuente', 'mapa'} donde 'mapa' es
              {modo_normalizado: unidad}.
    """
    meta = fuente("umbrales")
    ruta = _resolver_ruta(meta, data_dirs)

    hojas = pd.read_excel(ruta, sheet_name=None, header=None)
    for nombre_hoja, raw in hojas.items():
        if _es_hoja_unidad_medida(nombre_hoja):
            df = _leer_hoja_unidad_medida(raw)
            return df, {
                "ruta": str(ruta),
                "hoja": nombre_hoja,
                "total": len(df),
                "fuente": meta.id,
                "mapa": _mapa_unidad_medida(df),
            }

    return pd.DataFrame(columns=list(COLUMNAS_UNIDAD_MEDIDA)), {
        "ruta": str(ruta),
        "hoja": None,
        "total": 0,
        "fuente": meta.id,
        "mapa": {},
    }


def cargar_umbrales_curvas_dano(
    data_dirs: list[Path] = DATA_DIRS,
) -> tuple[dict[str, pd.DataFrame], dict]:
    """Carga las hojas del Excel de umbrales/curvas (excepto las excluidas en fuentes_datos)."""
    meta = fuente("umbrales")
    ruta = _resolver_ruta(meta, data_dirs)

    hojas = pd.read_excel(ruta, sheet_name=None, header=None)
    por_hoja: dict[str, pd.DataFrame] = {}
    excluidas: list[str] = []
    lista_impactos_indicador: pd.DataFrame | None = None
    df_unidad_medida: pd.DataFrame | None = None
    hoja_unidad_medida: str | None = None
    mapa_unidad_medida: dict[str, str] = {}

    for nombre_hoja, raw in hojas.items():
        if _normalizar(nombre_hoja).startswith("listrelacion impactos"):
            df_lista = _leer_hoja_umbrales(raw)
            if not df_lista.empty:
                lista_impactos_indicador = df_lista
            excluidas.append(nombre_hoja)
            continue
        # Hoja de unidades de medida: se normaliza aparte y se usa para enriquecer
        # el resto de pestañas con la columna "Unidad de medida".
        if _es_hoja_unidad_medida(nombre_hoja):
            df_unidad_medida = _leer_hoja_unidad_medida(raw)
            mapa_unidad_medida = _mapa_unidad_medida(df_unidad_medida)
            hoja_unidad_medida = nombre_hoja
            excluidas.append(nombre_hoja)
            continue
        if _hoja_umbrales_excluida(nombre_hoja, meta.hojas_excluir):
            excluidas.append(nombre_hoja)
            continue
        df = _leer_hoja_umbrales(raw)
        if not df.empty:
            por_hoja[nombre_hoja] = df

    # Enriquecer cada pestaña de variable con su unidad de medida (según el modo
    # de fallo/parada de cada fila). La hoja UnidadMedida no se muestra en la UI.
    if mapa_unidad_medida:
        for nombre_hoja, df in por_hoja.items():
            if (
                "Modos de fallo / Modos de parada" in df.columns
                and "Unidad de medida" not in df.columns
            ):
                unidades = df["Modos de fallo / Modos de parada"].map(
                    lambda v: mapa_unidad_medida.get(_normalizar(v))
                    if v is not None and not (isinstance(v, float) and pd.isna(v))
                    else None
                )
                pos = df.columns.get_loc("Modos de fallo / Modos de parada") + 1
                df.insert(pos, "Unidad de medida", unidades)

    info = {
        "ruta": str(ruta),
        "hojas": list(por_hoja.keys()),
        "hojas_excluidas": excluidas,
        "totales": {h: len(df) for h, df in por_hoja.items()},
        "lista_impactos_indicador": lista_impactos_indicador,
        "unidad_medida": (
            df_unidad_medida
            if df_unidad_medida is not None
            else pd.DataFrame(columns=list(COLUMNAS_UNIDAD_MEDIDA))
        ),
        "hoja_unidad_medida": hoja_unidad_medida,
        "mapa_unidad_medida": mapa_unidad_medida,
        "fuente": meta.id,
    }
    return por_hoja, info


def cargar_tipo_de_uo(
    data_dirs: list[Path] = DATA_DIRS,
) -> tuple[pd.DataFrame, dict]:
    """Carga los tipos de UO desde ``Tipo_de_UO.xlsx`` (esquema flexible)."""
    meta = fuente("tipos_uo")
    ruta = _resolver_ruta(meta, data_dirs)

    hojas = pd.read_excel(ruta, sheet_name=None, header=None)
    por_hoja: dict[str, pd.DataFrame] = {}
    for nombre_hoja, raw in hojas.items():
        df = _leer_hoja_umbrales(raw)
        if not df.empty:
            por_hoja[nombre_hoja] = df

    if not por_hoja:
        raise ValueError(f"El archivo {ruta.name} no tiene hojas con datos.")

    hoja = _elegir_hoja(list(por_hoja.keys()), meta.hoja)
    df = por_hoja[hoja].copy()

    col_tipo = _buscar_columna(
        list(df.columns),
        "tipo de uo",
        "tipo uo",
        "tipo de terminal",
        "tipo",
    )
    if col_tipo and col_tipo != "Tipo de UO":
        df = df.rename(columns={col_tipo: "Tipo de UO"})

    info = {
        "ruta": str(ruta),
        "hoja": hoja,
        "hojas": list(por_hoja.keys()),
        "por_hoja": por_hoja,
        "total": len(df),
        "fuente": meta.id,
    }
    return df, info
