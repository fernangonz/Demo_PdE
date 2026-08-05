# -*- coding: utf-8 -*-
"""Registro central de metodologias de impacto e inputs requeridos por motor.

Los activos y modos de fallo se leen siempre desde Excel; aqui solo se define
que motor aplica a cada tipo de calculo y que datos necesita.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.fuentes_datos import FuenteExcel, fuente, nombre_archivo_display
from core.modelos.catalogo_impactos import (
    CATALOGO_MODOS_IMPACTO,
    MOTOR_PI_CALADO_ELO,
    MOTOR_PI_CALADO_ELS,
    MOTOR_PI_CALADO_ELU,
    MOTOR_PI_FRANCOBORDO,
    MOTOR_PI_PRECIPITACION,
    MOTOR_PI_SUPERACION,
    EntradaCatalogoImpacto,
    entrada_catalogo,
)
from core.modelos.inputs_activo import CampoInputActivo, INPUTS_CALADO_ACTIVO
from core.modelos.impacto.pi_agitacion.utilidades import es_modo_superacion_umbral, match_texto
from core.modelos.impacto.pi_calado.utilidades import es_modo_falta_calado
from core.modelos.impacto.pi_francobordo.utilidades import es_modo_falta_francobordo
from core.modelos.impacto.pi_precipitacion.utilidades import es_modo_exceso_precipitacion
from core.modelos.registro import MODELOS_IMPACTO


@dataclass(frozen=True)
class FuenteDatoRequerida:
    """Excel u hoja necesaria para un motor."""

    fuente_id: str
    hoja: str | None = None
    descripcion: str = ""


@dataclass(frozen=True)
class MetodologiaImpacto:
    """Metodologia registrada: motor, fuentes e inputs del activo."""

    motor_id: str
    nombre: str
    fuentes: tuple[FuenteDatoRequerida, ...]
    inputs_activo: tuple[CampoInputActivo, ...] = ()


def _fuente(
    fuente_id: str,
    *,
    hoja: str | None = None,
    descripcion: str = "",
) -> FuenteDatoRequerida:
    return FuenteDatoRequerida(
        fuente_id=fuente_id,
        hoja=hoja,
        descripcion=descripcion,
    )


_FUENTES_PI_SUPERACION = (
    _fuente(
        "config_puerto",
        descripcion="fila del activo (tipo UO, activo; Fb si Inundación costera)",
    ),
    _fuente(
        "relacion_ivc",
        hoja="ListRelacion impactos-indicador",
        descripcion="modos de fallo del activo",
    ),
    _fuente(
        "umbrales",
        descripcion="umbral por variable (si Fb vacío en Inundación costera)",
    ),
    _fuente(
        "relacion_modelos",
        descripcion="percentil e indicador climatico (paso 5b)",
    ),
    _fuente(
        "clima",
        descripcion=(
            "series del indicador; hoja Inundacion costera para modo Inundación costera"
        ),
    ),
)

_FUENTES_PI_CALADO = (
    _fuente("config_puerto", descripcion="fila del activo, Dc, Rc y Fb"),
    _fuente(
        "relacion_ivc",
        hoja="ListRelacion impactos-indicador",
        descripcion="modos Falta de Calado (PI ELO / OPEX ELS / CAPEX ELU)",
    ),
    _fuente(
        "umbrales",
        descripcion="umbral con formulacion Dc (p. ej. 1,5*Dc+0,75)",
    ),
    _fuente(
        "relacion_modelos",
        descripcion="tres indicadores: NM, h0 y sedimentacion",
    ),
    _fuente(
        "clima",
        hoja="Nivel del mar",
        descripcion="indicadores NM, h0 y h sedimentacion",
    ),
)

_FUENTES_PI_FRANCOBORDO = (
    _fuente("config_puerto", descripcion="fila del activo, Fb (opcional)"),
    _fuente(
        "relacion_ivc",
        hoja="ListRelacion impactos-indicador",
        descripcion="modos Falta de francobordo (ELO)",
    ),
    _fuente("umbrales", descripcion="umbral si Fb vacio"),
    _fuente(
        "relacion_modelos",
        descripcion="percentil e indicador climatico (paso 5b)",
    ),
    _fuente(
        "clima",
        hoja="Inundacion costera",
        descripcion="indicadores inundacion costera en un atraque",
    ),
)

_FUENTES_PI_PRECIPITACION = (
    _fuente(
        "config_puerto",
        descripcion="fila del activo (tipo UO, activo)",
    ),
    _fuente(
        "relacion_ivc",
        hoja="ListRelacion impactos-indicador",
        descripcion="modos Exceso de precipitación (ELO)",
    ),
    _fuente(
        "relacion_modelos",
        descripcion="percentil y 2 indicadores predefinidos (paso 5b; sin umbral)",
    ),
    _fuente(
        "clima",
        hoja="Precipitacion",
        descripcion="valores de los 2 indicadores predefinidos",
    ),
)

METODOLOGIAS_IMPACTO: dict[str, MetodologiaImpacto] = {
    MOTOR_PI_SUPERACION: MetodologiaImpacto(
        motor_id=MOTOR_PI_SUPERACION,
        nombre="PI SUPERACIÓN DE UMBRAL",
        fuentes=_FUENTES_PI_SUPERACION,
    ),
    MOTOR_PI_PRECIPITACION: MetodologiaImpacto(
        motor_id=MOTOR_PI_PRECIPITACION,
        nombre="PI EXCESO DE PRECIPITACIÓN",
        fuentes=_FUENTES_PI_PRECIPITACION,
    ),
    MOTOR_PI_CALADO_ELO: MetodologiaImpacto(
        motor_id=MOTOR_PI_CALADO_ELO,
        nombre="PI FALTA DE CALADO",
        # Fuentes orientativas; no usar hasta existir diagrama PI FALTA DE CALADO.
        fuentes=_FUENTES_PI_CALADO,
        inputs_activo=INPUTS_CALADO_ACTIVO,
    ),
    MOTOR_PI_CALADO_ELS: MetodologiaImpacto(
        motor_id=MOTOR_PI_CALADO_ELS,
        nombre="OPEX FALTA DE CALADO",
        fuentes=_FUENTES_PI_CALADO,
        inputs_activo=INPUTS_CALADO_ACTIVO,
    ),
    MOTOR_PI_CALADO_ELU: MetodologiaImpacto(
        motor_id=MOTOR_PI_CALADO_ELU,
        nombre="CAPEX FALTA DE CALADO",
        fuentes=_FUENTES_PI_CALADO,
        inputs_activo=INPUTS_CALADO_ACTIVO,
    ),
    MOTOR_PI_FRANCOBORDO: MetodologiaImpacto(
        motor_id=MOTOR_PI_FRANCOBORDO,
        nombre="PI FALTA DE FRANCOBORDO",
        fuentes=_FUENTES_PI_FRANCOBORDO,
    ),
}


def metodologia(motor_id: str) -> MetodologiaImpacto | None:
    return METODOLOGIAS_IMPACTO.get(motor_id)


def motor_registrado(motor_id: str) -> bool:
    return motor_id in MODELOS_IMPACTO


def etiqueta_archivo_fuente(
    fuente_id: str,
    *,
    hoja: str | None = None,
) -> str:
    """Nombre legible del Excel (y hoja si aplica)."""
    try:
        meta: FuenteExcel = fuente(fuente_id)
    except KeyError:
        return fuente_id
    nombre = nombre_archivo_display(meta)
    hoja_txt = hoja or meta.hoja
    if hoja_txt:
        return f"{nombre} (hoja '{hoja_txt}')"
    return nombre


def resolver_motor_fila(
    row: pd.Series,
) -> tuple[str | None, EntradaCatalogoImpacto | None]:
    """Motor de calculo asociado a una fila IM del Excel de relacion."""
    modo = str(row.get("Modos de fallo / Modos de parada", "")).strip()
    variable = str(row.get("Variable", "")).strip()
    tipo = str(row.get("Tipo de impacto", "")).strip()

    if es_modo_exceso_precipitacion(modo, variable, tipo):
        entrada = entrada_catalogo(
            modo_fallo=modo,
            variable=variable,
            tipo_impacto=tipo or None,
        )
        return MOTOR_PI_PRECIPITACION, entrada

    if es_modo_superacion_umbral(modo, variable, tipo):
        entrada = entrada_catalogo(
            modo_fallo=modo,
            variable=variable,
            tipo_impacto=tipo or None,
        )
        return MOTOR_PI_SUPERACION, entrada

    if es_modo_falta_calado(modo, variable):
        entrada = entrada_catalogo(
            modo_fallo=modo,
            variable=variable,
            tipo_impacto=tipo or None,
        )
        # ELO -> PI, ELS -> OPEX, ELU -> CAPEX
        if tipo and match_texto(tipo, "ELU"):
            return MOTOR_PI_CALADO_ELU, entrada
        if tipo and match_texto(tipo, "ELS"):
            return MOTOR_PI_CALADO_ELS, entrada
        if tipo and match_texto(tipo, "ELO"):
            return MOTOR_PI_CALADO_ELO, entrada
        return None, entrada

    if es_modo_falta_francobordo(modo, variable, tipo):
        entrada = entrada_catalogo(
            modo_fallo=modo,
            variable=variable,
            tipo_impacto=tipo or None,
        )
        return MOTOR_PI_FRANCOBORDO, entrada

    entrada = entrada_catalogo(
        modo_fallo=modo,
        variable=variable,
        tipo_impacto=tipo or None,
    )
    if entrada is not None and entrada.implementado:
        return entrada.motor_id, entrada
    return None, entrada


def modos_catalogo_implementados() -> tuple[EntradaCatalogoImpacto, ...]:
    return tuple(e for e in CATALOGO_MODOS_IMPACTO if e.implementado)


__all__ = [
    "FuenteDatoRequerida",
    "METODOLOGIAS_IMPACTO",
    "MetodologiaImpacto",
    "etiqueta_archivo_fuente",
    "metodologia",
    "modos_catalogo_implementados",
    "motor_registrado",
    "resolver_motor_fila",
]
