"""Lectura de reglas de indicador climático desde ``config/indicadores.json``.

Algunos modelos (p. ej. PI viento ELO) no eligen indicador por umbral sino por nombre
predefinido. El archivo se relee en cada cálculo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
RUTA_CONFIG_INDICADORES = RAIZ_PROYECTO / "config" / "indicadores.json"

MODO_POR_UMBRAL = "por_umbral"
MODO_PREDEFINIDO = "predefinido"

_FALLBACK = {
    "modelos": {
        "PI_AGITACION": {
            "variables": {
                "Oleaje": {"modo_seleccion": MODO_POR_UMBRAL},
                "Viento": {
                    "modo_seleccion": MODO_PREDEFINIDO,
                    "indicador": "Número de días con vientos extremos",
                    "etiqueta": "Nº días con vientos extremos",
                },
            }
        }
    }
}


@dataclass(frozen=True)
class ReglaIndicador:
    """Cómo seleccionar el indicador climático en el paso 7."""

    modo_seleccion: str = MODO_POR_UMBRAL
    indicador: str | None = None
    etiqueta: str | None = None

    @property
    def usa_umbral(self) -> bool:
        return self.modo_seleccion == MODO_POR_UMBRAL

    @property
    def usa_predefinido(self) -> bool:
        return self.modo_seleccion == MODO_PREDEFINIDO and bool(self.indicador)

    def etiqueta_mostrar(self) -> str:
        if self.etiqueta:
            return self.etiqueta
        if self.indicador:
            return self.indicador
        return "Indicador por umbral"


def ruta_config_indicadores() -> Path:
    return RUTA_CONFIG_INDICADORES


def _clave_normalizada(texto: object) -> str:
    import unicodedata

    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii").lower()
    return "".join(c for c in t if c.isalnum())


def _coincide_clave(valor: object, clave: str) -> bool:
    if not clave or valor is None:
        return False
    return _clave_normalizada(valor) == _clave_normalizada(clave)


def _regla_desde_dict(bloque: dict[str, Any]) -> ReglaIndicador:
    modo = str(bloque.get("modo_seleccion") or MODO_POR_UMBRAL).strip().lower()
    if modo not in (MODO_POR_UMBRAL, MODO_PREDEFINIDO):
        modo = MODO_POR_UMBRAL
    indicador = bloque.get("indicador")
    etiqueta = bloque.get("etiqueta")
    return ReglaIndicador(
        modo_seleccion=modo,
        indicador=str(indicador).strip() if indicador else None,
        etiqueta=str(etiqueta).strip() if etiqueta else None,
    )


def cargar_config_indicadores(*, forzar_lectura: bool = True) -> dict[str, Any]:
    _ = forzar_lectura
    ruta = ruta_config_indicadores()
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


def _buscar_combinacion(
    combinaciones: list[Any],
    *,
    variable: str,
    estado_limite: str | None,
    modo_fallo: str | None,
) -> ReglaIndicador | None:
    mejor: ReglaIndicador | None = None
    mejor_puntos = -1

    for item in combinaciones:
        if not isinstance(item, dict):
            continue
        puntos = 0
        if variable and _coincide_clave(item.get("variable"), variable):
            puntos += 2
        elif item.get("variable"):
            continue
        if estado_limite:
            if _coincide_clave(item.get("estado_limite"), estado_limite):
                puntos += 2
            elif item.get("estado_limite"):
                continue
        if modo_fallo:
            if _coincide_clave(item.get("modo_fallo"), modo_fallo):
                puntos += 1
            elif item.get("modo_fallo"):
                continue
        if puntos > mejor_puntos:
            mejor_puntos = puntos
            mejor = _regla_desde_dict(item)

    return mejor if mejor_puntos >= 2 else None


def regla_indicador(
    *,
    modelo_id: str,
    variable: str,
    estado_limite: str | None = None,
    modo_fallo: str | None = None,
    config: dict[str, Any] | None = None,
) -> ReglaIndicador:
    """Resuelve la regla del paso 7 para un modelo / variable / estado límite.

    Prioridad:
    1. ``modelos[id].combinaciones`` (estado_limite + variable [+ modo_fallo])
    2. ``modelos[id].variables[variable]``
    3. Por defecto: ``por_umbral``
    """
    cfg = config or cargar_config_indicadores()
    modelos = cfg.get("modelos") or {}
    modelo = modelos.get(modelo_id) or {}
    if not isinstance(modelo, dict):
        return ReglaIndicador()

    combinaciones = modelo.get("combinaciones") or []
    if isinstance(combinaciones, list):
        regla = _buscar_combinacion(
            combinaciones,
            variable=variable,
            estado_limite=estado_limite,
            modo_fallo=modo_fallo,
        )
        if regla is not None:
            return regla

    variables = modelo.get("variables") or {}
    if isinstance(variables, dict):
        for clave, bloque in variables.items():
            if _coincide_clave(clave, variable) and isinstance(bloque, dict):
                return _regla_desde_dict(bloque)

    return ReglaIndicador()


def resumen_config_indicadores(
    *,
    modelo_id: str = "PI_AGITACION",
    variable: str = "Viento",
    estado_limite: str = "ELO",
    config: dict[str, Any] | None = None,
) -> dict[str, str]:
    cfg = config or cargar_config_indicadores()
    regla = regla_indicador(
        modelo_id=modelo_id,
        variable=variable,
        estado_limite=estado_limite,
        config=cfg,
    )
    ruta = ruta_config_indicadores()
    return {
        "ruta": str(ruta),
        "existe": str(ruta.is_file()),
        "modo": regla.modo_seleccion,
        "indicador": regla.indicador or "",
        "etiqueta": regla.etiqueta_mostrar(),
    }
