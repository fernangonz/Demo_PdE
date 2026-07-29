"""Contratos comunes para todos los modelos (impacto y económico)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from core.schemas.serializacion import dataclass_a_dict, dataframe_a_registros


@dataclass(frozen=True)
class MetadatosModelo:
    """Identidad estable del modelo (para registro y trazabilidad)."""

    id: str
    nombre: str
    version: str
    categoria: str  # "impacto" | "economico" | "dato"
    descripcion: str = ""


@dataclass
class ResultadoModelo:
    """Contrato base que cualquier modelo debe devolver.

    Un desarrollador externo puede consumir ``to_dict()`` sin depender de Streamlit
    ni de pandas en su capa de presentación.
    """

    metadatos: MetadatosModelo
    ok: bool = True
    error: str | None = None
    advertencias: list[str] = field(default_factory=list)
    metadatos_ejecucion: dict[str, Any] = field(default_factory=dict)
    tablas: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    sintesis: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        base = dataclass_a_dict(self)
        base["metadatos"] = dataclass_a_dict(self.metadatos)
        return base

    def to_json_ready(self) -> dict[str, Any]:
        """Alias explícito para integraciones REST/JSON."""
        return self.to_dict()

    def tabla_como_dataframe(self, nombre: str) -> pd.DataFrame:
        """Reconstruye un DataFrame desde ``tablas[nombre]``."""
        registros = self.tablas.get(nombre, [])
        return pd.DataFrame(registros) if registros else pd.DataFrame()
