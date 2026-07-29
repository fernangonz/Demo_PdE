# -*- coding: utf-8 -*-
"""Lectura de indicadores climaticos desde archivos .mat (Impacto_N).

Estructura esperada bajo ``P:\\99_TOOLRIESGO_PDE\\10_Indicadores``::

    <driver>/Impacto_1.mat   -> rejilla espacial (CoordenadaX/Y, Baseline, Proyecciones)
    <driver>/Impacto_11.mat  -> serie por puerto (Puerto, Baseline, Proyecciones)

Si un campo no existe o esta vacio, la UI debe mostrar ``-``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.io import loadmat

RUTA_INDICADORES_DEFAULT = Path(r"P:\99_TOOLRIESGO_PDE\10_Indicadores")

# Etiquetas en espanol para carpetas de driver.
ETIQUETAS_DRIVER: dict[str, str] = {
    "corriente": "Corriente",
    "inundacion_costera": "Inundaci\u00f3n costera",
    "nivel_del_mar": "Nivel del mar",
    "oleaje": "Oleaje",
    "precipitacion": "Precipitaci\u00f3n",
    "temperatura": "Temperatura",
    "viento": "Viento",
    "visibilidad": "Visibilidad",
}

# Escenarios tipicos en los .mat actuales (string array MCOS).
ESCENARIOS_DEFAULT = ("ssp245", "ssp585")

# Percentiles previstos por la herramienta de referencia (aun no en .mat).
PERCENTILES_UI = ("P50", "P66", "P95")

MISSING = "-"


@dataclass(frozen=True)
class ImpactoInfo:
    """Metadatos de un archivo Impacto_N.mat."""

    driver_id: str
    driver_label: str
    impacto_id: str
    ruta: Path
    tipo: str  # "espacial" | "puertos" | "desconocido"
    n_items: int
    n_con_datos: int


@dataclass
class SeriePuerto:
    puerto: str
    baseline: float | None
    centros: list[int]
    escenarios: list[str]
    # proyecciones[periodo_idx][escenario_idx] -> float | None
    proyecciones: np.ndarray  # shape (n_periodos, n_escenarios)


@dataclass
class CampoEspacial:
    puerto: str | None
    centros: list[int]
    escenarios: list[str]
    lon: np.ndarray  # 2D
    lat: np.ndarray  # 2D
    baseline: np.ndarray  # 2D
    # proyecciones: object/float array (n_periodos, n_escenarios) of 2D grids
    proyecciones: np.ndarray
    item_index: int


@dataclass
class ImpactoCargado:
    info: ImpactoInfo
    series_puerto: list[SeriePuerto] = field(default_factory=list)
    campos_espaciales: list[CampoEspacial] = field(default_factory=list)
    centros: list[int] = field(default_factory=list)
    escenarios: list[str] = field(default_factory=list)


def _normalizar(texto: object) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    return "".join(c for c in t if c.isalnum())


def _limpiar_texto(s: str) -> str:
    s = "".join(ch for ch in s if ch.isprintable())
    return re.sub(r"\s+", " ", s).strip()


def etiqueta_driver(driver_id: str) -> str:
    if driver_id in ETIQUETAS_DRIVER:
        return ETIQUETAS_DRIVER[driver_id]
    return driver_id.replace("_", " ").strip().capitalize()


def etiqueta_impacto(impacto_id: str) -> str:
    """Nombre mostrable; el catalogo de impactos aun no esta definido."""
    m = re.match(r"(?i)impacto[_\s-]?(\d+)$", impacto_id.strip())
    if m:
        return f"Impacto {m.group(1)}"
    return impacto_id


def fmt_valor(valor: Any, ndigits: int = 4) -> str:
    if valor is None:
        return MISSING
    try:
        if isinstance(valor, (float, np.floating)) and not np.isfinite(valor):
            return MISSING
        if isinstance(valor, (int, np.integer)):
            return str(int(valor))
        v = float(valor)
        if not np.isfinite(v):
            return MISSING
        return f"{v:.{ndigits}g}"
    except (TypeError, ValueError):
        return MISSING


def _read_utf16_z(blob: bytes, start: int) -> tuple[str, int]:
    chars: list[str] = []
    i = start
    while i + 1 < len(blob):
        code = blob[i] | (blob[i + 1] << 8)
        i += 2
        if code == 0:
            break
        chars.append(chr(code))
        if len(chars) > 240:
            break
    return "".join(chars), i


def _extraer_strings_prefijo(blob: bytes, prefix: str) -> list[str]:
    needle = prefix.encode("utf-16-le")
    out: list[str] = []
    start = 0
    while True:
        idx = blob.find(needle, start)
        if idx < 0:
            break
        s, end = _read_utf16_z(blob, idx)
        s = _limpiar_texto(s)
        if s:
            out.append(s)
        start = max(end, idx + 2)
    seen: set[str] = set()
    uniq: list[str] = []
    for s in out:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def _extraer_escenarios(blob: bytes) -> list[str]:
    """Busca tokens ssp### / rcp#.# en el workspace MCOS."""
    found: list[str] = []
    for pref in ("ssp", "SSP", "rcp", "RCP"):
        needle = pref.encode("utf-16-le")
        start = 0
        while True:
            idx = blob.find(needle, start)
            if idx < 0:
                break
            s, end = _read_utf16_z(blob, idx)
            s = _limpiar_texto(s)
            # A veces vienen concatenados: ssp245ssp585
            partes = re.findall(r"(?i)(?:ssp\d{2,3}|rcp\d\.?\d)", s)
            if partes:
                found.extend(partes)
            elif s and len(s) <= 16:
                found.append(s)
            start = max(end, idx + 2)
    seen: set[str] = set()
    uniq: list[str] = []
    for s in found:
        key = s.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(s.lower() if s.lower().startswith("ssp") else s)
    return uniq or list(ESCENARIOS_DEFAULT)


