"""Esquemas del modelo PI_FRANCOBORDO."""

from __future__ import annotations

from typing import Any

from core.modelos.impacto.pi_agitacion.schemas import (
    BASELINE_YEAR,
    IteracionResultado,
    ParametrosEntrada,
    ResultadoPIAgitacion,
    SintesisCambios,
)
from core.schemas.base import MetadatosModelo
from core.schemas.serializacion import dataframe_a_registros

MODELO_ID = "PI_FRANCOBORDO"
MODELO_VERSION = "1.0.0"

METADATOS = MetadatosModelo(
    id=MODELO_ID,
    nombre="PI FALTA DE FRANCOBORDO",
    version=MODELO_VERSION,
    categoria="impacto",
    descripcion=(
        "Seleccion de indicador por Fb o umbral + inundacion costera en un atraque; "
        "variacion respecto al historico por escenario."
    ),
)


class ResultadoPIFrancobordo(ResultadoPIAgitacion):
    """Resultado del motor PI_FRANCOBORDO (misma estructura que PI superacion)."""

    @classmethod
    def error(cls, mensaje: str) -> ResultadoPIFrancobordo:
        return cls(metadatos=METADATOS, ok=False, error=mensaje)

    @classmethod
    def desde_calculo(
        cls,
        *,
        metadatos_ejecucion: dict[str, Any],
        iteraciones: list[IteracionResultado],
        resultados_por_pasos=None,
    ) -> ResultadoPIFrancobordo:
        if not iteraciones:
            return cls.error("No se genero ninguna iteracion.")

        primera = iteraciones[0]
        advertencias = [adv for it in iteraciones for adv in it.advertencias]
        tablas = {
            f"resultado_escenarios_iter_{it.numero}": dataframe_a_registros(it.tabla_resultado)
            for it in iteraciones
        }
        sintesis = primera.sintesis_cambios or SintesisCambios()

        return cls(
            metadatos=METADATOS,
            ok=True,
            advertencias=advertencias,
            metadatos_ejecucion=metadatos_ejecucion,
            tablas=tablas,
            sintesis={
                "mayor_empeoramiento": sintesis.mayor_empeoramiento,
                "mayor_empeoramiento_cambio": sintesis.mayor_empeoramiento_cambio,
                "mayor_mejora": sintesis.mayor_mejora,
                "mayor_mejora_cambio": sintesis.mayor_mejora_cambio,
            },
            iteraciones=iteraciones,
            indicadores_evaluados=primera.indicadores_evaluados,
            sintesis_cambios=primera.sintesis_cambios,
            resultados_por_pasos=resultados_por_pasos,
            _tabla_resultado_df=primera.tabla_resultado,
        )


__all__ = [
    "BASELINE_YEAR",
    "IteracionResultado",
    "METADATOS",
    "MODELO_ID",
    "MODELO_VERSION",
    "ParametrosEntrada",
    "ResultadoPIFrancobordo",
    "SintesisCambios",
]
