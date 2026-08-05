# -*- coding: utf-8 -*-
"""Esquemas del modelo PI_PRECIPITACION (exceso de precipitación / ELO)."""

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

MODELO_ID = "PI_PRECIPITACION"
MODELO_VERSION = "1.0.0"
MODO_FALLO_DEFAULT = "Exceso de precipitación"
VARIABLE_DEFAULT = "Precipitación"
NUM_INDICADORES_REQUERIDOS = 2

COL_INCREMENTO_1 = "Incremento ind. 1"
COL_ANALISIS_1 = "Análisis ind. 1"
COL_INCREMENTO_2 = "Incremento ind. 2"
COL_ANALISIS_2 = "Análisis ind. 2"
ANALISIS_INCREMENTA = "INCREMENTA"
ANALISIS_NO = "NO"

METADATOS = MetadatosModelo(
    id=MODELO_ID,
    nombre="PI EXCESO DE PRECIPITACIÓN",
    version=MODELO_VERSION,
    categoria="impacto",
    descripcion=(
        "Misma cadena procedural que PI superación de umbral, sin búsqueda de umbral: "
        "dos indicadores predefinidos desde Excel 4; incremento futuro ? histórico "
        "por indicador con análisis INCREMENTA / NO."
    ),
)


class ResultadoPIPrecipitacion(ResultadoPIAgitacion):
    """Resultado del motor PI_PRECIPITACION."""

    @classmethod
    def error(cls, mensaje: str) -> ResultadoPIPrecipitacion:
        return cls(metadatos=METADATOS, ok=False, error=mensaje)

    @classmethod
    def desde_calculo(
        cls,
        *,
        metadatos_ejecucion: dict[str, Any],
        iteraciones: list[IteracionResultado],
        resultados_por_pasos=None,
    ) -> ResultadoPIPrecipitacion:
        if not iteraciones:
            return cls.error("No se generó ninguna iteración.")

        ok_iters = [it for it in iteraciones if (it.estado or "ok") == "ok"]
        err_msgs = [
            (f"{it.modo_fallo}: {it.motivo}" if it.motivo else it.modo_fallo)
            for it in iteraciones
            if (it.estado or "ok") == "error"
        ]
        primera = ok_iters[0] if ok_iters else iteraciones[0]
        advertencias = [adv for it in iteraciones for adv in it.advertencias]
        for msg in err_msgs:
            if msg and msg not in advertencias:
                advertencias.append(msg)
        tablas = {
            f"resultado_escenarios_iter_{it.numero}": dataframe_a_registros(it.tabla_resultado)
            for it in iteraciones
            if not it.tabla_resultado.empty
        }
        sintesis = primera.sintesis_cambios or SintesisCambios()
        ok = bool(ok_iters)
        error = None if ok else (err_msgs[0] if err_msgs else "Ningún modo pudo calcularse.")

        return cls(
            metadatos=METADATOS,
            ok=ok,
            error=error,
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
    "ANALISIS_INCREMENTA",
    "ANALISIS_NO",
    "BASELINE_YEAR",
    "COL_ANALISIS_1",
    "COL_ANALISIS_2",
    "COL_INCREMENTO_1",
    "COL_INCREMENTO_2",
    "IteracionResultado",
    "METADATOS",
    "MODELO_ID",
    "MODELO_VERSION",
    "MODO_FALLO_DEFAULT",
    "NUM_INDICADORES_REQUERIDOS",
    "ParametrosEntrada",
    "ResultadoPIPrecipitacion",
    "SintesisCambios",
    "VARIABLE_DEFAULT",
]
