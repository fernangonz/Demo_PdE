"""Esquemas y serialización — contrato entre modelos y cualquier interfaz."""

from core.schemas.base import MetadatosModelo, ResultadoModelo
from core.schemas.serializacion import (
    dataclass_a_dict,
    dataframe_a_registros,
    valor_serializable,
)

__all__ = [
    "MetadatosModelo",
    "ResultadoModelo",
    "dataclass_a_dict",
    "dataframe_a_registros",
    "valor_serializable",
]
