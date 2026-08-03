"""Modelos de impacto.

Importaciones pesadas (calcular, metadatos) van por submódulos para evitar
ciclos con ``inputs_activo`` / ``catalogo_impactos``.
"""

from __future__ import annotations

__all__ = [
    "METADATOS",
    "ParametrosEntrada",
    "ResultadoPIAgitacion",
    "calcular",
    "percentiles_disponibles",
]


def __getattr__(name: str):
    if name in __all__:
        from core.modelos.impacto import pi_agitacion as _pi

        return getattr(_pi, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
