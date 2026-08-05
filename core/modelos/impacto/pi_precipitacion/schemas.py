# -*- coding: utf-8 -*-
"""Esquemas del modelo PI_PRECIPITACION (exceso de precipitacion / ELO)."""

from __future__ import annotations

import re
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
MODELO_VERSION = "1.1.0"
MODO_FALLO_DEFAULT = "Exceso de precipitaci\u00f3n"
VARIABLE_DEFAULT = "Precipitaci\u00f3n"
NUM_INDICADORES_REQUERIDOS = 2

PREF_CAMBIO = "Cambio respecto al hist\u00f3rico"
PREF_INTERP = "Interpretaci\u00f3n"

INTERP_MEJORA = "Mejora"
INTERP_NO_MEJORA = "no mejora"
INTERP_SIN_CAMBIOS = "Sin cambios"
INTERP_REFERENCIA = "Referencia"

_RE_MM = re.compile(r"(\d+(?:[.,]\d+)?)\s*mm\b", re.IGNORECASE)


def umbral_mm_desde_indicador(nombre_indicador: str) -> str | None:
    """Extrae umbral en mm del nombre del indicador (p. ej. '>= 1 mm' -> '1 mm')."""
    texto = (nombre_indicador or "").strip()
    if not texto:
        return None
    m = _RE_MM.search(texto)
    if not m:
        return None
    raw = m.group(1).replace(",", ".")
    try:
        val = float(raw)
    except ValueError:
        return f"{m.group(1)} mm"
    if val == int(val):
        return f"{int(val)} mm"
    return f"{raw} mm"


def etiqueta_umbral_columna(nombre_indicador: str, indice: int = 1) -> str:
    return umbral_mm_desde_indicador(nombre_indicador) or f"ind. {indice}"


def col_cambio_indicador(nombre_indicador: str, indice: int = 1) -> str:
    return f"{PREF_CAMBIO} ({etiqueta_umbral_columna(nombre_indicador, indice)})"


def col_interpretacion_indicador(nombre_indicador: str, indice: int = 1) -> str:
    return f"{PREF_INTERP} ({etiqueta_umbral_columna(nombre_indicador, indice)})"


def columnas_pares_indicadores(
    nombre_ind_1: str,
    nombre_ind_2: str,
) -> tuple[str, str, str, str]:
    return (
        col_cambio_indicador(nombre_ind_1, 1),
        col_interpretacion_indicador(nombre_ind_1, 1),
        col_cambio_indicador(nombre_ind_2, 2),
        col_interpretacion_indicador(nombre_ind_2, 2),
    )


METADATOS = MetadatosModelo(
    id=MODELO_ID,
    nombre="PI EXCESO DE PRECIPITACI\u00d3N",
    version=MODELO_VERSION,
    categoria="impacto",
    descripcion=(
        "Misma cadena procedural que PI superaci\u00f3n de umbral, sin b\u00fasqueda de umbral: "
        "dos indicadores predefinidos desde Excel 4; cambio futuro \u2212 hist\u00f3rico "
        "por indicador con interpretaci\u00f3n Mejora / no mejora / Sin cambios."
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
            return cls.error("No se gener\u00f3 ninguna iteraci\u00f3n.")

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
        error = None if ok else (err_msgs[0] if err_msgs else "Ning\u00fan modo pudo calcularse.")

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
    "BASELINE_YEAR",
    "INTERP_MEJORA",
    "INTERP_NO_MEJORA",
    "INTERP_REFERENCIA",
    "INTERP_SIN_CAMBIOS",
    "IteracionResultado",
    "METADATOS",
    "MODELO_ID",
    "MODELO_VERSION",
    "MODO_FALLO_DEFAULT",
    "NUM_INDICADORES_REQUERIDOS",
    "PREF_CAMBIO",
    "PREF_INTERP",
    "ParametrosEntrada",
    "ResultadoPIPrecipitacion",
    "SintesisCambios",
    "VARIABLE_DEFAULT",
    "col_cambio_indicador",
    "col_interpretacion_indicador",
    "columnas_pares_indicadores",
    "etiqueta_umbral_columna",
    "umbral_mm_desde_indicador",
]
