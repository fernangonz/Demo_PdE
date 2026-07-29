# -*- coding: utf-8 -*-
"""Utilidades del modelo PI_FRANCOBORDO (falta de francobordo / ELO)."""

from __future__ import annotations

import re

import pandas as pd

from core.config_indicadores import ReglaIndicador
from core.data_loader import _normalizar
from core.modelos.impacto.pi_agitacion.schemas import IndicadorEvaluado
from core.modelos.impacto.pi_agitacion.utilidades import (
    _buscar_fila_umbral,
    _clasificar_indicadores_predefinido,
    _resultado_umbral_fila,
    buscar_umbral_umbrales,
    es_tipo_impacto_pi_operacional,
    hoja_umbrales_variable,
    resolver_umbral_lista_master,
)

_PATRON_NUMERICO = re.compile(r"(\d+[.,]\d+|\d+)")


def es_modo_falta_francobordo(
    modo: object,
    variable: object,
    tipo_impacto: object | None = None,
) -> bool:
    """Modos PI falta de francobordo (ELO + Nivel del mar)."""
    modo_n = _normalizar(modo)
    if "francobordo" not in modo_n:
        return False
    var_n = _normalizar(variable)
    if var_n not in ("nivel del mar", "calado"):
        return False
    if tipo_impacto is not None and not es_tipo_impacto_pi_operacional(tipo_impacto):
        return False
    return True


def modos_falta_francobordo(impactos: pd.DataFrame) -> list[pd.Series]:
    """Filas IM de falta de francobordo para el activo actual."""
    filas: list[pd.Series] = []
    for _, row in impactos.iterrows():
        if es_modo_falta_francobordo(
            row.get("Modos de fallo / Modos de parada"),
            row.get("Variable"),
            row.get("Tipo de impacto"),
        ):
            filas.append(row)
    return filas


def es_indicador_inundacion_atraque(texto: str) -> bool:
    n = _normalizar(texto)
    return "inundacion" in n and "costera" in n and "atraque" in n


def extraer_valor_numerico_indicador(texto: str) -> float | None:
    """Extrae el valor numerico asociado al indicador (p. ej. 0,35 en el nombre)."""
    if not texto:
        return None
    candidatos: list[float] = []
    for match in _PATRON_NUMERICO.finditer(texto):
        fragmento = match.group(1).replace(",", ".")
        try:
            valor = float(fragmento)
        except ValueError:
            continue
        if 0 <= valor <= 10:
            candidatos.append(valor)
    if not candidatos:
        return None
    return max(candidatos)


