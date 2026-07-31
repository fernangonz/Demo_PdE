# -*- coding: utf-8 -*-
"""Mensajes concretos cuando no se encuentra un indicador climatico."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config_indicadores import ReglaIndicador
from core.fuentes_datos import fuente, nombre_archivo_display

_AB = "\u00ab"
_CB = "\u00bb"
_ARROW = "\u2192"
_GE = "\u2265"


def nombre_excel_clima(datos: object | None = None) -> str:
    """Nombre real del Excel de clima si esta en rutas; si no, el de catalogo."""
    rutas = getattr(datos, "rutas", None) or {}
    ruta = rutas.get("clima") if isinstance(rutas, dict) else None
    if ruta:
        return Path(str(ruta)).name
    try:
        return nombre_archivo_display(fuente("clima"))
    except KeyError:
        return "Indicadores_climaticos.xlsx"


def _etiqueta_clima_fallback() -> str:
    try:
        return nombre_archivo_display(fuente("clima"))
    except KeyError:
        return "Indicadores_climaticos.xlsx"


def conteos_busqueda_indicador(
    df_clima: pd.DataFrame | None,
    *,
    percentil: str | None = None,
) -> tuple[int, int | None]:
    """(filas en hoja, filas tras filtro de percentil o None si no aplica)."""
    if df_clima is None or df_clima.empty:
        return 0, None
    n_hoja = len(df_clima)
    if percentil and "Percentil" in df_clima.columns:
        mask = (
            df_clima["Percentil"].astype(str).str.strip().str.upper()
            == str(percentil).strip().upper()
        )
        if mask.any():
            return n_hoja, int(mask.sum())
    return n_hoja, None


def mensaje_indicador_no_encontrado(
    *,
    hoja: str,
    percentil: str,
    patron: str,
    modo_seleccion: str,
    archivo: str | None = None,
    variable: str | None = None,
    n_filas_hoja: int | None = None,
    n_tras_percentil: int | None = None,
    n_candidatos: int | None = None,
    detalle_filtro: str | None = None,
) -> str:
    """Texto de Motivo: donde se busco el indicador y que filtros fallaron."""
    excel = archivo or _etiqueta_clima_fallback()
    partes = [
        f"No se encontr\u00f3 el indicador {_AB}{patron}{_CB}.",
        f"B\u00fasqueda en {excel}, hoja {_AB}{hoja}{_CB}.",
    ]
    filtros: list[str] = [f"percentil {percentil}", f"selecci\u00f3n {modo_seleccion}"]
    if variable and variable.strip().lower() != str(hoja).strip().lower():
        filtros.append(f"variable {variable}")
    if detalle_filtro:
        filtros.append(detalle_filtro)
    partes.append("Filtros: " + "; ".join(filtros) + ".")

    conteos: list[str] = []
    if n_filas_hoja is not None:
        conteos.append(f"{n_filas_hoja} filas en la hoja")
    if n_tras_percentil is not None:
        conteos.append(f"{n_tras_percentil} tras percentil {percentil}")
    if n_candidatos is not None:
        conteos.append(f"{n_candidatos} candidatas tras el filtro de nombre/umbral")
    if conteos:
        partes.append("Candidatas: " + f" {_ARROW} ".join(conteos) + ".")
    elif n_filas_hoja == 0:
        partes.append("La hoja estaba vac\u00eda o no existe en el Excel cargado.")
    return " ".join(partes)


def modo_seleccion_desde_regla(
    regla: ReglaIndicador | None,
    *,
    inundacion_fb: bool = False,
    origen_referencia: str = "",
) -> str:
    if regla and regla.usa_predefinido:
        return f"predefinido {_AB}{regla.indicador}{_CB}"
    if inundacion_fb:
        if origen_referencia == "Fb" or origen_referencia.startswith("Fb"):
            return "Fb / inundaci\u00f3n costera en atraque"
        if origen_referencia.startswith("umbral"):
            return "umbral (Fb vac\u00edo) / inundaci\u00f3n costera en atraque"
        return "inundaci\u00f3n costera en atraque"
    return "por umbral"


def patron_busqueda_indicador(
    *,
    regla: ReglaIndicador | None,
    umbral_txt: str = "",
    umbral_m: float | None = None,
    inundacion_fb: bool = False,
    referencia_m: float | None = None,
    variable: str = "",
) -> str:
    if regla and regla.usa_predefinido and regla.indicador:
        return regla.indicador
    if inundacion_fb:
        ref = referencia_m if referencia_m is not None else umbral_m
        if ref is not None:
            return f"inundaci\u00f3n costera en un atraque {_GE} {ref:g} m"
        return "inundaci\u00f3n costera en un atraque"
    if umbral_txt:
        return umbral_txt
    if umbral_m is not None:
        return f"umbral {umbral_m:g} ({variable or 'variable'})"
    return f"indicador de {variable or 'clima'}"


__all__ = [
    "conteos_busqueda_indicador",
    "mensaje_indicador_no_encontrado",
    "modo_seleccion_desde_regla",
    "nombre_excel_clima",
    "patron_busqueda_indicador",
]
