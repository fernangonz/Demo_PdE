"""Cálculo unificado de impactos por activo (todos los motores implementados)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from core.modelos.catalogo_impactos import (
    CATALOGO_MODOS_IMPACTO,
    MOTOR_PI_CALADO_ELO,
    MOTOR_PI_CALADO_ELS,
    MOTOR_PI_CALADO_ELU,
)
from core.modelos.flujos import tiene_diagrama
from core.modelos.impacto.auditoria import ModoSinModelo, modos_sin_modelo_puerto
from core.modelos.impacto.pi_agitacion import ParametrosEntrada as ParametrosAgitacion
from core.modelos.impacto.pi_agitacion import ResultadoPIAgitacion, calcular as calcular_agitacion
from core.modelos.impacto.pi_agitacion.utilidades import fila_configuracion
from core.modelos.impacto.pi_calado import ParametrosEntrada as ParametrosCalado
from core.modelos.impacto.pi_calado import ResultadoPICalado, calcular as calcular_calado
from core.modelos.impacto.pi_calado.utilidades import modos_falta_calado
from core.modelos.impacto.pi_francobordo import ParametrosEntrada as ParametrosFrancobordo
from core.modelos.impacto.pi_francobordo import ResultadoPIFrancobordo
from core.modelos.impacto.pi_francobordo.utilidades import modos_falta_francobordo
from core.modelos.impacto.pi_agitacion.utilidades import (
    impactos_por_activo,
    modos_superacion_umbral,
    nombre_activo_resumen,
)
from core.modelos.impacto.impactos_no_factibles import FiltroImpactosNoFactibles
from core.modelos.impacto.vista_resultados import listar_activos_config
from core.modelos.inputs_activo import (
    INPUTS_CALADO_ACTIVO,
    leer_calado_activo_desde_fila,
    leer_inputs_config_activo_desde_fila,
)
from core.modelos.registro import ejecutar_pi_agitacion, ejecutar_pi_francobordo


def _calado_con_procedimiento(tipo_impacto: str) -> bool:
    """True si el motor de esa familia tiene diagrama (metodologia definida)."""
    mapa = {
        "ELO": MOTOR_PI_CALADO_ELO,
        "ELS": MOTOR_PI_CALADO_ELS,
        "ELU": MOTOR_PI_CALADO_ELU,
    }
    motor_id = mapa.get(tipo_impacto.upper() if tipo_impacto else "")
    if not motor_id:
        return False
    return tiene_diagrama(motor_id)


@dataclass
class ResultadoCalculoActivo:
    """Salida combinada del cálculo para un activo (CP)."""

    ok: bool
    activo: str = ""
    activo_raw: str = ""
    cp_numero: int = 1
    error: str = ""
    advertencias: list[str] = field(default_factory=list)
    resultado_agitacion: ResultadoPIAgitacion | None = None
    resultado_francobordo: ResultadoPIFrancobordo | None = None
    resultado_calado_pi: ResultadoPICalado | None = None
    resultado_calado_opex: ResultadoPICalado | None = None
    resultado_calado_capex: ResultadoPICalado | None = None
    metadatos_ejecucion: dict[str, Any] = field(default_factory=dict)

    @property
    def parcial(self) -> bool:
        return self.ok and bool(self.advertencias)

    @property
    def resultado_calado(self) -> ResultadoPICalado | None:
        """Compatibilidad: primer calado disponible (PI / OPEX / CAPEX)."""
        return (
            self.resultado_calado_pi
            or self.resultado_calado_opex
            or self.resultado_calado_capex
        )


@dataclass
class ResultadoCalculoPuerto:
    """Salida del cálculo iterando todos los activos de Configuración del puerto."""

    ok: bool
    cp_total: int = 0
    error: str = ""
    advertencias: list[str] = field(default_factory=list)
    resultados_por_activo: list[ResultadoCalculoActivo] = field(default_factory=list)
    modos_sin_modelo: list[ModoSinModelo] = field(default_factory=list)

    @property
    def parcial(self) -> bool:
        return self.ok and bool(self.advertencias or self.modos_sin_modelo)


def _ejecutar_calado(
    datos: object,
    params: ParametrosCalado,
    *,
    etiqueta: str,
    incluir_pasos_comunes: bool = True,
) -> tuple[ResultadoPICalado | None, list[str]]:
    resultado = calcular_calado(
        datos,
        params,
        incluir_pasos_comunes=incluir_pasos_comunes,
    )
    advertencias: list[str] = []
    if resultado.advertencias:
        advertencias.extend(resultado.advertencias)
    if not resultado.ok:
        if resultado.error:
            advertencias.append(resultado.error)
        # Conservar resultado si hay ejecuciones auditables (OK o ERROR por modo).
        if getattr(resultado, "ejecuciones", None):
            return resultado, advertencias
        return None, advertencias or [f"Error en {etiqueta}."]
    return resultado, advertencias


def _activo_requiere_calado(
    df_relacion: pd.DataFrame,
    activo_raw: str,
) -> bool:
    impactos = impactos_por_activo(df_relacion, activo_raw)
    return (
        (
            bool(modos_falta_calado(impactos, tipo_impacto="ELO"))
            and _calado_con_procedimiento("ELO")
        )
        or (
            bool(modos_falta_calado(impactos, tipo_impacto="ELS"))
            and _calado_con_procedimiento("ELS")
        )
        or (
            bool(modos_falta_calado(impactos, tipo_impacto="ELU"))
            and _calado_con_procedimiento("ELU")
        )
    )


def _activo_requiere_agitacion(
    df_relacion: pd.DataFrame,
    activo_raw: str,
) -> bool:
    impactos = impactos_por_activo(df_relacion, activo_raw)
    return bool(modos_superacion_umbral(impactos))


def _activo_requiere_francobordo(
    df_relacion: pd.DataFrame,
    activo_raw: str,
) -> bool:
    impactos = impactos_por_activo(df_relacion, activo_raw)
    return bool(modos_falta_francobordo(impactos))


def _es_aviso_sin_modos_agitacion(texto: str) -> bool:
    return "No hay modos de superación de umbral" in texto


def _calado_buque_activo(
    *,
    activo_raw: str,
    fila_cfg: pd.Series,
    columnas: list[str],
    override: float | None = None,
) -> float | None:
    if override is not None and override > 0:
        return override
    return leer_calado_activo_desde_fila(fila_cfg, columnas).get("calado_buque")


def calcular_impactos_activo(
    datos: object,
    *,
    params_agitacion: ParametrosAgitacion | None = None,
    params_calado: ParametrosCalado | None = None,
    incluir_agitacion: bool = True,
    incluir_francobordo: bool = True,
    incluir_calado: bool = True,
    cp_numero: int = 1,
) -> ResultadoCalculoActivo:
    """Ejecuta los motores implementados para un activo (un CP)."""
    params_agitacion = params_agitacion or ParametrosAgitacion()
    activo_raw = params_agitacion.activo or (params_calado.activo if params_calado else "")
    activo_resumen = nombre_activo_resumen(activo_raw) if activo_raw else ""
    advertencias: list[str] = []
    resultado_ag: ResultadoPIAgitacion | None = None
    resultado_fb: ResultadoPIFrancobordo | None = None
    resultado_pi_cal: ResultadoPICalado | None = None
    resultado_opex: ResultadoPICalado | None = None
    resultado_capex: ResultadoPICalado | None = None

    if incluir_agitacion:
        resultado_ag = ejecutar_pi_agitacion(datos, params=params_agitacion)
        if not resultado_ag.ok:
            error_ag = resultado_ag.error or "Error en PI superación de umbral."
            # Activos sin modos PI (p. ej. diques) no deben generar aviso confuso.
            if not _es_aviso_sin_modos_agitacion(error_ag):
                advertencias.append(error_ag)

    if incluir_francobordo:
        resultado_fb = ejecutar_pi_francobordo(
            datos,
            params=ParametrosFrancobordo(
                tipo_uo=params_agitacion.tipo_uo,
                activo=params_agitacion.activo,
                baseline_year=params_agitacion.baseline_year,
            ),
        )
        omitido = (resultado_fb.metadatos_ejecucion or {}).get("omitido")
        if not resultado_fb.ok and omitido != "sin_modos_falta_francobordo":
            advertencias.append(resultado_fb.error or "Error en PI falta de francobordo.")

    if incluir_calado and params_calado is not None:
        df_relacion = getattr(datos, "relacion_impactos", None)
        impactos_cal = (
            impactos_por_activo(df_relacion, activo_raw)
            if df_relacion is not None and not df_relacion.empty
            else pd.DataFrame()
        )
        incluir_pasos = True

        # ELO -> PI / perdida de ingreso (solo si hay diagrama PI FALTA DE CALADO)
        if (
            modos_falta_calado(impactos_cal, tipo_impacto="ELO")
            and _calado_con_procedimiento("ELO")
        ):
            resultado_pi_cal, adv_pi = _ejecutar_calado(
                datos,
                ParametrosCalado(
                    tipo_uo=params_calado.tipo_uo,
                    activo=params_calado.activo,
                    calado_buque=params_calado.calado_buque,
                    baseline_year=params_calado.baseline_year,
                    tipo_impacto="ELO",
                ),
                etiqueta="PI FALTA DE CALADO",
                incluir_pasos_comunes=incluir_pasos,
            )
            advertencias.extend(adv_pi)
            if resultado_pi_cal is not None:
                incluir_pasos = False
        elif modos_falta_calado(impactos_cal, tipo_impacto="ELO"):
            advertencias.append(
                "PI FALTA DE CALADO (ELO): metodologia no definida "
                "(falta diagrama en Flujo de modelos). No se calcula."
            )

        # ELS -> OPEX
        if (
            modos_falta_calado(impactos_cal, tipo_impacto="ELS")
            and _calado_con_procedimiento("ELS")
        ):
            resultado_opex, adv_opex = _ejecutar_calado(
                datos,
                ParametrosCalado(
                    tipo_uo=params_calado.tipo_uo,
                    activo=params_calado.activo,
                    calado_buque=params_calado.calado_buque,
                    baseline_year=params_calado.baseline_year,
                    tipo_impacto="ELS",
                ),
                etiqueta="OPEX FALTA DE CALADO",
                incluir_pasos_comunes=incluir_pasos,
            )
            advertencias.extend(adv_opex)
            if resultado_opex is not None:
                incluir_pasos = False

        # ELU -> CAPEX
        if (
            modos_falta_calado(impactos_cal, tipo_impacto="ELU")
            and _calado_con_procedimiento("ELU")
        ):
            resultado_capex, adv_capex = _ejecutar_calado(
                datos,
                ParametrosCalado(
                    tipo_uo=params_calado.tipo_uo,
                    activo=params_calado.activo,
                    calado_buque=params_calado.calado_buque,
                    baseline_year=params_calado.baseline_year,
                    tipo_impacto="ELU",
                ),
                etiqueta="CAPEX FALTA DE CALADO",
                incluir_pasos_comunes=incluir_pasos,
            )
            advertencias.extend(adv_capex)

    if (
        not incluir_agitacion
        and not incluir_francobordo
        and resultado_pi_cal is None
        and resultado_opex is None
        and resultado_capex is None
    ):
        # Sin motores aplicables a este activo: no es un fallo, se omite en silencio.
        return ResultadoCalculoActivo(
            ok=True,
            activo=activo_raw or activo_resumen,
            activo_raw=activo_raw,
            cp_numero=cp_numero,
            advertencias=[],
            resultado_agitacion=None,
            resultado_francobordo=None,
            resultado_calado_pi=None,
            resultado_calado_opex=None,
            resultado_calado_capex=None,
        )

    meta: dict[str, Any] = {}
    if resultado_ag and resultado_ag.ok:
        meta.update(resultado_ag.metadatos_ejecucion)
    if resultado_fb and resultado_fb.ok:
        meta["francobordo"] = resultado_fb.metadatos_ejecucion
    if resultado_pi_cal:
        meta["calado_pi"] = resultado_pi_cal.metadatos_ejecucion
    if resultado_opex:
        meta["calado_opex"] = resultado_opex.metadatos_ejecucion
    if resultado_capex:
        meta["calado_capex"] = resultado_capex.metadatos_ejecucion

    ok = bool(
        (resultado_ag and resultado_ag.ok)
        or (resultado_fb and resultado_fb.ok)
        or (resultado_pi_cal and resultado_pi_cal.ok)
        or (resultado_opex and resultado_opex.ok)
        or (resultado_capex and resultado_capex.ok)
        or bool(getattr(resultado_pi_cal, "ejecuciones", None))
        or bool(getattr(resultado_opex, "ejecuciones", None))
        or bool(getattr(resultado_capex, "ejecuciones", None))
    )

    return ResultadoCalculoActivo(
        ok=ok,
        activo=activo_raw or activo_resumen,
        activo_raw=activo_raw,
        cp_numero=cp_numero,
        advertencias=advertencias,
        resultado_agitacion=resultado_ag if resultado_ag and resultado_ag.ok else None,
        resultado_francobordo=resultado_fb if resultado_fb and resultado_fb.ok else None,
        resultado_calado_pi=resultado_pi_cal,
        resultado_calado_opex=resultado_opex,
        resultado_calado_capex=resultado_capex,
        metadatos_ejecucion=meta,
    )


def calcular_impactos_puerto(
    datos: object,
    *,
    overrides_calado: dict[str, float] | None = None,
    incluir_agitacion: bool = True,
    incluir_francobordo: bool = True,
    incluir_calado: bool = True,
    filtro_impactos_no_factibles: FiltroImpactosNoFactibles | None = None,
) -> ResultadoCalculoPuerto:
    """Itera CP (paso 3 del diagrama) sobre todos los activos de Configuración del puerto."""
    if filtro_impactos_no_factibles is not None:
        setattr(datos, "filtro_impactos_no_factibles", filtro_impactos_no_factibles)
    config_puerto = getattr(datos, "config_puerto", None)
    df_relacion = getattr(datos, "relacion_impactos", None)

    if config_puerto is None or config_puerto.empty:
        return ResultadoCalculoPuerto(
            ok=False,
            error="Se requiere la configuración del puerto (Configuración_del_puerto.xlsx).",
        )

    activos = listar_activos_config(config_puerto)
    if not activos:
        return ResultadoCalculoPuerto(
            ok=False,
            error="No hay activos en Configuración del puerto.",
        )

    overrides_calado = overrides_calado or {}
    columnas = list(config_puerto.columns)
    advertencias: list[str] = []
    resultados: list[ResultadoCalculoActivo] = []

    if df_relacion is not None and not df_relacion.empty:
        modos_faltantes = modos_sin_modelo_puerto(df_relacion, activos)
    else:
        modos_faltantes = []

    for cp_num, activo_raw in enumerate(activos, start=1):
        fila_cfg = fila_configuracion(config_puerto, activo=activo_raw)
        if fila_cfg is None:
            advertencias.append(
                f"CP {cp_num}: no se encontró fila en Configuración del puerto "
                f"para «{nombre_activo_resumen(activo_raw)}»."
            )
            resultados.append(
                ResultadoCalculoActivo(
                    ok=False,
                    activo=nombre_activo_resumen(activo_raw),
                    activo_raw=activo_raw,
                    cp_numero=cp_num,
                    error="Fila de configuración no encontrada.",
                )
            )
            continue

        requiere_agitacion = (
            df_relacion is not None
            and not df_relacion.empty
            and _activo_requiere_agitacion(df_relacion, activo_raw)
        )
        requiere_calado = (
            df_relacion is not None
            and not df_relacion.empty
            and _activo_requiere_calado(df_relacion, activo_raw)
        )
        requiere_francobordo = (
            df_relacion is not None
            and not df_relacion.empty
            and _activo_requiere_francobordo(df_relacion, activo_raw)
        )
        inputs_cfg = leer_inputs_config_activo_desde_fila(fila_cfg, columnas)
        fb_activo = inputs_cfg.get("francobordo")
        if fb_activo is not None and not requiere_francobordo:
            advertencias.append(
                f"CP {cp_num} — {nombre_activo_resumen(activo_raw)}: "
                f"tiene Fb={fb_activo:g} m en Configuracion del puerto pero "
                f"no hay modo «Falta de francobordo» asociado a este activo "
                f"en la matriz de impactos."
            )
        override = overrides_calado.get(activo_raw)
        calado_buque = (
            _calado_buque_activo(
                activo_raw=activo_raw,
                fila_cfg=fila_cfg,
                columnas=columnas,
                override=override,
            )
            if requiere_calado
            else None
        )

        if requiere_calado and calado_buque is None:
            etiqueta = INPUTS_CALADO_ACTIVO[0].etiqueta
            msg = (
                f"CP {cp_num} — {nombre_activo_resumen(activo_raw)}: "
                f"falta {etiqueta} en Configuración del puerto "
                "(necesario para OPEX/CAPEX falta de calado)."
            )
            advertencias.append(msg)
            params_calado = None
        else:
            params_calado = (
                ParametrosCalado(
                    activo=activo_raw,
                    calado_buque=calado_buque,
                )
                if requiere_calado and calado_buque is not None
                else None
            )

        resultado = calcular_impactos_activo(
            datos,
            params_agitacion=ParametrosAgitacion(activo=activo_raw),
            params_calado=params_calado,
            incluir_agitacion=incluir_agitacion and requiere_agitacion,
            incluir_francobordo=incluir_francobordo and requiere_francobordo,
            incluir_calado=incluir_calado and params_calado is not None,
            cp_numero=cp_num,
        )
        resultados.append(resultado)
        if requiere_francobordo and resultado.resultado_francobordo is None:
            ya_avisado = any(
                "francobordo" in adv.lower()
                for adv in resultado.advertencias
            )
            if not ya_avisado:
                advertencias.append(
                    f"CP {cp_num} — {nombre_activo_resumen(activo_raw)}: "
                    f"PI falta de francobordo no produjo resultado "
                    f"(revise Fb, umbrales e indicadores climaticos)."
                )
        if resultado.advertencias:
            prefijo = f"CP {cp_num} — {resultado.activo}:"
            advertencias.extend(
                f"{prefijo} {adv}" if not adv.startswith("CP ") else adv
                for adv in resultado.advertencias
                if "No hay modos de superación de umbral" not in adv
            )
        if not resultado.ok and resultado.error:
            if "No hay modos de superación de umbral" not in resultado.error:
                advertencias.append(
                    f"CP {cp_num} — {resultado.activo}: {resultado.error}"
                )

    ok = any(r.ok for r in resultados)
    error = ""
    if not ok:
        error = advertencias[0] if advertencias else "Ningún activo pudo calcularse."

    return ResultadoCalculoPuerto(
        ok=ok,
        cp_total=len(activos),
        error=error,
        advertencias=advertencias,
        resultados_por_activo=resultados,
        modos_sin_modelo=modos_faltantes,
    )


def modo_implementado(modo_id: str) -> bool:
    for entrada in CATALOGO_MODOS_IMPACTO:
        if entrada.id == modo_id:
            return entrada.implementado
    return False
