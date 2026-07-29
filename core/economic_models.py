"""Funciones económicas — reexporta desde ``core/modelos/economico/``."""

from core.modelos.economico.legacy import (
    ColumnaEscenario,
    resultado_acumulado,
    resultado_equivalente_anual,
    revenue_descont,
)

__all__ = [
    "ColumnaEscenario",
    "revenue_descont",
    "resultado_acumulado",
    "resultado_equivalente_anual",
]
