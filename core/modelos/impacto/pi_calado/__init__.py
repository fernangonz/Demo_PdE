"""Modelo de falta de calado — OPEX (ELS) y CAPEX (ELU)."""

from core.modelos.impacto.pi_calado.calcular import calcular
from core.modelos.impacto.pi_calado.schemas import (
    METADATOS,
    METADATOS_ELS,
    METADATOS_ELU,
    ParametrosEntrada,
    ResultadoPICalado,
)

__all__ = [
    "METADATOS",
    "METADATOS_ELS",
    "METADATOS_ELU",
    "ParametrosEntrada",
    "ResultadoPICalado",
    "calcular",
]
