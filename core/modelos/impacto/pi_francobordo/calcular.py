# -*- coding: utf-8 -*-
"""Punto de entrada del modelo PI_FRANCOBORDO (falta de francobordo / ELO)."""

from __future__ import annotations

import pandas as pd

from core.config_indicadores import ReglaIndicador
from core.modelos.inputs_activo import leer_inputs_config_activo_desde_fila
from core.relacion_modelos import buscar_regla_modelo
from core.modelos.impacto.pi_agitacion.interpretacion import (
    advertencia_valores_negativos,
    sintesis_cambios,
)
from core.modelos.impacto.pi_agitacion.pasos import (
    PasoResultado,
    ResultadosPorPasos,
    TablaPaso,
    construir_pasos_activo,
    construir_pasos_modo_fallo,
)
from core.modelos.impacto.pi_agitacion.utilidades import (
    columna_por_patron,
    columnas_oleaje,
    etiqueta_indicador_corta,
    fila_configuracion,
    impactos_por_activo,
    nombre_activo_resumen,
    tabla_resultado_indicador,
)
from core.modelos.impacto.pi_francobordo.schemas import (
    METADATOS,
    MODELO_ID,
    IteracionResultado,
    ParametrosEntrada,
    ResultadoPIFrancobordo,
)
from core.modelos.impacto.pi_francobordo.utilidades import (
    buscar_umbral_francobordo,
    clasificar_indicadores_francobordo,
    modos_falta_francobordo,
    pestana_clima_francobordo,
)
from core.modelos.impacto.impactos_no_factibles import (
    MOTIVO_NO_FACTIBLE,
    debe_omitir_im,
)


def _texto_error_indicador(
    variable: str,
    referencia_txt: str,
    percentil: str,
    *,
    regla: ReglaIndicador | None = None,
) -> str:
    if regla and regla.usa_predefinido:
        return (
            f"No se encontro el indicador predefinido '{regla.indicador}' "
            f"({variable}, {percentil}). Revisa Relacion_modelos_activos_e_indicadores.xlsx."
        )
    return (
        f"No se encontro indicador de inundacion costera en un atraque "
        f"(referencia {referencia_txt}, {percentil})."
    )


