# -*- coding: utf-8 -*-
"""Esquemas del modelo de falta de calado.

Mapeo economico (tipo de impacto):
- ELO -> interrupcion operativa -> PI / perdida de ingreso
- ELS -> limitacion operativa -> OPEX
- ELU -> fallo -> CAPEX
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from core.modelos.impacto.pi_agitacion.schemas import IndicadorEvaluado, IteracionResultado, SintesisCambios
from core.modelos.impacto.pi_agitacion.utilidades import match_texto
from core.schemas.base import MetadatosModelo, ResultadoModelo
from core.schemas.ejecucion import IteracionEjecucion
from core.schemas.serializacion import dataframe_a_registros

MODELO_ID_ELO = "PI_CALADO_ELO"
MODELO_ID_ELS = "PI_CALADO_ELS"
MODELO_ID_ELU = "PI_CALADO_ELU"
MODELO_ID = MODELO_ID_ELS
MODELO_VERSION = "1.0.0"
MODO_FALLO_DEFAULT = "Falta de Calado"
VARIABLE_DEFAULT = "Nivel del mar"

METADATOS_ELO = MetadatosModelo(
    id=MODELO_ID_ELO,
    nombre="PI FALTA DE CALADO",
    version=MODELO_VERSION,
    categoria="impacto",
    descripcion=(
        "h = NM - h0 - h sedimentacion. Solo filas IM con tipo de impacto ELO "
        "(interrupcion operativa / perdida de ingreso)."
    ),
)

METADATOS_ELS = MetadatosModelo(
    id=MODELO_ID_ELS,
    nombre="OPEX FALTA DE CALADO",
    version=MODELO_VERSION,
    categoria="impacto",
    descripcion=(
        "h = NM - h0 - h sedimentacion. Solo filas IM con tipo de impacto ELS "
        "(limitacion operativa / OPEX)."
    ),
)

METADATOS_ELU = MetadatosModelo(
    id=MODELO_ID_ELU,
    nombre="CAPEX FALTA DE CALADO",
    version=MODELO_VERSION,
    categoria="impacto",
    descripcion=(
        "h = NM - h0 - h sedimentacion. Solo filas IM con tipo de impacto ELU "
        "(fallo / CAPEX)."
    ),
)

# Compatibilidad: alias historico apuntaba a OPEX.
METADATOS = METADATOS_ELS


def metadatos_para_tipo_impacto(tipo_impacto: str) -> MetadatosModelo:
    """ELO->PI, ELS->OPEX, ELU->CAPEX."""
    if match_texto(tipo_impacto, "ELU"):
        return METADATOS_ELU
    if match_texto(tipo_impacto, "ELS"):
        return METADATOS_ELS
    return METADATOS_ELO


def modelo_id_para_tipo_impacto(tipo_impacto: str) -> str:
    return metadatos_para_tipo_impacto(tipo_impacto).id


def nombre_modelo_para_tipo_impacto(tipo_impacto: str) -> str:
    return metadatos_para_tipo_impacto(tipo_impacto).nombre


@dataclass
class ParametrosEntrada:
    """Parametros del activo para falta de calado."""

    tipo_uo: str | None = None
    activo: str | None = None
    calado_buque: float | None = None
    baseline_year: int = 2005
    tipo_impacto: str = "ELS"

    @property
    def modelo_id(self) -> str:
        return modelo_id_para_tipo_impacto(self.tipo_impacto)


@dataclass
class ResultadoPICalado(ResultadoModelo):
    """Salida del modelo de falta de calado (PI / OPEX / CAPEX)."""

    iteraciones: list[IteracionResultado] = field(default_factory=list)
    ejecuciones: list[IteracionEjecucion] = field(default_factory=list)
    resultados_por_pasos: Any = None
    hsedimentacion_historico: float | None = None

    @classmethod
    def error(
        cls,
        mensaje: str,
        *,
        metadatos: MetadatosModelo | None = None,
        ejecuciones: list[IteracionEjecucion] | None = None,
        metadatos_ejecucion: dict[str, Any] | None = None,
        resultados_por_pasos=None,
    ) -> ResultadoPICalado:
        return cls(
            metadatos=metadatos or METADATOS_ELS,
            ok=False,
            error=mensaje,
            ejecuciones=list(ejecuciones or []),
            metadatos_ejecucion=dict(metadatos_ejecucion or {}),
            resultados_por_pasos=resultados_por_pasos,
        )

    @classmethod
    def desde_calculo(
        cls,
        *,
        metadatos: MetadatosModelo,
        metadatos_ejecucion: dict[str, Any],
        iteraciones: list[IteracionResultado],
        ejecuciones: list[IteracionEjecucion] | None = None,
        resultados_por_pasos=None,
        hsedimentacion_historico: float | None = None,
    ) -> ResultadoPICalado:
        ejecuciones = list(ejecuciones or [])
        if not iteraciones and not any(e.ok for e in ejecuciones):
            motivos = [e.motivo for e in ejecuciones if e.motivo]
            return cls.error(
                motivos[0] if motivos else "No se genero ninguna iteracion de falta de calado.",
                metadatos=metadatos,
                ejecuciones=ejecuciones,
                metadatos_ejecucion=metadatos_ejecucion,
                resultados_por_pasos=resultados_por_pasos,
            )

        tablas = {
            f"resultado_calado_iter_{it.numero}": dataframe_a_registros(it.tabla_resultado)
            for it in iteraciones
        }
        advertencias = [adv for it in iteraciones for adv in it.advertencias]
        for ej in ejecuciones:
            if ej.estado != "ok" and ej.motivo:
                advertencias.append(f"{ej.modo_fallo}: {ej.motivo}")

        return cls(
            metadatos=metadatos,
            ok=bool(iteraciones),
            error=None if iteraciones else (
                ejecuciones[0].motivo if ejecuciones else "Sin iteraciones OK"
            ),
            advertencias=advertencias,
            metadatos_ejecucion=metadatos_ejecucion,
            tablas=tablas,
            iteraciones=iteraciones,
            ejecuciones=ejecuciones,
            resultados_por_pasos=resultados_por_pasos,
            hsedimentacion_historico=hsedimentacion_historico,
        )
