"""Esquemas del modelo de falta de calado (OPEX ELS y CAPEX ELU)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from core.modelos.impacto.pi_agitacion.schemas import IndicadorEvaluado, IteracionResultado, SintesisCambios
from core.modelos.impacto.pi_agitacion.utilidades import match_texto
from core.schemas.base import MetadatosModelo, ResultadoModelo
from core.schemas.serializacion import dataframe_a_registros

MODELO_ID_ELS = "PI_CALADO_ELS"
MODELO_ID_ELU = "PI_CALADO_ELU"
MODELO_ID = MODELO_ID_ELS
MODELO_VERSION = "1.0.0"
MODO_FALLO_DEFAULT = "Falta de Calado"
VARIABLE_DEFAULT = "Nivel del mar"

METADATOS_ELS = MetadatosModelo(
    id=MODELO_ID_ELS,
    nombre="OPEX falta de calado",
    version=MODELO_VERSION,
    categoria="impacto",
    descripcion=(
        "Calcula h = NM - h0 - h sedimentacion por escenario, compara con umbral "
        "(p. ej. 1,5*Dc + 0,75). Solo filas IM con tipo de impacto ELO (OPEX)."
    ),
)

METADATOS_ELU = MetadatosModelo(
    id=MODELO_ID_ELU,
    nombre="CAPEX falta de calado",
    version=MODELO_VERSION,
    categoria="impacto",
    descripcion=(
        "Misma formulacion h = NM - h0 - h sedimentacion. Solo filas IM con "
        "tipo de impacto ELS (CAPEX); sin mezclar reglas con OPEX/ELO."
    ),
)

METADATOS = METADATOS_ELS


def metadatos_para_tipo_impacto(tipo_impacto: str) -> MetadatosModelo:
    """OPEX (PI_CALADO_ELS) solo ELO; CAPEX (PI_CALADO_ELU) solo ELS."""
    if match_texto(tipo_impacto, "ELS"):
        return METADATOS_ELU
    return METADATOS_ELS


def modelo_id_para_tipo_impacto(tipo_impacto: str) -> str:
    if match_texto(tipo_impacto, "ELS"):
        return MODELO_ID_ELU
    return MODELO_ID_ELS


def nombre_modelo_para_tipo_impacto(tipo_impacto: str) -> str:
    return metadatos_para_tipo_impacto(tipo_impacto).nombre


@dataclass
class ParametrosEntrada:
    """Parámetros del activo para falta de calado."""

    tipo_uo: str | None = None
    activo: str | None = None
    calado_buque: float | None = None
    baseline_year: int = 2005
    tipo_impacto: str = "ELO"

    @property
    def modelo_id(self) -> str:
        return modelo_id_para_tipo_impacto(self.tipo_impacto)


@dataclass
class ResultadoPICalado(ResultadoModelo):
    """Salida del modelo de falta de calado (OPEX o CAPEX)."""

    iteraciones: list[IteracionResultado] = field(default_factory=list)
    resultados_por_pasos: Any = None
    hsedimentacion_historico: float | None = None

    @classmethod
    def error(
        cls,
        mensaje: str,
        *,
        metadatos: MetadatosModelo | None = None,
    ) -> ResultadoPICalado:
        return cls(metadatos=metadatos or METADATOS_ELS, ok=False, error=mensaje)

    @classmethod
    def desde_calculo(
        cls,
        *,
        metadatos: MetadatosModelo,
        metadatos_ejecucion: dict[str, Any],
        iteraciones: list[IteracionResultado],
        resultados_por_pasos=None,
        hsedimentacion_historico: float | None = None,
    ) -> ResultadoPICalado:
        if not iteraciones:
            return cls.error("No se generó ninguna iteración de falta de calado.", metadatos=metadatos)

        tablas = {
            f"resultado_calado_iter_{it.numero}": dataframe_a_registros(it.tabla_resultado)
            for it in iteraciones
        }
        advertencias = [adv for it in iteraciones for adv in it.advertencias]

        return cls(
            metadatos=metadatos,
            ok=True,
            advertencias=advertencias,
            metadatos_ejecucion=metadatos_ejecucion,
            tablas=tablas,
            iteraciones=iteraciones,
            resultados_por_pasos=resultados_por_pasos,
            hsedimentacion_historico=hsedimentacion_historico,
        )