def calcular(
    datos: object,
    params: ParametrosEntrada | None = None,
    *,
    info_clima: dict | None = None,
    config_puerto: pd.DataFrame | None = None,
    df_relacion: pd.DataFrame | None = None,
    por_hoja_umbrales: dict[str, pd.DataFrame] | None = None,
) -> ResultadoPIFrancobordo:
    """Ejecuta PI falta de francobordo para los modos IM del activo."""
    params = params or ParametrosEntrada()

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
        return ResultadoPIFrancobordo.error(
            "Se requiere la configuracion del puerto (Configuracion_del_puerto.xlsx)."
        )

    fila_cfg = fila_configuracion(
        config_puerto,
        tipo_uo=params.tipo_uo,
        activo=params.activo,
    )
    if fila_cfg is None:
        return ResultadoPIFrancobordo.error(
            "No se encontro fila en la configuracion del puerto."
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
    inputs_cfg = leer_inputs_config_activo_desde_fila(fila_cfg, cols_cfg)
    fb_activo = inputs_cfg.get("francobordo")

    if df_relacion is None or df_relacion.empty:
        from core.data_loader import cargar_relacion_impactos_indicadores

        df_relacion, _ = cargar_relacion_impactos_indicadores()

    impactos = impactos_por_activo(df_relacion, activo_raw)
    modos = modos_falta_francobordo(impactos)
    if not modos:
        return ResultadoPIFrancobordo(
            metadatos=METADATOS,
            ok=True,
            error="",
            iteraciones=[],
            metadatos_ejecucion={
                "activo": activo_resumen,
                "activo_raw": activo_raw,
                "omitido": "sin_modos_falta_francobordo",
            },
        )

    if por_hoja_umbrales is None:
        from core.data_loader import cargar_umbrales_curvas_dano

        por_hoja_umbrales, info_umb = cargar_umbrales_curvas_dano()
        if lista_master is None:
            lista_master = info_umb.get("lista_impactos_indicador")

    pasos_comunes = construir_pasos_activo(
        tipo_uo=tipo_uo,
        activo_raw=activo_raw,
        impactos=impactos,
    )
    pasos_totales: list = list(pasos_comunes)
    iteraciones: list[IteracionResultado] = []
    omitidos_no_factibles: list[dict[str, str]] = []
    relacion_modelos = getattr(datos, "relacion_modelos", None)

    for numero, fila_rel in enumerate(modos, start=1):
        modo_fallo = str(fila_rel.get("Modos de fallo / Modos de parada", "")).strip()
        variable = str(fila_rel.get("Variable", "")).strip()
        estado_limite = str(fila_rel.get("Tipo de impacto", "")).strip() or None
        from core.modelos.catalogo_impactos import titulo_desde_modo

        etiqueta_im = titulo_desde_modo(
            modo_fallo,
            variable=variable,
            tipo_impacto=estado_limite,
        )
        if debe_omitir_im(
            datos,
            activo=activo_raw,
            tipo_impacto=estado_limite or "",
            modo_fallo=modo_fallo,
        ):
            omitidos_no_factibles.append({
                "activo": activo_raw,
                "tipo_impacto": estado_limite or "",
                "modo_fallo": modo_fallo,
            })
            pasos_totales.append(PasoResultado(
                numero=5,
                nombre=f"Iteración por Modos de fallo (IM={numero}) — omitido",
                excel="Configuración de impactos no factibles",
                procedimiento=MOTIVO_NO_FACTIBLE,
                tablas=[TablaPaso(
                    titulo="Omitido (no factible)",
                    columnas=["Activo", "Tipo de impacto", "Modos de fallo / Modos de parada"],
                    filas=[{
                        "Activo": activo_raw,
                        "Tipo de impacto": estado_limite or "",
                        "Modos de fallo / Modos de parada": modo_fallo,
                    }],
                )],
            ))
            continue
        n_rel = int(fila_rel["N\u00ba"]) if pd.notna(fila_rel.get("N\u00ba")) else None
        tipo_activo_servicio = str(fila_rel.get("Tipo activo/servicio", "")).strip() or tipo_activo_cfg

        regla_modelo = buscar_regla_modelo(
            relacion_modelos,
            modelo_id=MODELO_ID,
            activo=activo_raw,
            modo_fallo=modo_fallo,
            variable=variable,
            estado_limite=estado_limite,
        )
        percentil = regla_modelo.percentil
        regla_ind = regla_modelo.regla_indicador

        referencia_txt = ""
        referencia_m: float | None = None
        umbral_m: float | None = None

        if regla_modelo.desde_excel and regla_ind.usa_predefinido:
            referencia_txt = "Indicador fijado en Excel de relacion modelos"
        elif fb_activo is not None:
            referencia_m = fb_activo
            referencia_txt = f"Fb = {fb_activo:g} m"
        else:
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
                return ResultadoPIFrancobordo.error(
                    f"No se pudo determinar referencia (Fb o umbral) para "
                    f"'{modo_fallo}' / {variable}."
                )
            if umbral_info is not None:
                referencia_txt, referencia_m = umbral_info
                umbral_m = referencia_m
            elif regla_ind.usa_predefinido:
                referencia_txt = "Sin referencia numerica"

        df_clima, pestana_clima = pestana_clima_francobordo(info_clima, variable)
        col_hist, columnas_fut = columnas_oleaje(
            info_clima, params.baseline_year, variable=pestana_clima
        )
        if col_hist is None or not columnas_fut:
            return ResultadoPIFrancobordo.error(
                f"No se encontraron columnas climaticas para {pestana_clima}."
            )

        fila_ind, estados = clasificar_indicadores_francobordo(
            df_clima,
            referencia_m,
            percentil=percentil,
            tipo_uo=tipo_uo,
            regla=regla_ind,
        )
        if fila_ind is None:
            return ResultadoPIFrancobordo.error(
                _texto_error_indicador(
                    variable, referencia_txt, percentil, regla=regla_ind
                )
            )

        tabla = tabla_resultado_indicador(
            fila_ind,
            col_hist,
            columnas_fut,
            variable=pestana_clima,
        )
        advertencia = advertencia_valores_negativos(tabla)
        resumen_cambios = sintesis_cambios(tabla)
        advertencias = [advertencia] if advertencia else []

        pasos_modo = construir_pasos_modo_fallo(
            numero_iteracion=numero,
            tipo_uo=tipo_uo,
            activo_raw=activo_raw,
            modo_fallo=etiqueta_im,
            variable=variable,
            umbral_m=umbral_m if umbral_m is not None else referencia_m,
            umbral_txt=referencia_txt,
            percentil=percentil,
            origen_regla=regla_modelo.origen,
            indicador_predefinido=regla_ind.usa_predefinido,
            indicador_config=regla_ind.indicador if regla_ind.usa_predefinido else None,
            fila_excel=regla_modelo.fila,
            fila_ind=fila_ind,
            col_hist=col_hist,
            columnas_fut=columnas_fut,
            tabla_variacion=tabla,
        )
        pasos_totales.extend(pasos_modo)

        if regla_ind.usa_predefinido:
            indicador_resumen = regla_ind.etiqueta_mostrar()
        else:
            seleccionados = [e for e in estados if e.seleccionado]
            if seleccionados:
                indicador_resumen = seleccionados[0].nombre
            elif referencia_m is not None:
                indicador_resumen = (
                    f"Inundacion costera en un atraque ≥ {referencia_m:g} m"
                )
            else:
                indicador_resumen = etiqueta_indicador_corta(umbral_m, variable=variable)

        iteraciones.append(IteracionResultado(
            numero=numero,
            modo_fallo=etiqueta_im,
            variable_climatica=variable,
            umbral=referencia_txt,
            indicador_seleccionado=indicador_resumen,
            percentil=percentil,
            origen_regla=regla_modelo.origen,
            indicadores_evaluados=estados,
            sintesis_cambios=resumen_cambios,
            advertencias=advertencias,
            _tabla_resultado_df=tabla,
        ))

    meta_ejec = {
        "activo": activo_resumen,
        "tipo_uo": tipo_uo,
        "modelo_id": MODELO_ID,
        "fb": fb_activo,
        "origen_reglas": {
            it.variable_climatica: it.origen_regla for it in iteraciones
        },
        "fuente_percentil_indicador": (
            datos.rutas.get("relacion_modelos", "")
            if hasattr(datos, "rutas")
            else ""
        ),
        "impactos_asociados": len(impactos),
        "modos_falta_francobordo": len(iteraciones),
        "modos_omitidos_no_factibles": omitidos_no_factibles,
        "baseline_year": params.baseline_year,
    }
    if not iteraciones:
        return ResultadoPIFrancobordo(
            metadatos=METADATOS,
            ok=True,
            error="",
            iteraciones=[],
            metadatos_ejecucion={
                **meta_ejec,
                "activo_raw": activo_raw,
                "omitido": "todos_impactos_no_factibles",
            },
            resultados_por_pasos=ResultadosPorPasos(
                modelo_id=MODELO_ID,
                pasos=pasos_totales,
            ),
        )

    return ResultadoPIFrancobordo.desde_calculo(
        metadatos_ejecucion=meta_ejec,
        iteraciones=iteraciones,
        resultados_por_pasos=ResultadosPorPasos(
            modelo_id=MODELO_ID,
            pasos=pasos_totales,
        ),
    )


__all__ = [
    "METADATOS",
    "ParametrosEntrada",
    "ResultadoPIFrancobordo",
    "calcular",
]
