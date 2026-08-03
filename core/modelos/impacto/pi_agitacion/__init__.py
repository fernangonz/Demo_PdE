"""Modelo PI_AGITACION — módulo independiente.

Evita imports ansiosos de ``calcular`` para no ciclar con ``inputs_activo``.
"""

from __future__ import annotations

__all__ = [
    "METADATOS",
    "ParametrosEntrada",
    "ResultadoPIAgitacion",
    "SintesisCambios",
    "calcular",
    "percentiles_disponibles",
]


def __getattr__(name: str):
    if name in {"METADATOS", "ParametrosEntrada", "ResultadoPIAgitacion", "SintesisCambios"}:
        from core.modelos.impacto.pi_agitacion import schemas as _schemas

        return getattr(_schemas, name)
    if name == "calcular":
        from core.modelos.impacto.pi_agitacion.calcular import calcular as _calcular

        return _calcular
    if name == "percentiles_disponibles":
        from core.modelos.impacto.pi_agitacion.utilidades import percentiles_disponibles as _p

        return _p
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
