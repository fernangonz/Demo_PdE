"""Modelos económicos (independientes del resto)."""

from core.modelos.economico.legacy import (
    ColumnaEscenario,
    resultado_acumulado,
    resultado_equivalente_anual,
    revenue_descont,
)
from core.modelos.economico.schemas import ParametrosEconomicos, ResultadoEconomico

__all__ = [
    "ColumnaEscenario",
    "ParametrosEconomicos",
    "ResultadoEconomico",
    "revenue_descont",
    "resultado_acumulado",
    "resultado_equivalente_anual",
]