def _es_vacio(val: Any) -> bool:
    if val is None:
        return True
    if isinstance(val, np.ndarray) and val.size == 0:
        return True
    if isinstance(val, (float, np.floating)) and not np.isfinite(val):
        return True
    return False


def _a_float_o_none(val: Any) -> float | None:
    if _es_vacio(val):
        return None
    try:
        if isinstance(val, np.ndarray):
            if val.size == 0:
                return None
            val = val.astype(float).ravel()[0]
        v = float(val)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _centros_ventana(val: Any) -> list[int]:
    if _es_vacio(val):
        return []
    arr = np.asarray(val).astype(float).ravel()
    out: list[int] = []
    for x in arr:
        if np.isfinite(x):
            out.append(int(x))
    return out


def _matriz_proyecciones_scalar(val: Any) -> np.ndarray | None:
    """Proyecciones (n_periodos, n_escenarios) numericas."""
    if _es_vacio(val):
        return None
    arr = np.asarray(val)
    if arr.dtype == object:
        # Puede ser rejillas 2D por celda
        return arr
    try:
        out = arr.astype(float)
        return out
    except (TypeError, ValueError):
        return None


def _detectar_tipo(items: np.ndarray) -> str:
    for item in items:
        if not hasattr(item, "_fieldnames"):
            continue
        fields = set(item._fieldnames)
        cx = getattr(item, "CoordenadaX", None) if "CoordenadaX" in fields else None
        if isinstance(cx, np.ndarray) and cx.size > 0:
            return "espacial"
        proy = getattr(item, "Proyecciones", None) if "Proyecciones" in fields else None
        if isinstance(proy, np.ndarray) and proy.size > 0 and proy.dtype != object:
            return "puertos"
        if isinstance(proy, np.ndarray) and proy.dtype == object and proy.size > 0:
            sample = proy.ravel()[0]
            if isinstance(sample, np.ndarray) and sample.ndim == 2:
                return "espacial"
            if isinstance(sample, (float, np.floating, int, np.integer)):
                return "puertos"
    return "desconocido"


