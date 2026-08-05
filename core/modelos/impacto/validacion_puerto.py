# -*- coding: utf-8 -*-
"""Validacion automatica del puerto antes del calculo de impactos."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from core.data_loader import auditar_fuentes_excel
from core.fuentes_datos import fuente
from core.modelos.catalogo_impactos import (
    MOTOR_PI_CALADO_ELO,
    MOTOR_PI_CALADO_ELS,
    MOTOR_PI_CALADO_ELU,
    MOTOR_PI_FRANCOBORDO,
    MOTOR_PI_PRECIPITACION,
    MOTOR_PI_SUPERACION,
    titulo_desde_modo,
)
from core.modelos.impacto.auditoria import (
    ModoSinModelo,
    fila_tiene_modelo_implementado,
    modos_sin_modelo_puerto,
)
from core.modelos.impacto.impactos_no_factibles import (
    FiltroImpactosNoFactibles,
    debe_omitir_im,
)
from core.modelos.impacto.pi_agitacion.schemas import BASELINE_YEAR
from core.modelos.impacto.pi_agitacion.utilidades import (
    buscar_umbral_umbrales,
    clasificar_indicadores_umbral,
    columna_por_patron,
    columnas_oleaje,
    es_modo_inundacion_costera,
    es_modo_superacion_umbral,
    fila_configuracion,
    impactos_por_activo,
    modos_superacion_umbral,
    nombre_activo_resumen,
)
from core.modelos.impacto.pi_calado.utilidades import (
    buscar_fila_indicador,
    columnas_nivel_mar,
    dataframe_pestana,
    es_modo_falta_calado,
    modos_falta_calado,
    resolver_indicadores_calado,
)
from core.modelos.impacto.pi_francobordo.utilidades import (
    buscar_umbral_francobordo,
    clasificar_indicadores_francobordo,
    es_modo_falta_francobordo,
    modos_falta_francobordo,
    pestana_clima_francobordo,
    variable_clima_francobordo,
)
from core.modelos.impacto.pi_precipitacion.utilidades import (
    buscar_fila_indicador_predefinido,
    es_modo_exceso_precipitacion,
    indicadores_predefinidos_precipitacion,
    modos_exceso_precipitacion,
    resolver_pestana_clima_precipitacion,
)
from core.modelos.impacto.vista_resultados import listar_activos_config
from core.relacion_modelos import buscar_regla_modelo
from core.modelos.inputs_activo import (
    leer_calado_activo_desde_fila,
    leer_inputs_config_activo_desde_fila,
    validar_inputs_positivos,
)
from core.modelos.flujos import resolver_motivo_y_codigo_diagrama_indicadores, tiene_diagrama
from core.modelos.metodologias import (
    etiqueta_archivo_fuente,
    metodologia,
    motor_registrado,
    resolver_motor_fila,
)

NivelAviso = Literal["error", "warning", "info"]

_FUENTES_CRITICAS = frozenset({"config_puerto", "clima", "relacion_ivc"})
_COL_N_REL = "N\u00ba"


@dataclass(frozen=True)
class AvisoValidacion:
    """Problema detectado en la validacion previa al calculo."""

    nivel: NivelAviso
    codigo: str
    activo: str
    activo_raw: str
    modo_fallo: str
    variable: str
    tipo_impacto: str
    motor_id: str
    input_faltante: str
    archivo: str
    hoja: str
    mensaje: str
    n_relacion: int | None = None


@dataclass
class ResultadoValidacionPuerto:
    """Informe de validacion para todos los activos del puerto."""

    activos_detectados: list[str] = field(default_factory=list)
    avisos: list[AvisoValidacion] = field(default_factory=list)
    modos_sin_modelo: list[ModoSinModelo] = field(default_factory=list)
    activos_con_modo_calculable: set[str] = field(default_factory=set)

    @property
    def errores(self) -> list[AvisoValidacion]:
        return [a for a in self.avisos if a.nivel == "error"]

    @property
    def advertencias(self) -> list[AvisoValidacion]:
        return [a for a in self.avisos if a.nivel == "warning"]

    @property
    def bloquea_calculo(self) -> bool:
        if not self.activos_detectados:
            return True
        return any(
            a.codigo == "ARCHIVO_FALTANTE" and a.input_faltante in _FUENTES_CRITICAS
            for a in self.errores
        )

    @property
    def puede_calcular(self) -> bool:
        return not self.bloquea_calculo


def _tipo_y_modo_fila(fila_rel: pd.Series | object) -> tuple[str, str]:
    """Tipo de impacto (ELO/ELS/ELU) y modo de fallo de una fila de relación."""
    if isinstance(fila_rel, pd.Series):
        tipo = str(fila_rel.get("Tipo de impacto", "")).strip()
        modo = str(fila_rel.get("Modos de fallo / Modos de parada", "")).strip()
    else:
        tipo = str(getattr(fila_rel, "tipo_impacto", "") or "").strip()
        modo = str(getattr(fila_rel, "modo_fallo", "") or "").strip()
    return tipo, modo


def _omitir_modo_no_factible(
    datos: object,
    *,
    activo_raw: str,
    fila_rel: pd.Series | object,
) -> bool:
    """True si el triple está marcado en Configuración de impactos no factibles."""
    tipo, modo = _tipo_y_modo_fila(fila_rel)
    return debe_omitir_im(
        datos,
        activo=activo_raw,
        tipo_impacto=tipo,
        modo_fallo=modo,
    )


def _aviso(
    *,
    nivel: NivelAviso,
    codigo: str,
    activo: str,
    activo_raw: str,
    modo_fallo: str = "",
    variable: str = "",
    tipo_impacto: str = "",
    motor_id: str = "",
    input_faltante: str = "",
    archivo: str = "",
    hoja: str = "",
    mensaje: str,
    n_relacion: int | None = None,
) -> AvisoValidacion:
    return AvisoValidacion(
        nivel=nivel,
        codigo=codigo,
        activo=activo,
        activo_raw=activo_raw,
        modo_fallo=modo_fallo,
        variable=variable,
        tipo_impacto=tipo_impacto,
        motor_id=motor_id,
        input_faltante=input_faltante,
        archivo=archivo,
        hoja=hoja,
        mensaje=mensaje,
        n_relacion=n_relacion,
    )


def _n_relacion(row: pd.Series) -> int | None:
    n_rel = row.get(_COL_N_REL)
    if n_rel is None:
        for col in row.index:
            nombre = str(col).strip().lower()
            if nombre in ("n", "no", "num", "nro", "n\u00ba"):
                n_rel = row.get(col)
                break
    return int(n_rel) if pd.notna(n_rel) else None


def _pestana_ind(ind: object) -> str:
    pest = getattr(ind, "pesta\u00f1a", None)
    if pest is None:
        pest = getattr(ind, "pestana", None)
    texto = str(pest).strip() if pest is not None else ""
    return texto or "Nivel del mar"


def _validar_fuentes_excel(resultado: ResultadoValidacionPuerto) -> None:
    for auditoria in auditar_fuentes_excel():
        if auditoria.encontrado:
            continue
        try:
            meta = fuente(auditoria.fuente_id)
            hoja = meta.hoja or ""
        except KeyError:
            hoja = ""
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="ARCHIVO_FALTANTE",
                activo="(puerto)",
                activo_raw="",
                input_faltante=auditoria.fuente_id,
                archivo=auditoria.archivo,
                hoja=hoja,
                mensaje=(
                    f"No se encontro el archivo '{auditoria.archivo}' "
                    f"en {auditoria.carpeta}."
                ),
            )
        )


def _validar_fila_agitacion(
    resultado: ResultadoValidacionPuerto,
    *,
    activo_raw: str,
    activo_resumen: str,
    tipo_uo: str,
    tipo_activo_cfg: str | None,
    fila_rel: pd.Series,
    relacion_modelos: pd.DataFrame | None,
    por_hoja_umbrales: dict[str, pd.DataFrame] | None,
    lista_master: pd.DataFrame | None,
    info_clima: dict,
    baseline_year: int,
    fila_cfg: pd.Series | None = None,
    columnas_cfg: list[str] | None = None,
) -> bool:
    modo_fallo = str(fila_rel.get("Modos de fallo / Modos de parada", "")).strip()
    variable = str(fila_rel.get("Variable", "")).strip()
    estado_limite = str(fila_rel.get("Tipo de impacto", "")).strip() or None
    n_rel = _n_relacion(fila_rel)
    tipo_activo_servicio = (
        str(fila_rel.get("Tipo activo/servicio", "")).strip() or tipo_activo_cfg
    )
    etiqueta_im = titulo_desde_modo(
        modo_fallo,
        variable=variable,
        tipo_impacto=estado_limite,
    )
    motor_id = MOTOR_PI_SUPERACION
    es_inundacion = es_modo_inundacion_costera(modo_fallo, variable, estado_limite)

    fb_activo = None
    if es_inundacion and fila_cfg is not None and columnas_cfg is not None:
        inputs_cfg = leer_inputs_config_activo_desde_fila(fila_cfg, columnas_cfg)
        fb_activo = inputs_cfg.get("francobordo")

    regla_modelo = buscar_regla_modelo(
        relacion_modelos,
        modelo_id=motor_id,
        activo=activo_raw,
        modo_fallo=modo_fallo,
        variable=variable,
        estado_limite=estado_limite,
    )
    percentil = regla_modelo.percentil
    regla_ind = regla_modelo.regla_indicador

    umbral_m: float | None = None
    if not (regla_modelo.desde_excel and regla_ind.usa_predefinido):
        if es_inundacion and fb_activo is not None:
            umbral_m = fb_activo
        else:
            if por_hoja_umbrales is None:
                resultado.avisos.append(
                    _aviso(
                        nivel="error",
                        codigo="UMBRAL_FALTANTE",
                        activo=activo_resumen,
                        activo_raw=activo_raw,
                        modo_fallo=modo_fallo,
                        variable=variable,
                        tipo_impacto=estado_limite or "",
                        motor_id=motor_id,
                        input_faltante="Fb o umbral" if es_inundacion else "umbral",
                        archivo=etiqueta_archivo_fuente("umbrales"),
                        hoja=variable,
                        mensaje=(
                            f"{activo_resumen} - {etiqueta_im}: no hay datos de umbrales "
                            f"para {variable}"
                            + (
                                " y Fb está vacío en Configuración del puerto."
                                if es_inundacion
                                else "."
                            )
                        ),
                        n_relacion=n_rel,
                    )
                )
                return False

            umbral_info = buscar_umbral_umbrales(
                por_hoja_umbrales,
                n_relacion=n_rel,
                tipo_uo=tipo_uo,
                activo=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                tipo_activo_servicio=tipo_activo_servicio,
                lista_master=lista_master,
            )
            if umbral_info is None and not regla_ind.usa_predefinido:
                resultado.avisos.append(
                    _aviso(
                        nivel="error",
                        codigo="UMBRAL_FALTANTE",
                        activo=activo_resumen,
                        activo_raw=activo_raw,
                        modo_fallo=modo_fallo,
                        variable=variable,
                        tipo_impacto=estado_limite or "",
                        motor_id=motor_id,
                        input_faltante="Fb o umbral" if es_inundacion else "umbral",
                        archivo=etiqueta_archivo_fuente("umbrales"),
                        hoja=variable,
                        mensaje=(
                            f"{activo_resumen} - {etiqueta_im}: no se encontro "
                            + (
                                "referencia (Fb vacío y sin umbral) "
                                if es_inundacion
                                else "umbral "
                            )
                            + f"para '{modo_fallo}' / {variable}."
                        ),
                        n_relacion=n_rel,
                    )
                )
                return False
            if umbral_info is not None:
                _, umbral_m = umbral_info
                if umbral_m is None and not regla_ind.usa_predefinido:
                    var_n = variable.lower()
                    if var_n not in ("viento", "corriente", "visibilidad"):
                        resultado.avisos.append(
                            _aviso(
                                nivel="error",
                                codigo="UMBRAL_NO_NUMERICO",
                                activo=activo_resumen,
                                activo_raw=activo_raw,
                                modo_fallo=modo_fallo,
                                variable=variable,
                                tipo_impacto=estado_limite or "",
                                motor_id=motor_id,
                                input_faltante=(
                                    "Fb o umbral numerico"
                                    if es_inundacion
                                    else "umbral numerico"
                                ),
                                archivo=etiqueta_archivo_fuente("umbrales"),
                                hoja=variable,
                                mensaje=(
                                    f"{activo_resumen} - {etiqueta_im}: "
                                    + (
                                        "Fb vacío y el umbral no es numérico "
                                        if es_inundacion
                                        else "el umbral no es numérico "
                                    )
                                    + f"en {etiqueta_archivo_fuente('umbrales')}."
                                ),
                                n_relacion=n_rel,
                            )
                        )
                        return False

    if es_inundacion:
        df_clima, pestana_clima = pestana_clima_francobordo(info_clima, variable)
        col_hist, columnas_fut = columnas_oleaje(
            info_clima, baseline_year, variable=pestana_clima
        )
        hoja_clima = pestana_clima
    else:
        por_variable = info_clima.get("por_variable", {})
        if variable not in por_variable:
            resultado.avisos.append(
                _aviso(
                    nivel="error",
                    codigo="CLIMA_VARIABLE_FALTANTE",
                    activo=activo_resumen,
                    activo_raw=activo_raw,
                    modo_fallo=modo_fallo,
                    variable=variable,
                    tipo_impacto=estado_limite or "",
                    motor_id=motor_id,
                    input_faltante=f"variable climatica '{variable}'",
                    archivo=etiqueta_archivo_fuente("clima"),
                    hoja=variable,
                    mensaje=(
                        f"{activo_resumen} - {etiqueta_im}: no hay pestana de "
                        f"'{variable}' en Indicadores climaticos."
                    ),
                    n_relacion=n_rel,
                )
            )
            return False
        df_clima = por_variable.get(variable, {}).get("df", pd.DataFrame())
        col_hist, columnas_fut = columnas_oleaje(
            info_clima, baseline_year, variable=variable
        )
        hoja_clima = variable

    if col_hist is None or not columnas_fut:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="CLIMA_COLUMNAS_FALTANTES",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite or "",
                motor_id=motor_id,
                input_faltante="columnas de escenario climatico",
                archivo=etiqueta_archivo_fuente("clima"),
                hoja=hoja_clima,
                mensaje=(
                    f"{activo_resumen} - {etiqueta_im}: faltan columnas clim\u00e1ticas "
                    f"para {hoja_clima} (hist\u00f3rico o futuro)."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    if es_inundacion:
        fila_ind, _ = clasificar_indicadores_francobordo(
            df_clima,
            umbral_m,
            percentil=percentil,
            tipo_uo=tipo_uo,
            regla=regla_ind,
        )
    else:
        fila_ind, _ = clasificar_indicadores_umbral(
            df_clima,
            umbral_m,
            percentil=percentil,
            variable=variable,
            regla=regla_ind,
        )
    if fila_ind is None:
        if es_inundacion:
            indicador_txt = (
                regla_ind.indicador
                if regla_ind.usa_predefinido
                else f"inundacion costera en un atraque ≥ {umbral_m}"
            )
        else:
            indicador_txt = (
                regla_ind.indicador
                if regla_ind.usa_predefinido
                else f"indicador para umbral {umbral_m}"
            )
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="INDICADOR_CLIMA_FALTANTE",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite or "",
                motor_id=motor_id,
                input_faltante=indicador_txt or "indicador climatico",
                archivo=etiqueta_archivo_fuente("clima"),
                hoja=hoja_clima,
                mensaje=(
                    f"{activo_resumen} - {etiqueta_im}: no se encontro el indicador "
                    f"'{indicador_txt}' ({percentil}) en {etiqueta_archivo_fuente('clima')} "
                    f"ni regla en {etiqueta_archivo_fuente('relacion_modelos')}."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    return True


def _validar_fila_francobordo(
    resultado: ResultadoValidacionPuerto,
    *,
    activo_raw: str,
    activo_resumen: str,
    tipo_uo: str,
    tipo_activo_cfg: str | None,
    fila_rel: pd.Series,
    fila_cfg: pd.Series,
    columnas_cfg: list[str],
    relacion_modelos: pd.DataFrame | None,
    por_hoja_umbrales: dict[str, pd.DataFrame] | None,
    lista_master: pd.DataFrame | None,
    info_clima: dict,
    baseline_year: int,
) -> bool:
    modo_fallo = str(fila_rel.get("Modos de fallo / Modos de parada", "")).strip()
    variable = str(fila_rel.get("Variable", "")).strip()
    estado_limite = str(fila_rel.get("Tipo de impacto", "")).strip() or None
    n_rel = _n_relacion(fila_rel)
    tipo_activo_servicio = (
        str(fila_rel.get("Tipo activo/servicio", "")).strip() or tipo_activo_cfg
    )
    etiqueta_im = titulo_desde_modo(
        modo_fallo,
        variable=variable,
        tipo_impacto=estado_limite,
    )
    motor_id = MOTOR_PI_FRANCOBORDO
    meta = metodologia(motor_id)
    nombre_motor = meta.nombre if meta else motor_id

    inputs_cfg = leer_inputs_config_activo_desde_fila(fila_cfg, columnas_cfg)
    fb_activo = inputs_cfg.get("francobordo")

    regla_modelo = buscar_regla_modelo(
        relacion_modelos,
        modelo_id=motor_id,
        activo=activo_raw,
        modo_fallo=modo_fallo,
        variable=variable,
        estado_limite=estado_limite,
    )
    percentil = regla_modelo.percentil
    regla_ind = regla_modelo.regla_indicador

    referencia_m: float | None = None
    if not (regla_modelo.desde_excel and regla_ind.usa_predefinido):
        if fb_activo is not None:
            referencia_m = fb_activo
        else:
            if por_hoja_umbrales is None:
                resultado.avisos.append(
                    _aviso(
                        nivel="error",
                        codigo="UMBRAL_FALTANTE",
                        activo=activo_resumen,
                        activo_raw=activo_raw,
                        modo_fallo=modo_fallo,
                        variable=variable,
                        tipo_impacto=estado_limite or "",
                        motor_id=motor_id,
                        input_faltante="Fb o umbral",
                        archivo=etiqueta_archivo_fuente("umbrales"),
                        hoja=variable,
                        mensaje=(
                            f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): "
                            f"falta Fb en Configuracion del puerto y no hay datos de umbrales."
                        ),
                        n_relacion=n_rel,
                    )
                )
                return False

            umbral_info = buscar_umbral_francobordo(
                por_hoja_umbrales,
                n_relacion=n_rel,
                tipo_uo=tipo_uo,
                activo=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                tipo_activo_servicio=tipo_activo_servicio,
                lista_master=lista_master,
            )
            if umbral_info is None and not regla_ind.usa_predefinido:
                resultado.avisos.append(
                    _aviso(
                        nivel="error",
                        codigo="UMBRAL_FALTANTE",
                        activo=activo_resumen,
                        activo_raw=activo_raw,
                        modo_fallo=modo_fallo,
                        variable=variable,
                        tipo_impacto=estado_limite or "",
                        motor_id=motor_id,
                        input_faltante="Fb o umbral",
                        archivo=etiqueta_archivo_fuente("umbrales"),
                        hoja=variable,
                        mensaje=(
                            f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): "
                            f"no se encontro umbral (Fb vacio)."
                        ),
                        n_relacion=n_rel,
                    )
                )
                return False
            if umbral_info is not None:
                _, referencia_m = umbral_info
                if referencia_m is None and not regla_ind.usa_predefinido:
                    resultado.avisos.append(
                        _aviso(
                            nivel="error",
                            codigo="UMBRAL_NO_NUMERICO",
                            activo=activo_resumen,
                            activo_raw=activo_raw,
                            modo_fallo=modo_fallo,
                            variable=variable,
                            tipo_impacto=estado_limite or "",
                            motor_id=motor_id,
                            input_faltante="referencia numerica (Fb o umbral)",
                            archivo=etiqueta_archivo_fuente("umbrales"),
                            hoja=variable,
                            mensaje=(
                                f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): "
                                f"la referencia no es numerica."
                            ),
                            n_relacion=n_rel,
                        )
                    )
                    return False

    pestana_clima = variable_clima_francobordo(variable)
    por_variable = info_clima.get("por_variable", {})
    if pestana_clima not in por_variable and variable not in por_variable:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="CLIMA_VARIABLE_FALTANTE",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite or "",
                motor_id=motor_id,
                input_faltante=f"variable climatica '{pestana_clima}'",
                archivo=etiqueta_archivo_fuente("clima"),
                hoja=pestana_clima,
                mensaje=(
                    f"{activo_resumen} - {etiqueta_im}: no hay pestana de "
                    f"'{pestana_clima}' en Indicadores climaticos."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    df_clima, pestana_resuelta = pestana_clima_francobordo(info_clima, variable)
    col_hist, columnas_fut = columnas_oleaje(
        info_clima, baseline_year, variable=pestana_resuelta
    )
    if col_hist is None or not columnas_fut:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="CLIMA_COLUMNAS_FALTANTES",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite or "",
                motor_id=motor_id,
                input_faltante="columnas de escenario climatico",
                archivo=etiqueta_archivo_fuente("clima"),
                hoja=pestana_resuelta,
                mensaje=(
                    f"{activo_resumen} - {etiqueta_im}: faltan columnas clim\u00e1ticas "
                    f"para {pestana_resuelta} (hist\u00f3rico o futuro)."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    fila_ind, _ = clasificar_indicadores_francobordo(
        df_clima,
        referencia_m,
        percentil=percentil,
        tipo_uo=tipo_uo,
        regla=regla_ind,
    )
    if fila_ind is None:
        indicador_txt = (
            regla_ind.indicador
            if regla_ind.usa_predefinido
            else "inundacion costera en un atraque"
        )
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="INDICADOR_CLIMA_FALTANTE",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite or "",
                motor_id=motor_id,
                input_faltante=indicador_txt or "indicador climatico",
                archivo=etiqueta_archivo_fuente("clima"),
                hoja=pestana_resuelta,
                mensaje=(
                    f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): no se encontro "
                    f"indicador '{indicador_txt}' ({percentil})."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    return True


def _validar_fila_precipitacion(
    resultado: ResultadoValidacionPuerto,
    *,
    activo_raw: str,
    activo_resumen: str,
    fila_rel: pd.Series,
    relacion_modelos: pd.DataFrame | None,
    info_clima: dict,
    baseline_year: int,
) -> bool:
    """Valida exceso de precipitación: Excel 4 con 1 o 2 indicadores predefinidos; sin umbral."""
    modo_fallo = str(fila_rel.get("Modos de fallo / Modos de parada", "")).strip()
    variable = str(fila_rel.get("Variable", "")).strip()
    estado_limite = str(fila_rel.get("Tipo de impacto", "")).strip() or None
    n_rel = _n_relacion(fila_rel)
    etiqueta_im = titulo_desde_modo(
        modo_fallo,
        variable=variable,
        tipo_impacto=estado_limite,
    )
    motor_id = MOTOR_PI_PRECIPITACION

    if not tiene_diagrama(motor_id):
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="PROCEDIMIENTO_FLUJO_FALTANTE",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite or "",
                motor_id=motor_id,
                input_faltante="diagrama de procedimiento",
                archivo="Flujo de modelos",
                mensaje=(
                    f"{activo_resumen} - {etiqueta_im}: falta diagrama de procedimiento "
                    f"para PI exceso de precipitación."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    if relacion_modelos is None or getattr(relacion_modelos, "empty", True):
        from core.data_loader import cargar_relacion_modelos_activos_indicadores

        relacion_modelos, _ = cargar_relacion_modelos_activos_indicadores()

    regla_modelo = buscar_regla_modelo(
        relacion_modelos,
        modelo_id=motor_id,
        activo=activo_raw,
        modo_fallo=modo_fallo,
        variable=variable,
        estado_limite=estado_limite,
    )
    indicadores, error_inds = indicadores_predefinidos_precipitacion(
        regla_modelo,
        df_relacion=relacion_modelos,
        modelo_id=motor_id,
        activo=activo_raw,
        modo_fallo=modo_fallo,
        variable=variable,
        estado_limite=estado_limite,
    )
    if error_inds:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="INDICADORES_PREDEFINIDOS_INSUFICIENTES",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite or "",
                motor_id=motor_id,
                input_faltante="1 o 2 indicadores predefinidos",
                archivo=etiqueta_archivo_fuente("relacion_modelos"),
                mensaje=f"{activo_resumen} - {etiqueta_im}: {error_inds}",
                n_relacion=n_rel,
            )
        )
        return False

    pestana_ref = next((i.pestaña for i in indicadores if i.pestaña), "")
    df_clima, pestana_clima = resolver_pestana_clima_precipitacion(
        info_clima,
        variable=variable,
        pestana=pestana_ref,
    )
    col_hist, columnas_fut = columnas_oleaje(
        info_clima, baseline_year, variable=pestana_clima
    )
    if col_hist is None or not columnas_fut:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="COLUMNAS_CLIMA_FALTANTES",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite or "",
                motor_id=motor_id,
                input_faltante="columnas clim\u00e1ticas",
                archivo=etiqueta_archivo_fuente("clima"),
                hoja=pestana_clima,
                mensaje=(
                    f"{activo_resumen} - {etiqueta_im}: no hay columnas clim\u00e1ticas "
                    f"para {pestana_clima}."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    faltantes: list[str] = []
    for ind in indicadores:
        fila_ind, _ = buscar_fila_indicador_predefinido(
            df_clima,
            percentil=regla_modelo.percentil,
            nombre_indicador=ind.indicador,
        )
        if fila_ind is None:
            faltantes.append(ind.indicador)
    if faltantes:
        encontrados = [i.indicador for i in indicadores if i.indicador not in faltantes]
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="INDICADOR_CLIMA_FALTANTE",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite or "",
                motor_id=motor_id,
                input_faltante="indicadores climaticos",
                archivo=etiqueta_archivo_fuente("clima"),
                hoja=pestana_clima,
                mensaje=(
                    f"{activo_resumen} - {etiqueta_im}: faltan indicadores en "
                    f"{pestana_clima} ({regla_modelo.percentil}): "
                    f"{', '.join(f'«{f}»' for f in faltantes)}. "
                    f"Encontrados: "
                    + (
                        ", ".join(f"«{e}»" for e in encontrados)
                        if encontrados
                        else "(ninguno)"
                    )
                    + "."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    return True


def _validar_fila_calado(
    resultado: ResultadoValidacionPuerto,
    *,
    activo_raw: str,
    activo_resumen: str,
    tipo_uo: str,
    tipo_activo_cfg: str | None,
    fila_rel: pd.Series,
    motor_id: str,
    calado_buque: float | None,
    relacion_modelos: pd.DataFrame | None,
    por_hoja_umbrales: dict[str, pd.DataFrame] | None,
    lista_master: pd.DataFrame | None,
    info_clima: dict,
    baseline_year: int,
) -> bool:
    modo_fallo = str(fila_rel.get("Modos de fallo / Modos de parada", "")).strip()
    variable = str(fila_rel.get("Variable", "")).strip()
    estado_limite = str(fila_rel.get("Tipo de impacto", "")).strip() or ""
    n_rel = _n_relacion(fila_rel)
    tipo_activo_servicio = (
        str(fila_rel.get("Tipo activo/servicio", "")).strip() or tipo_activo_cfg
    )
    etiqueta_im = titulo_desde_modo(
        modo_fallo,
        variable=variable,
        tipo_impacto=estado_limite or None,
    )
    meta = metodologia(motor_id)
    nombre_motor = meta.nombre if meta else motor_id

    if calado_buque is None or calado_buque <= 0:
        campo = meta.inputs_activo[0] if meta and meta.inputs_activo else None
        etiqueta_dc = campo.etiqueta if campo else "Dc"
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="INPUT_ACTIVO_FALTANTE",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=motor_id,
                input_faltante=etiqueta_dc,
                archivo=etiqueta_archivo_fuente("config_puerto"),
                hoja="",
                mensaje=(
                    f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): falta "
                    f"{etiqueta_dc} en Configuracion del puerto."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    inputs_form = {"calado_buque": calado_buque, "Dc": calado_buque}

    regla_modelo = buscar_regla_modelo(
        relacion_modelos,
        modelo_id=motor_id,
        activo=activo_raw,
        modo_fallo=modo_fallo,
        variable=variable,
        estado_limite=estado_limite,
    )
    percentil = regla_modelo.percentil
    roles = resolver_indicadores_calado(regla_modelo.indicadores)
    ind_nm = roles.get("nm")
    ind_h0 = roles.get("h0")
    ind_hsed = roles.get("hsedim")

    if ind_nm is None or ind_h0 is None or ind_hsed is None:
        mensaje_ind, codigo_ind = resolver_motivo_y_codigo_diagrama_indicadores(
            motor_id,
            (
                f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): se requieren "
                f"3 indicadores en Relacion_modelos_activos_e_indicadores."
            ),
        )
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo=codigo_ind,
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=motor_id,
                input_faltante="NM, h0 y h sedimentacion",
                archivo=etiqueta_archivo_fuente("relacion_modelos"),
                hoja="",
                mensaje=mensaje_ind,
                n_relacion=n_rel,
            )
        )
        return False

    if por_hoja_umbrales is None:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="UMBRAL_FALTANTE",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=motor_id,
                input_faltante="umbral con Dc",
                archivo=etiqueta_archivo_fuente("umbrales"),
                hoja=variable,
                mensaje=(
                    f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): "
                    f"no hay datos de umbrales."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    umbral_info = buscar_umbral_umbrales(
        por_hoja_umbrales,
        n_relacion=n_rel,
        tipo_uo=tipo_uo,
        activo=activo_raw,
        modo_fallo=modo_fallo,
        variable=variable,
        inputs_formulacion=inputs_form,
        tipo_impacto=estado_limite,
        tipo_activo_servicio=tipo_activo_servicio,
        lista_master=lista_master,
    )
    if umbral_info is None:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="UMBRAL_FALTANTE",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=motor_id,
                input_faltante="umbral (formulacion Dc)",
                archivo=etiqueta_archivo_fuente("umbrales"),
                hoja=variable,
                mensaje=(
                    f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): "
                    f"no se pudo determinar el umbral (revise formulacion con Dc)."
                ),
                n_relacion=n_rel,
            )
        )
        return False
    _, umbral_m = umbral_info
    if umbral_m is None:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="UMBRAL_NO_NUMERICO",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=motor_id,
                input_faltante="umbral numerico",
                archivo=etiqueta_archivo_fuente("umbrales"),
                hoja=variable,
                mensaje=(
                    f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): "
                    f"el umbral no es numerico."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    col_hist, columnas_fut = columnas_nivel_mar(info_clima, baseline_year)
    if col_hist is None or not columnas_fut:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="CLIMA_COLUMNAS_FALTANTES",
                activo=activo_resumen,
                activo_raw=activo_raw,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=motor_id,
                input_faltante="columnas Nivel del mar",
                archivo=etiqueta_archivo_fuente("clima", hoja="Nivel del mar"),
                hoja="Nivel del mar",
                mensaje=(
                    f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): "
                    f"faltan columnas clim\u00e1ticas de Nivel del mar."
                ),
                n_relacion=n_rel,
            )
        )
        return False

    df_clima = dataframe_pestana(info_clima, _pestana_ind(ind_nm))
    for etiqueta_rol, ind in (
        ("indicador 1 (NM)", ind_nm),
        ("indicador 2 (h0)", ind_h0),
        ("indicador 3 (h sedimentacion)", ind_hsed),
    ):
        pest = _pestana_ind(ind)
        df_buscar = dataframe_pestana(info_clima, pest) if "sedimentacion" in etiqueta_rol else df_clima
        fila_ind, _ = buscar_fila_indicador(
            df_buscar,
            nombre_indicador=ind.indicador,
            percentil=percentil,
        )
        if fila_ind is None:
            resultado.avisos.append(
                _aviso(
                    nivel="error",
                    codigo="INDICADOR_CLIMA_FALTANTE",
                    activo=activo_resumen,
                    activo_raw=activo_raw,
                    modo_fallo=modo_fallo,
                    variable=variable,
                    tipo_impacto=estado_limite,
                    motor_id=motor_id,
                    input_faltante=f"{etiqueta_rol}: '{ind.indicador}'",
                    archivo=etiqueta_archivo_fuente("clima", hoja=pest),
                    hoja=pest,
                    mensaje=(
                        f"{activo_resumen} - {nombre_motor} ({etiqueta_im}): "
                        f"no se encontro {etiqueta_rol} '{ind.indicador}' "
                        f"({percentil})."
                    ),
                    n_relacion=n_rel,
                )
            )
            return False

    return True


def _validar_modos_catalogo_extra(
    resultado: ResultadoValidacionPuerto,
    *,
    datos: object,
    activo_raw: str,
    activo_resumen: str,
    impactos: pd.DataFrame,
) -> bool:
    calculable = False
    for _, fila_rel in impactos.iterrows():
        if not fila_tiene_modelo_implementado(fila_rel):
            continue
        if _omitir_modo_no_factible(datos, activo_raw=activo_raw, fila_rel=fila_rel):
            continue
        if es_modo_superacion_umbral(
            fila_rel.get("Modos de fallo / Modos de parada"),
            fila_rel.get("Variable"),
            fila_rel.get("Tipo de impacto"),
        ):
            continue
        if es_modo_exceso_precipitacion(
            fila_rel.get("Modos de fallo / Modos de parada"),
            fila_rel.get("Variable"),
            fila_rel.get("Tipo de impacto"),
        ):
            continue
        if es_modo_falta_calado(
            fila_rel.get("Modos de fallo / Modos de parada"),
            fila_rel.get("Variable"),
        ):
            continue
        if es_modo_falta_francobordo(
            fila_rel.get("Modos de fallo / Modos de parada"),
            fila_rel.get("Variable"),
            fila_rel.get("Tipo de impacto"),
        ):
            continue

        motor_id, entrada = resolver_motor_fila(fila_rel)
        modo_fallo = str(fila_rel.get("Modos de fallo / Modos de parada", "")).strip()
        variable = str(fila_rel.get("Variable", "")).strip()
        tipo_imp = str(fila_rel.get("Tipo de impacto", "")).strip()
        n_rel = _n_relacion(fila_rel)

        if motor_id and motor_registrado(motor_id):
            resultado.avisos.append(
                _aviso(
                    nivel="warning",
                    codigo="VALIDACION_PARCIAL",
                    activo=activo_resumen,
                    activo_raw=activo_raw,
                    modo_fallo=modo_fallo,
                    variable=variable,
                    tipo_impacto=tipo_imp,
                    motor_id=motor_id,
                    input_faltante="validacion detallada",
                    archivo="registro de metodologias (codigo)",
                    mensaje=(
                        f"{activo_resumen} - {modo_fallo}: motor {motor_id} "
                        f"registrado; validacion de inputs no automatizada aun."
                    ),
                    n_relacion=n_rel,
                )
            )
            calculable = True
        elif motor_id:
            nombre_cat = entrada.motor_nombre if entrada else motor_id
            resultado.avisos.append(
                _aviso(
                    nivel="error",
                    codigo="MOTOR_NO_REGISTRADO",
                    activo=activo_resumen,
                    activo_raw=activo_raw,
                    modo_fallo=modo_fallo,
                    variable=variable,
                    tipo_impacto=tipo_imp,
                    motor_id=motor_id,
                    input_faltante="implementacion del modelo",
                    archivo="registro MODELOS_IMPACTO (codigo)",
                    mensaje=(
                        f"{activo_resumen} - {modo_fallo} / {variable}: "
                        f"metodologia '{nombre_cat}' no registrada."
                    ),
                    n_relacion=n_rel,
                )
            )
    return calculable


def validar_puerto_antes_calculo(
    datos: object,
    *,
    baseline_year: int = BASELINE_YEAR,
    filtro_impactos_no_factibles: FiltroImpactosNoFactibles | None = None,
) -> ResultadoValidacionPuerto:
    """Valida inputs/diagramas solo para modos que se van a calcular.

    Orden:
    1. Comprobar datos requeridos de modos que sí correrán.
    2. Si el triple (Activo, Tipo impacto, Modo) está marcado como no factible,
       no validar diagrama/procedimiento ni contarlo como error de cálculo.
    3. Solo entonces exigir diagrama de cálculo / indicadores.
    """
    if filtro_impactos_no_factibles is not None:
        setattr(datos, "filtro_impactos_no_factibles", filtro_impactos_no_factibles)

    resultado = ResultadoValidacionPuerto()

    _validar_fuentes_excel(resultado)

    config_puerto = getattr(datos, "config_puerto", None)
    df_relacion = getattr(datos, "relacion_impactos", None)
    relacion_modelos = getattr(datos, "relacion_modelos", None)
    por_hoja_umbrales = getattr(datos, "umbrales_por_hoja", None)
    lista_master = getattr(datos, "umbrales_lista_master", None)
    info_clima = getattr(datos, "info_clima", None) or {}

    if config_puerto is None or config_puerto.empty:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="CONFIG_VACIA",
                activo="(puerto)",
                activo_raw="",
                input_faltante="activos",
                archivo=etiqueta_archivo_fuente("config_puerto"),
                mensaje="No hay activos en Configuracion del puerto.",
            )
        )
        return resultado

    activos = listar_activos_config(config_puerto)
    resultado.activos_detectados = activos

    if not activos:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="SIN_ACTIVOS",
                activo="(puerto)",
                activo_raw="",
                input_faltante="columna Activo",
                archivo=etiqueta_archivo_fuente("config_puerto"),
                mensaje="No se detectaron activos en Configuracion del puerto.",
            )
        )
        return resultado

    if df_relacion is None or df_relacion.empty:
        resultado.avisos.append(
            _aviso(
                nivel="error",
                codigo="RELACION_VACIA",
                activo="(puerto)",
                activo_raw="",
                input_faltante="ListRelacion impactos-indicador",
                archivo=etiqueta_archivo_fuente(
                    "relacion_ivc",
                    hoja="ListRelacion impactos-indicador",
                ),
                hoja="ListRelacion impactos-indicador",
                mensaje=(
                    "No hay datos en la hoja ListRelacion impactos-indicador "
                    "(modos de fallo por activo)."
                ),
            )
        )
        return resultado

    modos_sin = modos_sin_modelo_puerto(df_relacion, activos)
    resultado.modos_sin_modelo = [
        modo
        for modo in modos_sin
        if not _omitir_modo_no_factible(datos, activo_raw=modo.activo_raw, fila_rel=modo)
    ]
    for modo in resultado.modos_sin_modelo:
        n_rel = f"N {modo.n_relacion}" if modo.n_relacion is not None else "-"
        resultado.avisos.append(
            _aviso(
                nivel="warning",
                codigo="MODO_SIN_METODOLOGIA",
                activo=modo.activo,
                activo_raw=modo.activo_raw,
                modo_fallo=modo.modo_fallo,
                variable=modo.variable,
                tipo_impacto=modo.tipo_impacto,
                input_faltante="metodologia de calculo",
                archivo="registro de metodologias (codigo)",
                hoja="",
                mensaje=(
                    f"Activo «{modo.activo}» detectado en Configuracion del puerto; "
                    f"el modo {n_rel} «{modo.etiqueta}» ({modo.variable or 'sin variable'}, "
                    f"{modo.tipo_impacto or 'sin tipo'}) esta en ListRelacion pero no tiene "
                    f"motor de calculo implementado. No implica que el activo sea desconocido: "
                    f"solo ese modo se omite. Motores actuales: PI superacion de umbral "
                    f"(oleaje/viento/corriente/visibilidad/inundacion), exceso de "
                    f"precipitacion, falta de francobordo y falta de calado."
                ),
                n_relacion=modo.n_relacion,
            )
        )

    columnas_cfg = list(config_puerto.columns)

    for activo_raw in activos:
        activo_resumen = nombre_activo_resumen(activo_raw)
        fila_cfg = fila_configuracion(config_puerto, activo=activo_raw)
        if fila_cfg is None:
            resultado.avisos.append(
                _aviso(
                    nivel="error",
                    codigo="CONFIG_FILA_FALTANTE",
                    activo=activo_resumen,
                    activo_raw=activo_raw,
                    input_faltante="fila del activo",
                    archivo=etiqueta_archivo_fuente("config_puerto"),
                    mensaje=(
                        f"{activo_resumen}: no se encontro fila en "
                        f"Configuracion del puerto."
                    ),
                )
            )
            continue

        col_tipo = columna_por_patron(columnas_cfg, "tipo de uo", "tipo")
        col_tas = columna_por_patron(columnas_cfg, "tipo activo", "servicio")
        tipo_uo = str(fila_cfg[col_tipo]).strip() if col_tipo else ""
        tipo_activo_cfg = (
            str(fila_cfg[col_tas]).strip()
            if col_tas and pd.notna(fila_cfg.get(col_tas))
            else None
        )

        impactos = impactos_por_activo(df_relacion, activo_raw)
        if impactos.empty:
            resultado.avisos.append(
                _aviso(
                    nivel="warning",
                    codigo="SIN_MODOS_IM",
                    activo=activo_resumen,
                    activo_raw=activo_raw,
                    input_faltante="modos de fallo",
                    archivo=etiqueta_archivo_fuente(
                        "relacion_ivc",
                        hoja="ListRelacion impactos-indicador",
                    ),
                    hoja="ListRelacion impactos-indicador",
                    mensaje=(
                        f"Activo «{activo_resumen}» esta en Configuracion del puerto "
                        f"pero no aparece en la hoja ListRelacion impactos-indicador "
                        f"del Excel 2_Relacion_umbrales_y_curvas_de_dano_vs_activos "
                        f"(columna «Activo fisico u Operacional»). Anade al menos una "
                        f"fila con Tipo de impacto, Modos de fallo, Variable y el mismo "
                        f"nombre de activo; sin eso la herramienta no puede calcularlo."
                    ),
                )
            )
            continue

        calado_vals = leer_calado_activo_desde_fila(fila_cfg, columnas_cfg)
        meta_calado = metodologia(MOTOR_PI_CALADO_ELS) or metodologia(MOTOR_PI_CALADO_ELO)
        inputs_calado = meta_calado.inputs_activo if meta_calado else ()
        modos_calado_a_validar: list[tuple[str, object]] = []
        for tipo_imp, motor_calado in (
            ("ELO", MOTOR_PI_CALADO_ELO),
            ("ELS", MOTOR_PI_CALADO_ELS),
            ("ELU", MOTOR_PI_CALADO_ELU),
        ):
            if not motor_registrado(motor_calado):
                continue
            # Sin diagrama = metodologia indefinida: no validar inputs inventados
            # (p. ej. NM/h0/hsedim). Se reporta como sin metodologia mas arriba.
            if not tiene_diagrama(motor_calado):
                continue
            for fila_rel in modos_falta_calado(impactos, tipo_impacto=tipo_imp):
                if _omitir_modo_no_factible(
                    datos, activo_raw=activo_raw, fila_rel=fila_rel
                ):
                    continue
                modos_calado_a_validar.append((motor_calado, fila_rel))
        requiere_calado = bool(modos_calado_a_validar)
        calado_buque = calado_vals.get("calado_buque")
        if requiere_calado:
            for msg in validar_inputs_positivos(calado_vals, inputs_calado):
                resultado.avisos.append(
                    _aviso(
                        nivel="error",
                        codigo="INPUT_ACTIVO_FALTANTE",
                        activo=activo_resumen,
                        activo_raw=activo_raw,
                        motor_id=MOTOR_PI_CALADO_ELS,
                        input_faltante="Dc",
                        archivo=etiqueta_archivo_fuente("config_puerto"),
                        mensaje=f"{activo_resumen}: {msg}",
                    )
                )

        activo_tiene_calculable = False

        for fila_rel in modos_superacion_umbral(impactos):
            if _omitir_modo_no_factible(datos, activo_raw=activo_raw, fila_rel=fila_rel):
                continue
            if _validar_fila_agitacion(
                resultado,
                activo_raw=activo_raw,
                activo_resumen=activo_resumen,
                tipo_uo=tipo_uo,
                tipo_activo_cfg=tipo_activo_cfg,
                fila_rel=fila_rel,
                relacion_modelos=relacion_modelos,
                por_hoja_umbrales=por_hoja_umbrales,
                lista_master=lista_master,
                info_clima=info_clima,
                baseline_year=baseline_year,
                fila_cfg=fila_cfg,
                columnas_cfg=columnas_cfg,
            ):
                activo_tiene_calculable = True

        for fila_rel in modos_exceso_precipitacion(impactos):
            if _omitir_modo_no_factible(datos, activo_raw=activo_raw, fila_rel=fila_rel):
                continue
            if _validar_fila_precipitacion(
                resultado,
                activo_raw=activo_raw,
                activo_resumen=activo_resumen,
                fila_rel=fila_rel,
                relacion_modelos=relacion_modelos,
                info_clima=info_clima,
                baseline_year=baseline_year,
            ):
                activo_tiene_calculable = True

        for motor_calado, fila_rel in modos_calado_a_validar:
            if _validar_fila_calado(
                resultado,
                activo_raw=activo_raw,
                activo_resumen=activo_resumen,
                tipo_uo=tipo_uo,
                tipo_activo_cfg=tipo_activo_cfg,
                fila_rel=fila_rel,
                motor_id=motor_calado,
                calado_buque=calado_buque,
                relacion_modelos=relacion_modelos,
                por_hoja_umbrales=por_hoja_umbrales,
                lista_master=lista_master,
                info_clima=info_clima,
                baseline_year=baseline_year,
            ):
                activo_tiene_calculable = True

        if motor_registrado(MOTOR_PI_FRANCOBORDO):
            for fila_rel in modos_falta_francobordo(impactos):
                if _omitir_modo_no_factible(
                    datos, activo_raw=activo_raw, fila_rel=fila_rel
                ):
                    continue
                if _validar_fila_francobordo(
                    resultado,
                    activo_raw=activo_raw,
                    activo_resumen=activo_resumen,
                    tipo_uo=tipo_uo,
                    tipo_activo_cfg=tipo_activo_cfg,
                    fila_rel=fila_rel,
                    fila_cfg=fila_cfg,
                    columnas_cfg=columnas_cfg,
                    relacion_modelos=relacion_modelos,
                    por_hoja_umbrales=por_hoja_umbrales,
                    lista_master=lista_master,
                    info_clima=info_clima,
                    baseline_year=baseline_year,
                ):
                    activo_tiene_calculable = True

        if _validar_modos_catalogo_extra(
            resultado,
            datos=datos,
            activo_raw=activo_raw,
            activo_resumen=activo_resumen,
            impactos=impactos,
        ):
            activo_tiene_calculable = True

        if activo_tiene_calculable:
            resultado.activos_con_modo_calculable.add(activo_raw)

    return resultado


def resumen_validacion(resultado: ResultadoValidacionPuerto) -> dict[str, int]:
    return {
        "activos": len(resultado.activos_detectados),
        "errores": len(resultado.errores),
        "advertencias": len(resultado.advertencias),
        "modos_sin_modelo": len(resultado.modos_sin_modelo),
        "activos_calculables": len(resultado.activos_con_modo_calculable),
    }


__all__ = [
    "AvisoValidacion",
    "ResultadoValidacionPuerto",
    "resumen_validacion",
    "validar_puerto_antes_calculo",
]
