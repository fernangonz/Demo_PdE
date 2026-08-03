"""Modelo PI_AGITACION — módulo independiente.

Reexporta ``calcular`` como **función** (no el submódulo ``calcular.py``).
``from package import calcular`` resolvería el submódulo si no se enlaza aquí.
"""

from __future__ import annotations

from core.modelos.impacto.pi_agitacion.calcular import calcular
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
