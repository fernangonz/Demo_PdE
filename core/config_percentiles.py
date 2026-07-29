"""Lectura de percentiles por defecto desde ``config/percentiles.json``.

El archivo se relee en cada llamada (sin caché) para que un cambio surta efecto
en la siguiente ejecución del modelo.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_CONFIG_PERCENTILES = RAIZ_PROYECTO / "config" / "percentiles.json"

_FALLBACK = {
    "global": {"percentil_por_defecto": "P99"},
    "variables_climaticas": {"Oleaje": "P99", "Viento": "P99"},
    "estados_limite": {"ELO": "P99", "ELS": "P99", "ELU": "P99"},
    "modelos": {
        "PI_AGITACION": {
            "percentil_por_defecto": "P99",
            "variables": {"Oleaje": "P99", "Viento": "P99"},
        }
    },
}


def ruta_config_percentiles() -> Path:
    """Ruta absoluta del JSON editable por el usuario."""
    return RUTA_CONFIG_PERCENTILES


def normalizar_percentil(valor: object, *, fallback: str = "P99") -> str:
    texto = str(valor or "").strip().upper()
    if not texto:
        return fallback
    if texto.startswith("P") and texto[1:].isdigit():
        return texto
    if texto.isdigit():
        return f"P{texto}"
    return fallback


def _clave_normalizada(texto: object) -> str:
    import unicodedata

    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    return "".join(c for c in t if c.isalnum())


def _buscar_en_mapa(mapa: dict[str, Any], clave: str) -> str | None:
    if not mapa or not clave:
        return None
    if clave in mapa:
        return normalizar_percentil(mapa[clave])
    clave_n = _clave_normalizada(clave)
    for k, v in mapa.items():
        if str(k).startswith("_"):
            continue
        if _clave_normalizada(k) == clave_n:
            return normalizar_percentil(v)
    return None


def cargar_config_percentiles(*, forzar_lectura: bool = True) -> dict[str, Any]:
    """Carga el JSON de percentiles desde disco.

    ``forzar_lectura`` se mantiene por compatibilidad; siempre se lee el archivo.
    """
    _ = forzar_lectura
    ruta = ruta_config_percentiles()
    if not ruta.is_file():
        return dict(_FALLBACK)
    try:
        with ruta.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return dict(_FALLBACK)
        return data
    except (OSError, json.JSONDecodeError):
        return dict(_FALLBACK)


def percentil_global(config: dict[str, Any] | None = None) -> str:
    cfg = config or cargar_config_percentiles()
    global_cfg = cfg.get("global") or {}
    return normalizar_percentil(global_cfg.get("percentil_por_defecto", "P99"))


def percentil_por_defecto_modelo(modelo_id: str, config: dict[str, Any] | None = None) -> str:
    """Percentil por defecto del selector UI de un modelo."""
    cfg = config or cargar_config_percentiles()
    modelos = cfg.get("modelos") or {}
    modelo = modelos.get(modelo_id) or {}
    if isinstance(modelo, dict):
        pct = _buscar_en_mapa(modelo, "percentil_por_defecto")
        if pct:
            return pct
    return percentil_global(cfg)


def percentil_para_calculo(
    *,
    modelo_id: str,
    variable: str | None = None,
    estado_limite: str | None = None,
    override: str | None = None,
    config: dict[str, Any] | None = None,
) -> str:
    """Resuelve el percentil a usar en un cálculo.

    Prioridad:
    1. ``override`` (p. ej. valor elegido en la UI)
    2. ``modelos[modelo_id].variables[variable]``
    3. ``variables_climaticas[variable]``
    4. ``estados_limite[estado_limite]``
    5. ``modelos[modelo_id].percentil_por_defecto``
    6. ``global.percentil_por_defecto``
    """
    if override:
        return normalizar_percentil(override)

    cfg = config or cargar_config_percentiles()
    modelos = cfg.get("modelos") or {}
    modelo = modelos.get(modelo_id) or {}
    if not isinstance(modelo, dict):
        modelo = {}

    if variable:
        pct = _buscar_en_mapa(modelo.get("variables") or {}, variable)
        if pct:
            return pct
        pct = _buscar_en_mapa(cfg.get("variables_climaticas") or {}, variable)
        if pct:
            return pct

    if estado_limite:
        pct = _buscar_en_mapa(cfg.get("estados_limite") or {}, estado_limite)
        if pct:
            return pct

    pct = _buscar_en_mapa(modelo, "percentil_por_defecto")
    if pct:
        return pct

    return percentil_global(cfg)


def resumen_config_percentiles(config: dict[str, Any] | None = None) -> dict[str, str]:
    """Metadatos breves para mostrar en la UI."""
    cfg = config or cargar_config_percentiles()
    ruta = ruta_config_percentiles()
    return {
        "ruta": str(ruta),
        "existe": str(ruta.is_file()),
        "global": percentil_global(cfg),
        "pi_agitacion": percentil_por_defecto_modelo("PI_AGITACION", cfg),
    }
