"""Punto de entrada del modelo de falta de calado (PI ELO / OPEX ELS / CAPEX ELU)."""

from __future__ import annotations

import pandas as pd

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
    construir_pasos_modo_calado_error,
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
from core.schemas.ejecucion import (
    IteracionEjecucion,
    envolver_pasos,
    familia_desde_tipo_impacto,
)


def _mensaje_fila_excel(n_rel: int | None, tipo_impacto: str) -> str:
    if n_rel is None:
        return ""
    return f" (fila Nº {n_rel}, {tipo_impacto})"


def _ejecucion_error(
    *,
    numero: int,
    activo: str,
    modo_fallo: str,
    modo_fallo_excel: str,
    variable: str,
    tipo_impacto: str,
    motor_id: str,
    motivo: str,
    error_code: str,
    inputs_usados: dict | None = None,
    pasos: list | None = None,
) -> IteracionEjecucion:
    # No anteponer diagrama aquí: Motivo y Código deben ir alineados en el caller.
    pasos_ej = envolver_pasos(pasos or [], status="error") if pasos else []
    return IteracionEjecucion(
        numero=numero,
        activo=activo,
        modo_fallo=modo_fallo,
        modo_fallo_excel=modo_fallo_excel,
        variable=variable,
        tipo_impacto=tipo_impacto,
        familia=familia_desde_tipo_impacto(tipo_impacto),
        motor_id=motor_id,
        estado="error",
        motivo=motivo,
        error_code=error_code,
        inputs_usados=dict(inputs_usados or {}),
        pasos=pasos_ej,
    )


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
    """Ejecuta falta de calado para el activo (PI ELO / OPEX ELS / CAPEX ELU), sin atajos cruzados."""
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
    ejecuciones: list[IteracionEjecucion] = []
    hsedim_hist: float | None = None
    pasos_totales: list = []
    familia = familia_desde_tipo_impacto(params.tipo_impacto)
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
        from core.modelos.catalogo_impactos import titulo_desde_modo

        etiqueta_im = titulo_desde_modo(
            modo_fallo,
            variable=variable,
            tipo_impacto=estado_limite,
        )
        n_rel = int(fila_rel["Nº"]) if pd.notna(fila_rel.get("Nº")) else None
        sufijo_fila = _mensaje_fila_excel(n_rel, estado_limite)
        tipo_activo_servicio = str(fila_rel.get("Tipo activo/servicio", "")).strip() or tipo_activo_cfg
        inputs_base = {
            "n_relacion": n_rel,
            "Dc": params.calado_buque,
            "tipo_impacto": estado_limite,
            "variable": variable,
        }

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
            motivo = (
                f"No se pudo determinar el umbral para «{modo_fallo}» / {variable}"
                f"{sufijo_fila}."
            )
            pasos_err = construir_pasos_modo_calado_error(
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
                error_code="UMBRAL_FALTANTE",
                motivo=motivo,
                percentil=percentil,
                origen_regla=regla_modelo.origen,
                fila_excel=regla_modelo.fila,
                num_indicadores=regla_modelo.num_indicadores,
                indicadores=regla_modelo.indicadores,
            )
            pasos_totales.extend(pasos_err)
            ejecuciones.append(_ejecucion_error(
                numero=numero,
                activo=activo_resumen,
                modo_fallo=etiqueta_im,
                modo_fallo_excel=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=params.modelo_id,
                motivo=motivo,
                error_code="UMBRAL_FALTANTE",
                inputs_usados=inputs_base,
                pasos=pasos_err,
            ))
            continue
        umbral_txt, umbral_m = umbral_info
        if umbral_m is None:
            motivo = f"Umbral no numérico ({umbral_txt}){sufijo_fila}."
            pasos_err = construir_pasos_modo_calado_error(
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
                error_code="UMBRAL_NO_NUMERICO",
                motivo=motivo,
                percentil=percentil,
                origen_regla=regla_modelo.origen,
                fila_excel=regla_modelo.fila,
                num_indicadores=regla_modelo.num_indicadores,
                indicadores=regla_modelo.indicadores,
                umbral_txt=umbral_txt,
            )
            pasos_totales.extend(pasos_err)
            ejecuciones.append(_ejecucion_error(
                numero=numero,
                activo=activo_resumen,
                modo_fallo=etiqueta_im,
                modo_fallo_excel=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=params.modelo_id,
                motivo=motivo,
                error_code="UMBRAL_NO_NUMERICO",
                inputs_usados={**inputs_base, "umbral": umbral_txt},
                pasos=pasos_err,
            ))
            continue

        ind_nm = roles.get("nm")
        ind_h0 = roles.get("h0")
        ind_hsed = roles.get("hsedim")
        if ind_nm is None or ind_h0 is None or ind_hsed is None:
            # Lazy: evita ciclo core.modelos.__init__ → registro → pi_calado → flujos
            from core.modelos.flujos import resolver_motivo_y_codigo_diagrama_indicadores

            motivo, error_code = resolver_motivo_y_codigo_diagrama_indicadores(
                params.modelo_id,
                "Faltan 3 indicadores (NM, h0 y h sedimentacion) en "
                "Relacion_modelos_activos_e_indicadores.",
            )
            pasos_err = construir_pasos_modo_calado_error(
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
                error_code=error_code,
                motivo=motivo,
                percentil=percentil,
                origen_regla=regla_modelo.origen,
                fila_excel=regla_modelo.fila,
                num_indicadores=regla_modelo.num_indicadores,
                indicadores=regla_modelo.indicadores,
                umbral_txt=umbral_txt,
                umbral_m=umbral_m,
            )
            pasos_totales.extend(pasos_err)
            ejecuciones.append(_ejecucion_error(
                numero=numero,
                activo=activo_resumen,
                modo_fallo=etiqueta_im,
                modo_fallo_excel=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=params.modelo_id,
                motivo=motivo,
                error_code=error_code,
                inputs_usados={
                    **inputs_base,
                    "percentil": percentil,
                    "origen_regla": regla_modelo.origen,
                },
                pasos=pasos_err,
            ))
            continue

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
            motivo = f"No se encontró indicador 1 «{ind_nm.indicador}» ({percentil})."
            pasos_err = construir_pasos_modo_calado_error(
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
                error_code="INDICADOR_NM_FALTANTE",
                motivo=motivo,
                percentil=percentil,
                origen_regla=regla_modelo.origen,
                fila_excel=regla_modelo.fila,
                num_indicadores=regla_modelo.num_indicadores,
                indicadores=regla_modelo.indicadores,
                umbral_txt=umbral_txt,
                umbral_m=umbral_m,
            )
            pasos_totales.extend(pasos_err)
            ejecuciones.append(_ejecucion_error(
                numero=numero,
                activo=activo_resumen,
                modo_fallo=etiqueta_im,
                modo_fallo_excel=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=params.modelo_id,
                motivo=motivo,
                error_code="INDICADOR_NM_FALTANTE",
                inputs_usados={**inputs_base, "indicador_nm": ind_nm.indicador, "percentil": percentil},
                pasos=pasos_err,
            ))
            continue
        if fila_h0 is None:
            motivo = f"No se encontró indicador 2 «{ind_h0.indicador}» ({percentil})."
            pasos_err = construir_pasos_modo_calado_error(
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
                error_code="INDICADOR_H0_FALTANTE",
                motivo=motivo,
                percentil=percentil,
                origen_regla=regla_modelo.origen,
                fila_excel=regla_modelo.fila,
                num_indicadores=regla_modelo.num_indicadores,
                indicadores=regla_modelo.indicadores,
                umbral_txt=umbral_txt,
                umbral_m=umbral_m,
            )
            pasos_totales.extend(pasos_err)
            ejecuciones.append(_ejecucion_error(
                numero=numero,
                activo=activo_resumen,
                modo_fallo=etiqueta_im,
                modo_fallo_excel=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=params.modelo_id,
                motivo=motivo,
                error_code="INDICADOR_H0_FALTANTE",
                inputs_usados={**inputs_base, "indicador_h0": ind_h0.indicador, "percentil": percentil},
                pasos=pasos_err,
            ))
            continue
        if fila_hsed is None:
            motivo = f"No se encontró indicador 3 «{ind_hsed.indicador}» ({percentil})."
            pasos_err = construir_pasos_modo_calado_error(
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
                error_code="INDICADOR_HSED_FALTANTE",
                motivo=motivo,
                percentil=percentil,
                origen_regla=regla_modelo.origen,
                fila_excel=regla_modelo.fila,
                num_indicadores=regla_modelo.num_indicadores,
                indicadores=regla_modelo.indicadores,
                umbral_txt=umbral_txt,
                umbral_m=umbral_m,
            )
            pasos_totales.extend(pasos_err)
            ejecuciones.append(_ejecucion_error(
                numero=numero,
                activo=activo_resumen,
                modo_fallo=etiqueta_im,
                modo_fallo_excel=modo_fallo,
                variable=variable,
                tipo_impacto=estado_limite,
                motor_id=params.modelo_id,
                motivo=motivo,
                error_code="INDICADOR_HSED_FALTANTE",
                inputs_usados={
                    **inputs_base,
                    "indicador_hsed": ind_hsed.indicador,
                    "percentil": percentil,
                },
                pasos=pasos_err,
            ))
            continue

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

        pasos_modo = construir_pasos_modo_calado(
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
        )
        pasos_totales.extend(pasos_modo)
        pasos_ej = envolver_pasos(pasos_modo)

        indicador_sel = f"h = NM − h₀ − h sedimentación | umbral {umbral_txt}"
        inputs_ok = {
            **inputs_base,
            "umbral": umbral_txt,
            "umbral_m": umbral_m,
            "percentil": percentil,
            "origen_regla": regla_modelo.origen,
            "indicador_nm": ind_nm.indicador,
            "indicador_h0": ind_h0.indicador,
            "indicador_hsed": ind_hsed.indicador,
        }

        ejecuciones.append(IteracionEjecucion(
            numero=numero,
            activo=activo_resumen,
            modo_fallo=etiqueta_im,
            modo_fallo_excel=modo_fallo,
            variable=variable,
            tipo_impacto=estado_limite,
            familia=familia_desde_tipo_impacto(estado_limite) or familia,
            motor_id=params.modelo_id,
            estado="ok",
            umbral=umbral_txt,
            percentil=percentil,
            indicador_seleccionado=indicador_sel,
            origen_regla=regla_modelo.origen,
            inputs_usados=inputs_ok,
            pasos=pasos_ej,
            advertencias=[],
            _tabla_resultado_df=tabla,
        ))

        iteraciones.append(IteracionResultado(
            numero=numero,
            modo_fallo=etiqueta_im,
            variable_climatica=variable,
            umbral=umbral_txt,
            indicador_seleccionado=indicador_sel,
            percentil=percentil,
            origen_regla=regla_modelo.origen,
            indicadores_evaluados=est_nm + est_h0 + est_hsed,
            sintesis_cambios=None,
            advertencias=[],
            _tabla_resultado_df=tabla,
        ))

    meta_ejec = {
        "activo": activo_resumen,
        "tipo_uo": tipo_uo,
        "impactos_asociados": len(impactos),
        "modos_falta_calado": len(modos),
        "modos_ok": sum(1 for e in ejecuciones if e.ok),
        "modos_error": sum(1 for e in ejecuciones if e.estado == "error"),
        "baseline_year": params.baseline_year,
        "calado_buque": params.calado_buque,
        "tipo_impacto": params.tipo_impacto,
        "modelo_id": params.modelo_id,
        "nombre_modelo": nombre_modelo,
        "familia": familia,
    }

    return ResultadoPICalado.desde_calculo(
        metadatos=meta_modelo,
        metadatos_ejecucion=meta_ejec,
        iteraciones=iteraciones,
        ejecuciones=ejecuciones,
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
