"""Modelos económicos — esquemas (implementación pendiente de nueva metodología)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.schemas.base import MetadatosModelo, ResultadoModelo

MODELO_INCREMENTO_ID = "INCREMENTO"
MODELO_ACUMULADO_ID = "ACUMULADO"
MODELO_EQUIVALENTE_ID = "EQUIVALENTE_ANUAL"


@dataclass
class ParametrosEconomicos:
    """Entrada genérica para modelos económicos (a definir por modelo)."""

    tasa_descuento: float = 0.03
    baseline_year: int = 2005
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResultadoEconomico(ResultadoModelo):
    """Salida de un modelo económico."""

    @classmethod
    def pendiente(cls, metadatos: MetadatosModelo) -> ResultadoEconomico:
        return cls(
            metadatos=metadatos,
            ok=False,
            error="Modelo económico pendiente de implementación.",
        )