def descubrir_impactos(raiz: Path | None = None) -> list[ImpactoInfo]:
    """Recorre carpetas de driver y lista archivos Impacto_*.mat."""
    raiz = Path(raiz or RUTA_INDICADORES_DEFAULT)
    if not raiz.is_dir():
        return []
    resultado: list[ImpactoInfo] = []
    for carpeta in sorted(raiz.iterdir(), key=lambda p: p.name.lower()):
        if not carpeta.is_dir():
            continue
        driver_id = carpeta.name
        for mat in sorted(carpeta.glob("Impacto_*.mat")) + sorted(carpeta.glob("impacto_*.mat")):
            # Evitar duplicados por case
            if any(i.ruta.resolve() == mat.resolve() for i in resultado):
                continue
            try:
                raw = loadmat(mat, struct_as_record=False, squeeze_me=True)
            except Exception:
                resultado.append(
                    ImpactoInfo(
                        driver_id=driver_id,
                        driver_label=etiqueta_driver(driver_id),
                        impacto_id=mat.stem,
                        ruta=mat,
                        tipo="desconocido",
                        n_items=0,
                        n_con_datos=0,
                    )
                )
                continue
            keys = [k for k in raw if not k.startswith("__")]
            if not keys:
                continue
            arr = np.atleast_1d(raw[keys[0]]).ravel()
            tipo = _detectar_tipo(arr)
            n_datos = 0
            for item in arr:
                if not hasattr(item, "_fieldnames"):
                    continue
                proy = getattr(item, "Proyecciones", None)
                base = getattr(item, "Baseline", None)
                cx = getattr(item, "CoordenadaX", None)
                if isinstance(cx, np.ndarray) and cx.size > 0:
                    n_datos += 1
                elif isinstance(proy, np.ndarray) and proy.size > 0:
                    n_datos += 1
                elif _a_float_o_none(base) is not None:
                    n_datos += 1
            resultado.append(
                ImpactoInfo(
                    driver_id=driver_id,
                    driver_label=etiqueta_driver(driver_id),
                    impacto_id=mat.stem,
                    ruta=mat,
                    tipo=tipo,
                    n_items=len(arr),
                    n_con_datos=n_datos,
                )
            )
    return resultado


def listar_drivers(raiz: Path | None = None) -> list[tuple[str, str]]:
    """Lista (id, etiqueta) de drivers con al menos un .mat."""
    infos = descubrir_impactos(raiz)
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for info in infos:
        if info.driver_id not in seen:
            seen.add(info.driver_id)
            out.append((info.driver_id, info.driver_label))
    # Incluir carpetas vacias para que el filtro exista aunque sin datos
    raiz = Path(raiz or RUTA_INDICADORES_DEFAULT)
    if raiz.is_dir():
        for carpeta in sorted(raiz.iterdir(), key=lambda p: p.name.lower()):
            if carpeta.is_dir() and carpeta.name not in seen:
                out.append((carpeta.name, etiqueta_driver(carpeta.name)))
                seen.add(carpeta.name)
    return out


