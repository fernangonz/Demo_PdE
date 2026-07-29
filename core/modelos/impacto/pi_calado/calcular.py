"""Punto de entrada del modelo de falta de calado (OPEX ELS / CAPEX ELU)."""

from __future__ import annotations

import pandas as pd

from core.modelos.catalogo_impactos import titulo_desde_modo
from core.relacion_modelos import buscar_regla_modelo
from core.modelos.impacto.pi_agitacion.utilidades import (
    buscar_umbral_umbrales,
    columna_por_patron,
    fila_configuracion,
    impactos_por_activo,
    nombre_activo_resumen,
)
from core.modelos.impacto.pi_agitacion.schemas import IteracionResultado
from core.modelos.impacto.pi_calado.schemas import (
    ParametrosEntrada,
    ResultadoPICalado,
    metadatos_para_tipo_impacto,
    nombre_modelo_para_tipo_impacto,
)
from core.modelos.impacto.pi_calado.pasos import (
    ResultadosPorPasos,
    construir_pasos_activo_calado,
    construir_pasos_modo_calado,
)
from core.modelos.impacto.pi_calado.utilidades import (
    buscar_fila_indicador,
    columnas_nivel_mar,
    construir_tabla_calado,
    dataframe_pestana,
    modos_falta_calado,
    resolver_indicadores_calado,
    valor_columna,
)


def _mensaje_fila_excel(n_rel: int | None, tipo_impacto: str) -> str:
    if n_rel is None:
        return ""
    return f" (fila Nº {n_rel}, {tipo_impacto})"


