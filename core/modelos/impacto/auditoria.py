"""Auditoría de modos de fallo asociados a un activo vs modelos implementados."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.modelos.catalogo_impactos import entrada_catalogo, titulo_desde_modo
from core.modelos.flujos import tiene_diagrama
from core.modelos.impacto.pi_agitacion.utilidades import (
    es_modo_superacion_umbral,
    impactos_por_activo,
    nombre_activo_resumen,
)
from core.modelos.impacto.pi_calado.utilidades import es_modo_falta_calado
from core.modelos.impacto.pi_francobordo.utilidades import es_modo_falta_francobordo
from core.modelos.metodologias import motor_registrado, resolver_motor_fila


@dataclass(frozen=True)
class ModoSinModelo:
    """Fila IM del Excel de impactos sin motor de cálculo implementado."""

    activo: str
    activo_raw: str
    n_relacion: int | None
    modo_fallo: str
    variable: str
    tipo_impacto: str

    @property
    def etiqueta(self) -> str:
        return titulo_desde_modo(
            self.modo_fallo,
            variable=self.variable,
            tipo_impacto=self.tipo_impacto or None,
        )


def _motor_con_procedimiento(motor_id: str | None) -> bool:
    """True solo si el motor esta registrado y tiene diagrama de procedimiento."""
    if not motor_id or not motor_registrado(motor_id):
        return False
    return tiene_diagrama(motor_id)


def fila_tiene_modelo_implementado(row: pd.Series) -> bool:
    """True si existe un motor con procedimiento definido que procese esta fila IM.

    Sin diagrama de metodologia (p. ej. PI FALTA DE CALADO / ELO) -> False:
    se reporta como sin metodologia, no se inventan inputs del procedimiento.
    """
    modo = str(row.get("Modos de fallo / Modos de parada", "")).strip()
    variable = str(row.get("Variable", "")).strip()
    tipo = str(row.get("Tipo de impacto", "")).strip()

    if es_modo_superacion_umbral(modo, variable, tipo):
        from core.modelos.catalogo_impactos import MOTOR_PI_SUPERACION

        return _motor_con_procedimiento(MOTOR_PI_SUPERACION)

    if es_modo_falta_calado(modo, variable):
        motor_id, _entrada = resolver_motor_fila(row)
        return _motor_con_procedimiento(motor_id)

    if es_modo_falta_francobordo(modo, variable, tipo):
        from core.modelos.catalogo_impactos import MOTOR_PI_FRANCOBORDO

        return _motor_con_procedimiento(MOTOR_PI_FRANCOBORDO)

    entrada = entrada_catalogo(
        modo_fallo=modo,
        variable=variable,
        tipo_impacto=tipo or None,
    )
    if entrada is None or not entrada.implementado:
        return False
    return _motor_con_procedimiento(entrada.motor_id)


def modos_sin_modelo_activo(
    df_relacion: pd.DataFrame,
    activo_raw: str,
) -> list[ModoSinModelo]:
    """Modos IM del activo que aún no tienen modelo de impacto."""
    faltantes: list[ModoSinModelo] = []
    activo_resumen = nombre_activo_resumen(activo_raw)

    for _, row in impactos_por_activo(df_relacion, activo_raw).iterrows():
        if fila_tiene_modelo_implementado(row):
            continue
        n_rel = row.get("Nº")
        faltantes.append(
            ModoSinModelo(
                activo=activo_resumen,
                activo_raw=activo_raw,
                n_relacion=int(n_rel) if pd.notna(n_rel) else None,
                modo_fallo=str(row.get("Modos de fallo / Modos de parada", "")).strip(),
                variable=str(row.get("Variable", "")).strip(),
                tipo_impacto=str(row.get("Tipo de impacto", "")).strip(),
            )
        )
    return faltantes


def modos_sin_modelo_puerto(
    df_relacion: pd.DataFrame,
    activos: list[str],
) -> list[ModoSinModelo]:
    """Todos los modos IM sin modelo para los activos del puerto."""
    todos: list[ModoSinModelo] = []
    for activo_raw in activos:
        todos.extend(modos_sin_modelo_activo(df_relacion, activo_raw))
    return todos


__all__ = [
    "ModoSinModelo",
    "fila_tiene_modelo_implementado",
    "modos_sin_modelo_activo",
    "modos_sin_modelo_puerto",
]
