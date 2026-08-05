# -*- coding: utf-8 -*-
"""Pasos auditables del motor PI_PRECIPITACION."""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.modelos.impacto.pi_agitacion.pasos import PasoResultado, TablaPaso
from core.modelos.impacto.pi_agitacion.utilidades import ColumnaEscenario
from core.modelos.impacto.pi_precipitacion.schemas import PREF_CAMBIO, PREF_INTERP
from core.relacion_modelos import IndicadorRelacion


def construir_pasos_precipitacion(
    *,
    numero_iteracion: int,
    tipo_uo: str,
    activo_raw: str,
    modo_fallo: str,
    variable: str,
    percentil: str,
    origen_regla: str,
    fila_excel: int | None,
    indicadores: tuple[IndicadorRelacion, ...],
    pestana_clima: str,
    col_hist: ColumnaEscenario,
    columnas_fut: list[ColumnaEscenario],
    tabla_variacion: pd.DataFrame,
) -> list[PasoResultado]:
    """Pasos 5-8: sin umbral; 1 o 2 indicadores predefinidos y sus cambios."""
    pasos: list[PasoResultado] = []

    pasos.append(PasoResultado(
        numero=5,
        nombre=f"Iteracion por Modos de fallo (IM={numero_iteracion})",
        excel="Relacion umbrales y curvas de dano vs activos / ListRelacion impactos-indicador",
        tablas=[TablaPaso(
            titulo="Input",
            columnas=["Modos de fallo / Modos de parada"],
            filas=[{"Modos de fallo / Modos de parada": modo_fallo}],
        )],
        procedimiento=(
            "Exceso de precipitacion: mismos pasos que PI superacion de umbral, "
            "sin busqueda de umbral; indicadores predefinidos (Excel 4)."
        ),
    ))

    filas_5b: list[dict[str, Any]] = [
        {
            "Campo": "Origen de la regla",
            "Valor": (
                "Excel (Relacion_modelos_activos_e_indicadores)"
                if origen_regla == "excel"
                else "Diagrama"
            ),
        },
        {"Campo": "Percentil", "Valor": percentil.upper()},
        {"Campo": "Seleccion indicador", "Valor": "Predefinido"},
        {"Campo": "No indicadores", "Valor": len(indicadores)},
        {"Campo": "Umbral", "Valor": "No aplica (omitido)"},
    ]
    if fila_excel is not None:
        filas_5b.append({"Campo": "Fila Excel", "Valor": fila_excel})
    for i, ind in enumerate(indicadores, start=1):
        filas_5b.append({"Campo": f"Indicador {i}", "Valor": ind.indicador})
        if ind.etiqueta:
            filas_5b.append({"Campo": f"Etiqueta {i}", "Valor": ind.etiqueta})
        pest = getattr(ind, "pesta\u00f1a", None) or getattr(ind, "pestana", None) or ""
        if pest:
            filas_5b.append({"Campo": f"Pestana {i}", "Valor": pest})

    pasos.append(PasoResultado(
        numero=5,
        nombre="5b. Regla en Relacion_modelos_activos_e_indicadores",
        excel="Relacion_modelos_activos_e_indicadores",
        tablas=[
            TablaPaso(
                titulo="Input",
                columnas=[
                    "Activo fisico u Operacional",
                    "Modos de fallo / Modos de parada",
                    "Variable",
                    "Tipo UO",
                ],
                filas=[{
                    "Activo fisico u Operacional": activo_raw,
                    "Modos de fallo / Modos de parada": modo_fallo,
                    "Variable": variable,
                    "Tipo UO": tipo_uo,
                }],
            ),
            TablaPaso(
                titulo="Output",
                columnas=["Campo", "Valor"],
                filas=filas_5b,
            ),
        ],
        procedimiento="Paso 5b: percentil e indicadores predefinidos desde Excel 4.",
    ))

    pasos.append(PasoResultado(
        numero=6,
        nombre="Obtener umbral (omitido)",
        excel="\u2014",
        tablas=[TablaPaso(
            titulo="Nota",
            columnas=["Campo", "Valor"],
            filas=[{
                "Campo": "Umbral",
                "Valor": "Omitido: no existe umbral a buscar para precipitacion.",
            }],
        )],
        procedimiento="Paso 6/7 por umbral omitido; se usan indicadores predefinidos.",
    ))

    filas_sel = []
    for i, ind in enumerate(indicadores, start=1):
        pest = getattr(ind, "pesta\u00f1a", None) or getattr(ind, "pestana", None) or ""
        filas_sel.append({
            "N": i,
            "Indicador": ind.indicador,
            "Etiqueta": ind.etiqueta or ind.indicador,
            "Pestana clima": pest or pestana_clima,
        })
    pasos.append(PasoResultado(
        numero=7,
        nombre="Seleccionar indicadores predefinidos",
        excel=f"Indicadores climaticos / hoja {pestana_clima}",
        tablas=[TablaPaso(
            titulo="Output",
            columnas=["N", "Indicador", "Etiqueta", "Pestana clima"],
            filas=filas_sel,
        )],
        procedimiento=(
            f"Se seleccionan {len(indicadores)} indicadores predefinidos "
            f"(hoja {pestana_clima}, percentil {percentil})."
        ),
    ))

    cols_out = ["Escenario"] + [
        str(c)
        for c in tabla_variacion.columns
        if str(c) != "Escenario"
        and (
            str(c).startswith(PREF_CAMBIO)
            or str(c).startswith(PREF_INTERP)
            or str(c).startswith("Interpretacion")
        )
    ]
    filas_out: list[dict[str, Any]] = []
    for _, row in tabla_variacion.iterrows():
        filas_out.append({c: row.get(c) for c in cols_out if c in tabla_variacion.columns})

    n_inds = len(indicadores)
    pasos.append(PasoResultado(
        numero=8,
        nombre=f"Cambio futuro vs historico ({n_inds} indicador{'es' if n_inds != 1 else ''})",
        excel=f"Indicadores climaticos / hoja {pestana_clima}",
        tablas=[TablaPaso(
            titulo="Output",
            columnas=[c for c in cols_out if c in tabla_variacion.columns],
            filas=filas_out,
        )],
        procedimiento=(
            "Por cada indicador: delta = valor escenario - historico; "
            "Interpretacion = no mejora si delta > 0, Mejora si delta < 0, "
            "Sin cambios si delta = 0 (misma polaridad que PI agitacion). "
            f"Referencia historica: {col_hist.etiqueta}; "
            f"{len(columnas_fut)} escenarios futuros; "
            f"{n_inds} par(es) Cambio/Interpretacion."
        ),
    ))
    return pasos
