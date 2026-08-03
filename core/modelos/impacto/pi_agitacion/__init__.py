"""Modelo PI_AGITACION.

``calcular`` se resuelve de forma perezosa para evitar un ciclo:
``pi_agitacion.__init__`` -> ``calcular.py`` -> ``inputs_activo`` ->
``pi_agitacion.utilidades`` (que reentra en este mismo ``__init__``).

Quien necesite la función debe importarla desde ``.calcular`` (registro.py lo
hace así) o vía ``core.modelos.impacto.pi_agitacion.calcular`` (atributo lazy).
"""

from __future__ import annotations

from core.modelos.impacto.pi_agitacion.schemas import (
    METADATOS,
    ParametrosEntrada,
    ResultadoPIAgitacion,
    SintesisCambios,
)
from core.modelos.impacto.pi_agitacion.utilidades import percentiles_disponibles

__all__ = [
    "METADATOS",
    "ParametrosEntrada",
    "ResultadoPIAgitacion",
    "SintesisCambios",
    "calcular",
    "percentiles_disponibles",
]


def __getattr__(name: str):
    if name == "calcular":
        from core.modelos.impacto.pi_agitacion.calcular import calcular as _calcular

        return _calcular
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