@lru_cache(maxsize=32)
def cargar_impacto(ruta_str: str) -> ImpactoCargado:
    """Carga un Impacto_N.mat y normaliza puertos / rejillas."""
    ruta = Path(ruta_str)
    driver_id = ruta.parent.name
    raw = loadmat(ruta, struct_as_record=False, squeeze_me=True)
    keys = [k for k in raw if not k.startswith("__")]
    if not keys:
        info = ImpactoInfo(
            driver_id=driver_id,
            driver_label=etiqueta_driver(driver_id),
            impacto_id=ruta.stem,
            ruta=ruta,
            tipo="desconocido",
            n_items=0,
            n_con_datos=0,
        )
        return ImpactoCargado(info=info)

    blob = b""
    if "__function_workspace__" in raw:
        blob = np.asarray(raw["__function_workspace__"]).astype(np.uint8).ravel().tobytes()
    nombres_puerto = _extraer_strings_prefijo(blob, "PUERTO") if blob else []
    escenarios_ws = _extraer_escenarios(blob) if blob else list(ESCENARIOS_DEFAULT)

    arr = np.atleast_1d(raw[keys[0]]).ravel()
    tipo = _detectar_tipo(arr)
    series: list[SeriePuerto] = []
    campos: list[CampoEspacial] = []
    centros_global: list[int] = []
    escenarios_global: list[str] = list(escenarios_ws)

    for i, item in enumerate(arr):
        if not hasattr(item, "_fieldnames"):
            continue
        fields = set(item._fieldnames)
        centros = _centros_ventana(getattr(item, "CentroVentana", None)) if "CentroVentana" in fields else []
        if centros and not centros_global:
            centros_global = centros

        puerto_nombre = nombres_puerto[i] if i < len(nombres_puerto) else f"Punto {i + 1}"
        cx = getattr(item, "CoordenadaX", None) if "CoordenadaX" in fields else None
        cy = getattr(item, "CoordenadaY", None) if "CoordenadaY" in fields else None
        baseline = getattr(item, "Baseline", None) if "Baseline" in fields else None
        proy = getattr(item, "Proyecciones", None) if "Proyecciones" in fields else None

        if isinstance(cx, np.ndarray) and isinstance(cy, np.ndarray) and cx.size > 0 and cy.size > 0:
            proy_arr = _matriz_proyecciones_scalar(proy)
            if proy_arr is None:
                proy_arr = np.empty((0, 0), dtype=object)
            base_arr = np.asarray(baseline, dtype=float) if not _es_vacio(baseline) else np.full(cx.shape, np.nan)
            n_esc = proy_arr.shape[1] if proy_arr.ndim == 2 and proy_arr.size else len(escenarios_global)
            if len(escenarios_global) < n_esc:
                escenarios_global = [f"escenario_{j+1}" for j in range(n_esc)]
            campos.append(
                CampoEspacial(
                    puerto=puerto_nombre if nombres_puerto else None,
                    centros=centros or centros_global,
                    escenarios=list(escenarios_global[:n_esc]),
                    lon=np.asarray(cx, dtype=float),
                    lat=np.asarray(cy, dtype=float),
                    baseline=base_arr,
                    proyecciones=proy_arr,
                    item_index=i,
                )
            )
            continue

        proy_arr = _matriz_proyecciones_scalar(proy)
        if proy_arr is None or proy_arr.dtype == object:
            # Sin rejilla ni serie numerica util
            base_f = _a_float_o_none(baseline)
            if base_f is None and (proy_arr is None or proy_arr.size == 0):
                continue
            if proy_arr is None or proy_arr.dtype == object:
                proy_num = np.full((len(centros) or 1, len(escenarios_global)), np.nan)
            else:
                proy_num = proy_arr.astype(float)
        else:
            proy_num = proy_arr.astype(float)

        n_esc = proy_num.shape[1] if proy_num.ndim == 2 else len(escenarios_global)
        esc = list(escenarios_global[:n_esc]) if n_esc else list(escenarios_global)
        if len(esc) < n_esc:
            esc = [f"escenario_{j+1}" for j in range(n_esc)]
        series.append(
            SeriePuerto(
                puerto=puerto_nombre,
                baseline=_a_float_o_none(baseline),
                centros=centros or centros_global,
                escenarios=esc,
                proyecciones=proy_num,
            )
        )

    if tipo == "desconocido":
        if campos:
            tipo = "espacial"
        elif series:
            tipo = "puertos"

    info = ImpactoInfo(
        driver_id=driver_id,
        driver_label=etiqueta_driver(driver_id),
        impacto_id=ruta.stem,
        ruta=ruta,
        tipo=tipo,
        n_items=len(arr),
        n_con_datos=len(campos) + len(series),
    )
    return ImpactoCargado(
        info=info,
        series_puerto=series,
        campos_espaciales=campos,
        centros=centros_global,
        escenarios=escenarios_global,
    )