def calcular(
    datos: object,
    params: ParametrosEntrada | None = None,
    *,
    info_clima: dict | None = None,
    config_puerto: pd.DataFrame | None = None,
    df_relacion: pd.DataFrame | None = None,
    por_hoja_umbrales: dict[str, pd.DataFrame] | None = None,
    incluir_pasos_comunes: bool = True,
) -> ResultadoPICalado:
    """Ejecuta falta de calado para el activo (OPEX ELS o CAPEX ELU), sin atajos cruzados."""
    params = params or ParametrosEntrada()
    meta_modelo = metadatos_para_tipo_impacto(params.tipo_impacto)
    nombre_modelo = nombre_modelo_para_tipo_impacto(params.tipo_impacto)

    if info_clima is None:
        info_clima = getattr(datos, "info_clima", None) or datos  # type: ignore[assignment]
    if config_puerto is None:
        config_puerto = getattr(datos, "config_puerto", None)
    if df_relacion is None:
        df_relacion = getattr(datos, "relacion_impactos", None)
    if por_hoja_umbrales is None:
        por_hoja_umbrales = getattr(datos, "umbrales_por_hoja", None)
    lista_master = getattr(datos, "umbrales_lista_master", None)

    if config_puerto is None or config_puerto.empty:
        return ResultadoPICalado.error(
            "Se requiere la configuración del puerto (Configuración_del_puerto.xlsx).",
            metadatos=meta_modelo,
        )

    if params.calado_buque is None or params.calado_buque <= 0:
        return ResultadoPICalado.error(
            "Dc (m): obligatorio, valor numerico positivo.",
            metadatos=meta_modelo,
        )

    fila_cfg = fila_configuracion(
        config_puerto,
        tipo_uo=params.tipo_uo,
        activo=params.activo,
    )
    if fila_cfg is None:
        return ResultadoPICalado.error(
            "No se encontró fila en la configuración del puerto.",
            metadatos=meta_modelo,
        )

    cols_cfg = list(config_puerto.columns)
    col_activo = columna_por_patron(cols_cfg, "activo fisico u operacional", "activo")
    col_tipo = columna_por_patron(cols_cfg, "tipo de uo", "tipo")
    col_tas = columna_por_patron(cols_cfg, "tipo activo", "servicio")
    activo_raw = str(fila_cfg[col_activo]).strip() if col_activo else (params.activo or "")
    activo_resumen = nombre_activo_resumen(activo_raw)
    tipo_uo = str(fila_cfg[col_tipo]).strip() if col_tipo else (params.tipo_uo or "")
    tipo_activo_cfg = (
        str(fila_cfg[col_tas]).strip() if col_tas and pd.notna(fila_cfg.get(col_tas)) else None
    )

    if df_relacion is None or df_relacion.empty:
        from core.data_loader import cargar_relacion_impactos_indicadores

        df_relacion, _ = cargar_relacion_impactos_indicadores()

    impactos = impactos_por_activo(df_relacion, activo_raw)
    modos = modos_falta_calado(impactos, tipo_impacto=params.tipo_impacto)
    if not modos:
        return ResultadoPICalado.error(
            f"No hay modo «Falta de Calado» ({params.tipo_impacto}) "
            f"para el activo «{activo_resumen}» en ListRelacion impactos-indicador "
            f"(Relación umbrales y curvas de daño vs activos).",
            metadatos=meta_modelo,
        )

    if por_hoja_umbrales is None:
        from core.data_loader import cargar_umbrales_curvas_dano

        por_hoja_umbrales, info_umb = cargar_umbrales_curvas_dano()
        if lista_master is None:
            lista_master = info_umb.get("lista_impactos_indicador")

    relacion_modelos = getattr(datos, "relacion_modelos", None)
    inputs_form = {
        "calado_buque": params.calado_buque,
        "Dc": params.calado_buque,
    }

    col_hist, columnas_fut = columnas_nivel_mar(info_clima, params.baseline_year)
    if col_hist is None or not columnas_fut:
        return ResultadoPICalado.error(
            "No se encontraron columnas climáticas para Nivel del mar.",
            metadatos=meta_modelo,
        )

    iteraciones: list[IteracionResultado] = []
    hsedim_hist: float | None = None
    pasos_totales: list = []
    if incluir_pasos_comunes:
        pasos_totales.extend(construir_pasos_activo_calado(
            nombre_modelo=nombre_modelo,
            tipo_impacto=params.tipo_impacto,
            tipo_uo=tipo_uo,
            activo_raw=activo_raw,
            calado_buque=params.calado_buque,
            filas_im=modos,
        ))

    for numero, fila_rel in enumerate(modos, start=1):
        modo_fallo = str(fila_rel.get("Modos de fallo / Modos de parada", "")).strip()
        variable = str(fila_rel.get("Variable", "")).strip()
        estado_limite = str(fila_rel.get("Tipo de impacto", "")).strip() or params.tipo_impacto
        etiqueta_im = titulo_desde_modo(
            modo_fallo,
            variable=variable,
            tipo_impacto=estado_limite,
        )
        n_rel = int(fila_rel["Nº"]) if pd.notna(fila_rel.get("Nº")) else None
        sufijo_fila = _mensaje_fila_excel(n_rel, estado_limite)
        tipo_activo_servicio = str(fila_rel.get("Tipo activo/servicio", "")).strip() or tipo_activo_cfg

        regla_modelo = buscar_regla_modelo(
            relacion_modelos,
            modelo_id=params.modelo_id,
            activo=activo_raw,
            modo_fallo=modo_fallo,
            variable=variable,
            estado_limite=estado_limite,
        )
        percentil = regla_modelo.percentil
        roles = resolver_indicadores_calado(regla_modelo.indicadores)

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
            return ResultadoPICalado.error(
                f"{nombre_modelo}: no se pudo determinar el umbral para "
                f"«{modo_fallo}» / {variable}{sufijo_fila}. "
                "Revise Relación umbrales y curvas de daño vs activos "
                f"(Umbral General o columna del Tipo UO, formulación con Dc).",
                metadatos=meta_modelo,
            )
        umbral_txt, umbral_m = umbral_info
        if umbral_m is None:
            return ResultadoPICalado.error(
                f"{nombre_modelo}: umbral no numérico para «{modo_fallo}» "
                f"({umbral_txt}){sufijo_fila}.",
                metadatos=meta_modelo,
            )

        ind_nm = roles.get("nm")
        ind_h0 = roles.get("h0")
        ind_hsed = roles.get("hsedim")
        if ind_nm is None or ind_h0 is None or ind_hsed is None:
            return ResultadoPICalado.error(
                f"{nombre_modelo}: se requieren 3 indicadores (NM, h0 y h sedimentacion) "
                f"en Relacion_modelos_activos_e_indicadores para "
                f"«{modo_fallo}» / {variable} / {estado_limite}{sufijo_fila}. "
                f"Configure la fila del modelo con tipo de impacto {estado_limite}; "
                "no se reutilizan reglas de otro tipo.",
                metadatos=meta_modelo,
            )

        df_clima = dataframe_pestana(info_clima, ind_nm.pestaña or "Nivel del mar")

        fila_nm, est_nm = buscar_fila_indicador(
            df_clima, nombre_indicador=ind_nm.indicador, percentil=percentil
        )
        fila_h0, est_h0 = buscar_fila_indicador(
            df_clima, nombre_indicador=ind_h0.indicador, percentil=percentil
        )
        df_hsed = dataframe_pestana(info_clima, ind_hsed.pestaña or ind_nm.pestaña or "Nivel del mar")
        fila_hsed, est_hsed = buscar_fila_indicador(
            df_hsed, nombre_indicador=ind_hsed.indicador, percentil=percentil
        )
        if fila_nm is None:
            return ResultadoPICalado.error(
                f"{nombre_modelo}: no se encontró indicador 1 «{ind_nm.indicador}» ({percentil}).",
                metadatos=meta_modelo,
            )
        if fila_h0 is None:
            return ResultadoPICalado.error(
                f"{nombre_modelo}: no se encontró indicador 2 «{ind_h0.indicador}» ({percentil}).",
                metadatos=meta_modelo,
            )
        if fila_hsed is None:
            return ResultadoPICalado.error(
                f"{nombre_modelo}: no se encontró indicador 3 «{ind_hsed.indicador}» ({percentil}).",
                metadatos=meta_modelo,
            )

        tabla = construir_tabla_calado(
            fila_nm=fila_nm,
            fila_h0=fila_h0,
            fila_hsedim=fila_hsed,
            umbral=umbral_m,
            umbral_txt=umbral_txt,
            col_hist=col_hist,
            columnas_fut=columnas_fut,
        )
        if hsedim_hist is None:
            hsedim_hist = valor_columna(fila_hsed, col_hist)

        pasos_totales.extend(construir_pasos_modo_calado(
            numero_iteracion=numero,
            tipo_uo=tipo_uo,
            activo_raw=activo_raw,
            modo_fallo=etiqueta_im,
            modo_fallo_excel=modo_fallo,
            etiqueta_im=etiqueta_im,
            nombre_modelo=nombre_modelo,
            variable=variable,
            tipo_impacto=estado_limite,
            n_relacion=n_rel,
            calado_buque=params.calado_buque,
            umbral_m=umbral_m,
            umbral_txt=umbral_txt,
            percentil=percentil,
            origen_regla=regla_modelo.origen,
            fila_excel=regla_modelo.fila,
            num_indicadores=regla_modelo.num_indicadores,
            indicadores=regla_modelo.indicadores,
            ind_nm=ind_nm,
            ind_h0=ind_h0,
            ind_hsed=ind_hsed,
            fila_nm=fila_nm,
            fila_h0=fila_h0,
            fila_hsed=fila_hsed,
            col_hist=col_hist,
            columnas_fut=columnas_fut,
            tabla_resultado=tabla,
            indicadores_clima=est_nm + est_h0 + est_hsed,
        ))

        iteraciones.append(IteracionResultado(
            numero=numero,
            modo_fallo=etiqueta_im,
            variable_climatica=variable,
            umbral=umbral_txt,
            indicador_seleccionado=(
                f"h = NM − h₀ − h sedimentación | umbral {umbral_txt}"
            ),
            percentil=percentil,
            origen_regla=regla_modelo.origen,
            indicadores_evaluados=est_nm + est_h0 + est_hsed,
            sintesis_cambios=None,
            advertencias=[],
            _tabla_resultado_df=tabla,
        ))

    return ResultadoPICalado.desde_calculo(
        metadatos=meta_modelo,
        metadatos_ejecucion={
            "activo": activo_resumen,
            "tipo_uo": tipo_uo,
            "impactos_asociados": len(impactos),
            "modos_falta_calado": len(iteraciones),
            "baseline_year": params.baseline_year,
            "calado_buque": params.calado_buque,
            "tipo_impacto": params.tipo_impacto,
            "modelo_id": params.modelo_id,
            "nombre_modelo": nombre_modelo,
        },
        iteraciones=iteraciones,
        resultados_por_pasos=ResultadosPorPasos(
            modelo_id=params.modelo_id,
            pasos=pasos_totales,
        ),
        hsedimentacion_historico=hsedim_hist,
    )


__all__ = [
    "ParametrosEntrada",
    "ResultadoPICalado",
    "calcular",
]