def hoja_umbrales_francobordo(por_hoja: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    for nombre, df in por_hoja.items():
        if "francobordo" in _normalizar(nombre):
            return df
    return hoja_umbrales_variable(por_hoja, "Nivel del mar")


def buscar_umbral_francobordo(
    por_hoja: dict[str, pd.DataFrame],
    *,
    n_relacion: int | None,
    tipo_uo: str,
    activo: str,
    modo_fallo: str,
    variable: str,
    tipo_impacto: str | None = None,
    tipo_activo_servicio: str | None = None,
    lista_master: pd.DataFrame | None = None,
) -> tuple[str, float | None] | None:
    """Umbral para francobordo: hoja especifica si existe, si no la de calado/NM."""
    if lista_master is not None and not lista_master.empty:
        resultado = resolver_umbral_lista_master(
            lista_master,
            n_relacion=n_relacion,
            tipo_uo=tipo_uo,
            activo=activo,
            modo_fallo=modo_fallo,
            variable=variable,
            tipo_impacto=tipo_impacto,
            tipo_activo_servicio=tipo_activo_servicio,
        )
        if resultado is not None:
            return resultado

    hoja = hoja_umbrales_francobordo(por_hoja)
    if hoja is not None and not hoja.empty:
        fila = _buscar_fila_umbral(
            hoja,
            n_relacion=n_relacion,
            activo=activo,
            modo_fallo=modo_fallo,
            variable=variable,
            tipo_impacto=tipo_impacto,
            tipo_activo_servicio=tipo_activo_servicio,
        )
        if fila is not None:
            resultado = _resultado_umbral_fila(
                fila,
                hoja,
                tipo_uo=tipo_uo,
                activo=activo,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=tipo_impacto,
                tipo_activo_servicio=tipo_activo_servicio,
                n_relacion=n_relacion,
                lista_master=lista_master,
            )
            if resultado is not None:
                return resultado

    return buscar_umbral_umbrales(
        por_hoja,
        n_relacion=n_relacion,
        tipo_uo=tipo_uo,
        activo=activo,
        modo_fallo=modo_fallo,
        variable=variable,
        tipo_impacto=tipo_impacto,
        tipo_activo_servicio=tipo_activo_servicio,
        lista_master=lista_master,
    )


def _etiqueta_indicador_francobordo(referencia: float | None) -> str:
    if referencia is None:
        return "Inundacion costera en un atraque"
    return f"Inundacion costera en un atraque >= {referencia:g} m"


def clasificar_indicadores_francobordo(
    df_clima: pd.DataFrame,
    referencia: float | None,
    *,
    percentil: str,
    tipo_uo: str = "",
    regla: ReglaIndicador | None = None,
) -> tuple[pd.Series | None, list[IndicadorEvaluado]]:
    """Paso 7: predefinido o inundacion costera en atraque >= referencia (Fb/umbral)."""
    if df_clima.empty or "Indicador" not in df_clima.columns:
        return None, []

    regla = regla or ReglaIndicador()
    if regla.usa_predefinido:
        return _clasificar_indicadores_predefinido(
            df_clima,
            percentil=percentil,
            nombre_indicador=regla.indicador or "",
            etiqueta=regla.etiqueta_mostrar(),
        )

    if referencia is None:
        return None, []

    sub = df_clima.copy()
    if "Percentil" in sub.columns and percentil:
        mask_pct = sub["Percentil"].astype(str).str.strip().str.upper() == percentil.upper()
        if mask_pct.any():
            sub = sub[mask_pct]

    candidatos: list[tuple[float, pd.Series, str]] = []
    estados: list[IndicadorEvaluado] = []
    tipo_uo_n = _normalizar(tipo_uo)

    for _, row in sub.iterrows():
        ind = str(row.get("Indicador", "")).strip()
        if not ind or ind.lower() == "nan":
            continue
        if not es_indicador_inundacion_atraque(ind):
            estados.append(IndicadorEvaluado(nombre=ind[:80], seleccionado=False, descartado=True))
            continue
        valor = extraer_valor_numerico_indicador(ind)
        if valor is None or valor < referencia:
            estados.append(
                IndicadorEvaluado(
                    nombre=ind[:80],
                    seleccionado=False,
                    descartado=True,
                )
            )
            continue
        candidatos.append((valor, row, ind))

    if not candidatos:
        estados.append(
            IndicadorEvaluado(
                nombre=_etiqueta_indicador_francobordo(referencia),
                seleccionado=False,
                descartado=True,
            )
        )
        return None, estados

    min_valor = min(v for v, _, _ in candidatos)
    empatados = [(row, ind) for v, row, ind in candidatos if abs(v - min_valor) < 1e-9]

    elegido: pd.Series | None = None
    nombre_elegido = ""
    if len(empatados) > 1 and tipo_uo_n:
        for row, ind in empatados:
            if tipo_uo_n in _normalizar(ind):
                elegido = row
                nombre_elegido = ind
                break
    if elegido is None:
        elegido, nombre_elegido = empatados[0]

    etiqueta = _etiqueta_indicador_francobordo(min_valor)
    estados.insert(0, IndicadorEvaluado(nombre=etiqueta, seleccionado=True))
    for v, _, ind in candidatos:
        if ind == nombre_elegido:
            continue
        estados.append(
            IndicadorEvaluado(
                nombre=ind[:80],
                seleccionado=False,
                descartado=(v != min_valor or ind != nombre_elegido),
            )
        )
    return elegido, estados


def variable_clima_francobordo(variable: str) -> str:
    """Pestana de indicadores climaticos para falta de francobordo."""
    var_n = _normalizar(variable)
    if var_n in ("nivel del mar", "calado"):
        return "Inundacion costera"
    return variable


def pestana_clima_francobordo(info_clima: dict, variable: str) -> tuple[pd.DataFrame, str]:
    """DataFrame climatico y nombre de pestana para francobordo."""
    pestana = variable_clima_francobordo(variable)
    por_variable = info_clima.get("por_variable", {})
    if pestana in por_variable:
        df = por_variable.get(pestana, {}).get("df", pd.DataFrame())
        return df, pestana
    df = por_variable.get(variable, {}).get("df", pd.DataFrame())
    return df, variable


__all__ = [
    "buscar_umbral_francobordo",
    "clasificar_indicadores_francobordo",
    "es_indicador_inundacion_atraque",
    "es_modo_falta_francobordo",
    "extraer_valor_numerico_indicador",
    "modos_falta_francobordo",
    "pestana_clima_francobordo",
    "variable_clima_francobordo",
]