def puerto_mas_cercano(
    lat: float, lon: float, coords: pd.DataFrame
) -> tuple[str, float, float, float] | None:
    """Devuelve (nombre, lat, lon, distancia_km) del puerto mas cercano al clic."""
    if coords is None or coords.empty:
        return None
    best = None
    best_d = float("inf")
    for _, row in coords.iterrows():
        try:
            la, lo = float(row["lat"]), float(row["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        # Distancia aproximada en km (equirectangular)
        dy = (la - lat) * 111.0
        dx = (lo - lon) * 111.0 * max(0.2, np.cos(np.radians((la + lat) / 2)))
        d = float(np.hypot(dx, dy))
        if d < best_d:
            best_d = d
            best = (str(row["puerto"]), la, lo, d)
    return best


def _coords_serie(nombre_puerto: str, coords: pd.DataFrame) -> tuple[float, float] | None:
    """Resuelve lat/lon de un nombre de puerto del .mat contra la lista de puertos."""
    if coords is None or coords.empty:
        return None
    clave = _normalizar(nombre_puerto)
    # Quitar prefijo "puerto" / "puertode" para emparejar mejor
    clave_corta = clave
    for pref in ("puertode", "puerto", "puertobahiade", "puertoexteriorde"):
        if clave_corta.startswith(pref) and len(clave_corta) > len(pref) + 2:
            clave_corta = clave_corta[len(pref) :]
            break
    mejores: list[tuple[int, float, float]] = []
    for _, row in coords.iterrows():
        try:
            la, lo = float(row["lat"]), float(row["lon"])
        except (TypeError, ValueError, KeyError):
            continue
        k = _normalizar(row["puerto"])
        if not k:
            continue
        if k == clave or k == clave_corta:
            return la, lo
        if k in clave or clave in k or k in clave_corta or clave_corta in k:
            # puntuacion: mayor solapamiento
            score = min(len(k), len(clave_corta))
            mejores.append((score, la, lo))
    if not mejores:
        return None
    mejores.sort(key=lambda x: -x[0])
    return mejores[0][1], mejores[0][2]


def nearest_port_index(
    series: list[SeriePuerto], lat: float, lon: float, coords: pd.DataFrame
) -> int | None:
    """Indice de la serie del .mat geograficamente mas cercana a (lat, lon)."""
    if not series:
        return None
    best_i = None
    best_d = float("inf")
    for i, s in enumerate(series):
        xy = _coords_serie(s.puerto, coords)
        if xy is None:
            continue
        la, lo = xy
        dy = (la - lat) * 111.0
        dx = (lo - lon) * 111.0 * max(0.2, np.cos(np.radians((la + lat) / 2)))
        d = float(np.hypot(dx, dy))
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def describir_punto_cercano(
    impacto: ImpactoCargado,
    lat: float,
    lon: float,
    coords: pd.DataFrame,
) -> dict[str, Any]:
    """Metadatos del punto/puerto usado para muestrear un impacto en (lat, lon)."""
    out: dict[str, Any] = {
        "tipo": impacto.info.tipo,
        "etiqueta": None,
        "lat": None,
        "lon": None,
        "distancia_km": None,
    }
    if impacto.series_puerto:
        idx = nearest_port_index(impacto.series_puerto, lat, lon, coords)
        if idx is None:
            return out
        s = impacto.series_puerto[idx]
        xy = _coords_serie(s.puerto, coords)
        out["etiqueta"] = s.puerto
        if xy is not None:
            out["lat"], out["lon"] = xy
            dy = (xy[0] - lat) * 111.0
            dx = (xy[1] - lon) * 111.0 * max(0.2, np.cos(np.radians((xy[0] + lat) / 2)))
            out["distancia_km"] = float(np.hypot(dx, dy))
        return out
    if impacto.campos_espaciales:
        campo = impacto.campos_espaciales[0]
        ij = sample_espacial(campo, lat, lon)
        if ij is None:
            return out
        f, c = ij
        la = float(campo.lat[f, c])
        lo = float(campo.lon[f, c])
        dy = (la - lat) * 111.0
        dx = (lo - lon) * 111.0 * max(0.2, np.cos(np.radians((la + lat) / 2)))
        out["etiqueta"] = campo.puerto or f"celda ({f}, {c})"
        out["lat"] = la
        out["lon"] = lo
        out["distancia_km"] = float(np.hypot(dx, dy))
    return out


def sample_espacial(campo: CampoEspacial, lat: float, lon: float) -> tuple[int, int] | None:
    """Indices (fila, col) de la celda mas cercana a lat/lon."""
    dist = (campo.lat - lat) ** 2 + (campo.lon - lon) ** 2
    if not np.isfinite(dist).any():
        return None
    idx = int(np.nanargmin(dist))
    return np.unravel_index(idx, dist.shape)  # type: ignore[return-value]


def valor_en_celda(
    campo: CampoEspacial,
    fila: int,
    col: int,
    *,
    periodo: int | None,
    escenario_idx: int,
) -> float | None:
    if periodo is None:
        arr = campo.baseline
    else:
        if campo.proyecciones.size == 0:
            return None
        if periodo >= campo.proyecciones.shape[0] or escenario_idx >= campo.proyecciones.shape[1]:
            return None
        arr = campo.proyecciones[periodo, escenario_idx]
        if not isinstance(arr, np.ndarray):
            return _a_float_o_none(arr)
    try:
        v = float(np.asarray(arr)[fila, col])
        return v if np.isfinite(v) else None
    except Exception:
        return None


def tabla_indicadores_localizacion(
    impactos: list[ImpactoCargado],
    *,
    lat: float,
    lon: float,
    coords_puertos: pd.DataFrame,
    percentiles: tuple[str, ...] = PERCENTILES_UI,
) -> pd.DataFrame:
    """Tabla tipo referencia: filas indicador(+percentil), columnas historico/periodos x escenarios.

    Si no hay dimension de percentil en los datos, las filas de percentil muestran ``-``
    excepto la primera (P50), que muestra el valor disponible.
    """
    filas: list[dict[str, Any]] = []
    # Descubrir columnas globales
    periodos: list[int] = []
    escenarios: list[str] = []
    for imp in impactos:
        for c in imp.centros:
            if c not in periodos:
                periodos.append(c)
        for e in imp.escenarios:
            if e not in escenarios:
                escenarios.append(e)
        for s in imp.series_puerto:
            for c in s.centros:
                if c not in periodos:
                    periodos.append(c)
            for e in s.escenarios:
                if e not in escenarios:
                    escenarios.append(e)
        for campo in imp.campos_espaciales:
            for c in campo.centros:
                if c not in periodos:
                    periodos.append(c)
            for e in campo.escenarios:
                if e not in escenarios:
                    escenarios.append(e)
    periodos = sorted(periodos)
    if not escenarios:
        escenarios = list(ESCENARIOS_DEFAULT)

    col_order = ["Indicador", "Percentil", "Hist\u00f3rico"]
    for p in periodos:
        for e in escenarios:
            col_order.append(f"{p} / {e}")

    for imp in impactos:
        nombre = f"{imp.info.driver_label} - {etiqueta_impacto(imp.info.impacto_id)}"
        valores_base: dict[str, Any] = {c: MISSING for c in col_order}
        valores_base["Indicador"] = nombre

        # Preferir serie de puerto si existe; si no, muestrear rejilla
        valor_hist: float | None = None
        vals_proy: dict[str, float | None] = {}

        if imp.series_puerto:
            idx = nearest_port_index(imp.series_puerto, lat, lon, coords_puertos)
            if idx is not None:
                serie = imp.series_puerto[idx]
                valor_hist = serie.baseline
                for pi, year in enumerate(serie.centros):
                    for ei, esc in enumerate(serie.escenarios):
                        key = f"{year} / {esc}"
                        try:
                            vals_proy[key] = float(serie.proyecciones[pi, ei])
                        except Exception:
                            vals_proy[key] = None
        elif imp.campos_espaciales:
            campo = imp.campos_espaciales[0]
            ij = sample_espacial(campo, lat, lon)
            if ij is not None:
                f, c = ij
                valor_hist = valor_en_celda(campo, f, c, periodo=None, escenario_idx=0)
                for pi, year in enumerate(campo.centros):
                    for ei, esc in enumerate(campo.escenarios):
                        key = f"{year} / {esc}"
                        vals_proy[key] = valor_en_celda(campo, f, c, periodo=pi, escenario_idx=ei)

        for pi, perc in enumerate(percentiles):
            row = dict(valores_base)
            row["Percentil"] = perc
            # Solo el primer percentil muestra datos reales (no hay dimension en .mat)
            if pi == 0:
                row["Hist\u00f3rico"] = fmt_valor(valor_hist)
                for k, v in vals_proy.items():
                    if k in row:
                        row[k] = fmt_valor(v)
            filas.append(row)

        if not percentiles:
            row = dict(valores_base)
            row["Percentil"] = MISSING
            row["Hist\u00f3rico"] = fmt_valor(valor_hist)
            for k, v in vals_proy.items():
                if k in row:
                    row[k] = fmt_valor(v)
            filas.append(row)

    if not filas:
        return pd.DataFrame(columns=col_order)
    df = pd.DataFrame(filas)
    extras = [c for c in df.columns if c not in col_order]
    return df[col_order + extras]


def rejilla_para_mapa(
    campo: CampoEspacial,
    *,
    periodo: int | None,
    escenario_idx: int,
    max_points: int = 2500,
) -> pd.DataFrame:
    """DataFrame lat/lon/valor para HeatMap, con submuestreo si hace falta."""
    if periodo is None:
        grid = np.asarray(campo.baseline, dtype=float)
    else:
        if campo.proyecciones.size == 0:
            return pd.DataFrame(columns=["lat", "lon", "valor"])
        if periodo >= campo.proyecciones.shape[0] or escenario_idx >= campo.proyecciones.shape[1]:
            return pd.DataFrame(columns=["lat", "lon", "valor"])
        cell = campo.proyecciones[periodo, escenario_idx]
        grid = np.asarray(cell, dtype=float)

    lat = np.asarray(campo.lat, dtype=float)
    lon = np.asarray(campo.lon, dtype=float)
    mask = np.isfinite(grid) & np.isfinite(lat) & np.isfinite(lon)
    ys, xs = np.where(mask)
    if ys.size == 0:
        return pd.DataFrame(columns=["lat", "lon", "valor"])

    step = max(1, int(np.ceil(np.sqrt(ys.size / max_points))))
    ys = ys[::step]
    xs = xs[::step]
    return pd.DataFrame(
        {
            "lat": lat[ys, xs],
            "lon": lon[ys, xs],
            "valor": grid[ys, xs],
        }
    )


def valores_puertos_mapa(
    series: list[SeriePuerto],
    coords: pd.DataFrame,
    *,
    periodo: int | None,
    escenario_idx: int,
) -> pd.DataFrame:
    """Puntos puerto con valor para el visualizador."""
    filas = []
    for s in series:
        # resolver coords
        clave = _normalizar(s.puerto)
        lat = lon = None
        for _, row in coords.iterrows():
            k = _normalizar(row["puerto"])
            if k == clave or (k and k in clave) or (clave and clave in k):
                try:
                    lat, lon = float(row["lat"]), float(row["lon"])
                    break
                except (TypeError, ValueError):
                    continue
        if lat is None:
            continue
        if periodo is None:
            val = s.baseline
        else:
            try:
                val = float(s.proyecciones[periodo, escenario_idx])
            except Exception:
                val = None
        filas.append({"puerto": s.puerto, "lat": lat, "lon": lon, "valor": val})
    return pd.DataFrame(filas)


def limpiar_cache_impactos() -> None:
    cargar_impacto.cache_clear()
