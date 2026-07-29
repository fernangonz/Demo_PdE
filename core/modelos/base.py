"""Contratos base para modelos de impacto y económicos."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import pandas as pd

from core.schemas.base import MetadatosModelo, ResultadoModelo


@runtime_checkable
class ModeloImpacto(Protocol):
    """Interfaz que debe cumplir cualquier modelo de impacto."""

    METADATOS: MetadatosModelo

    def calcular(self, datos: Any, params: Any) -> ResultadoModelo: ...


@runtime_checkable
class ModeloEconomico(Protocol):
    """Interfaz para modelos económicos (incremento, acumulado, equivalente)."""

    METADATOS: MetadatosModelo

    def calcular(self, entrada: Any) -> ResultadoModelo: ...


@runtime_checkable
class CargadorDatos(Protocol):
    """Interfaz para fuentes de datos (Excel, API, BD)."""

    def info_clima(self) -> dict: ...
    def config_puerto(self) -> pd.DataFrame: ...
