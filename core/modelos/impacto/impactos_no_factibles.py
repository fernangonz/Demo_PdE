# -*- coding: utf-8 -*-
"""Filtro de impactos no factibles (Configuracion de impactos no factibles).

Filas marcadas en ``Preguntar_si_se_calculan.xlsx`` no se calculan en el paso 5 (IM).
La seleccion llega desde la UI; el core no importa Streamlit.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.data_loader import _buscar_columna, _normalizar
from core.modelos.impacto.pi_agitacion.utilidades import match_activo

MOTIVO_NO_FACTIBLE = (
    "Marcado como impacto no factible "
    "(Configuracion de impactos no factibles)."
)
CODIGO_NO_FACTIBLE = "IMPACTO_NO_FACTIBLE"


def _texto_celda(valor: object) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return str(valor).strip()


# Alias ya usado en PI agitacion: Agitacion <-> Exceso de oleaje (misma cadena).
_MODOS_ALIAS_AGITACION = frozenset({"agitacion", "exceso de oleaje"})
_MODO_CANONICO_AGITACION = "exceso de oleaje"


def _normalizar_modo(modo_fallo: object) -> str:
    """Normaliza modo; unifica Agitacion y Exceso de oleaje."""
    modo_n = _normalizar(modo_fallo)
    if modo_n in _MODOS_ALIAS_AGITACION:
        return _MODO_CANONICO_AGITACION
    return modo_n


def _clave_tipo_modo(tipo_impacto: object, modo_fallo: object) -> tuple[str, str]:
    return _normalizar(tipo_impacto), _normalizar_modo(modo_fallo)


@dataclass(frozen=True)
class TripleNoFactible:
    """Una combinacion Activo + Tipo de impacto + Modo de fallo marcada."""

    activo: str
    tipo_impacto: str
    modo_fallo: str


@dataclass(frozen=True)
class FiltroImpactosNoFactibles:
    """Conjunto de triples marcados como no factibles (no calcular)."""

    marcados: tuple[TripleNoFactible, ...] = ()

    @classmethod
    def vacio(cls) -> FiltroImpactosNoFactibles:
        return cls(marcados=())

    @classmethod
    def desde_dataframe(
        cls,
        df: pd.DataFrame,
        seleccion: list[bool] | None,
    ) -> FiltroImpactosNoFactibles:
        """Construye el filtro: ``seleccion[i]=True`` -> fila i no factible.

        Si ``seleccion`` falta o no alinea con las filas, por defecto todas
        las filas del Excel quedan marcadas (no se calculan).
        """
        if df is None or df.empty:
            return cls.vacio()

        n = len(df)
        if seleccion is None or len(seleccion) != n:
            flags = [True] * n
        else:
            flags = [bool(v) for v in seleccion]

        cols = list(df.columns)
        col_activo = _buscar_columna(
            cols,
            "activo fisico u operacional",
            "activo fisico",
            "activo",
        )
        col_tipo = _buscar_columna(cols, "tipo de impacto")
        col_modo = _buscar_columna(
            cols,
            "modos de fallo / modos de parada",
            "modos de fallo",
            "modo de fallo",
            "modos de parada",
        )
        if col_activo is None or col_tipo is None or col_modo is None:
            return cls.vacio()

        # Blank Activo cells (merged Excel rows) inherit the previous value.
        serie_activo = df[col_activo].ffill()

        marcados: list[TripleNoFactible] = []
        for i, (_, row) in enumerate(df.iterrows()):
            if not flags[i]:
                continue
            # Match Tipo de impacto (ELO/ELS/ELU), never the Descripcion column.
            activo = _texto_celda(serie_activo.iloc[i])
            tipo = _texto_celda(row.get(col_tipo))
            modo = _texto_celda(row.get(col_modo))
            if not activo or not tipo or not modo:
                continue
            marcados.append(
                TripleNoFactible(activo=activo, tipo_impacto=tipo, modo_fallo=modo)
            )
        return cls(marcados=tuple(marcados))

    def es_no_factible(
        self,
        activo: object,
        tipo_impacto: object,
        modo_fallo: object,
    ) -> bool:
        """True si Activo + Tipo impacto + Modo coinciden con una fila marcada."""
        if not self.marcados:
            return False
        tipo_n, modo_n = _clave_tipo_modo(tipo_impacto, modo_fallo)
        if not tipo_n or not modo_n:
            return False
        for t in self.marcados:
            if not match_activo(t.activo, activo):
                continue
            tt, mm = _clave_tipo_modo(t.tipo_impacto, t.modo_fallo)
            if tt == tipo_n and mm == modo_n:
                return True
        return False


def filtro_desde_datos(datos: object) -> FiltroImpactosNoFactibles | None:
    """Lee el filtro adjunto al repositorio/datos (si la UI lo paso)."""
    filtro = getattr(datos, "filtro_impactos_no_factibles", None)
    if filtro is None:
        return None
    if isinstance(filtro, FiltroImpactosNoFactibles):
        return filtro
    return None


def debe_omitir_im(
    datos: object,
    *,
    activo: object,
    tipo_impacto: object,
    modo_fallo: object,
) -> bool:
    """Punto unico: omitir este modo en el paso 5 / IM?"""
    filtro = filtro_desde_datos(datos)
    if filtro is None:
        return False
    return filtro.es_no_factible(activo, tipo_impacto, modo_fallo)


__all__ = [
    "MOTIVO_NO_FACTIBLE",
    "CODIGO_NO_FACTIBLE",
    "TripleNoFactible",
    "FiltroImpactosNoFactibles",
    "filtro_desde_datos",
    "debe_omitir_im",
]
