"""Punto de entrada del modelo PI_AGITACION (PI superación de umbral).

Uso desde otra interfaz::

    from core.datos.repositorio import RepositorioDatos
    from core.modelos.impacto.pi_agitacion import calcular, ParametrosEntrada

    datos = RepositorioDatos.cargar()
    resultado = calcular(datos, ParametrosEntrada())
    payload = resultado.to_dict()  # JSON-ready
"""

from __future__ import annotations

import pandas as pd

from core.relacion_modelos import buscar_regla_modelo
from core.config_indicadores import ReglaIndicador
from core.modelos.inputs_activo import leer_inputs_config_activo_desde_fila
from core.modelos.impacto.pi_agitacion.interpretacion import (
    advertencia_valores_negativos,
    sintesis_cambios,
)
from core.modelos.impacto.pi_agitacion.utilidades import (
    buscar_umbral_umbrales,
    clasificar_indicadores_umbral,
    columna_por_patron,
    columnas_oleaje,
    es_modo_inundacion_costera,
    etiqueta_indicador_corta,
    fila_configuracion,
    impactos_por_activo,
    modos_superacion_umbral,
    nombre_activo_resumen,
    tabla_resultado_indicador,
)
from core.modelos.impacto.pi_francobordo.utilidades import (
    clasificar_indicadores_francobordo,
    pestana_clima_francobordo,
)
from core.modelos.impacto.impactos_no_factibles import (
    MOTIVO_NO_FACTIBLE,
    debe_omitir_im,
)
from core.modelos.impacto.mensajes_indicador import (
    conteos_busqueda_indicador,
    mensaje_indicador_no_encontrado,
    modo_seleccion_desde_regla,
    nombre_excel_clima,
    patron_busqueda_indicador,
)
from core.modelos.impacto.pi_agitacion.pasos import (
    PasoResultado,
    ResultadosPorPasos,
    TablaPaso,
    construir_pasos_activo,
    construir_pasos_modo_fallo,
)
from core.modelos.impacto.pi_agitacion.schemas import (
    METADATOS,
    MODELO_ID,
    IteracionResultado,
    ParametrosEntrada,
    ResultadoPIAgitacion,
)


def _texto_error_indicador(
    *,
    datos: object,
    df_clima: pd.DataFrame,
    hoja: str,
    variable: str,
    percentil: str,
    umbral_txt: str = "",
    umbral_m: float | None = None,
    regla: ReglaIndicador | None = None,
    inundacion_fb: bool = False,
    origen_referencia: str = "",
    referencia_m: float | None = None,
    n_candidatos: int | None = None,
) -> str:
    n_hoja, n_pct = conteos_busqueda_indicador(df_clima, percentil=percentil)
    return mensaje_indicador_no_encontrado(
        archivo=nombre_excel_clima(datos),
        hoja=hoja,
        percentil=percentil,
        patron=patron_busqueda_indicador(
            regla=regla,
            umbral_txt=umbral_txt,
            umbral_m=umbral_m,
            inundacion_fb=inundacion_fb,
            referencia_m=referencia_m,
            variable=variable,
        ),
        modo_seleccion=modo_seleccion_desde_regla(
            regla,
            inundacion_fb=inundacion_fb,
            origen_referencia=origen_referencia,
        ),
        variable=variable,
        n_filas_hoja=n_hoja,
        n_tras_percentil=n_pct,
        n_candidatos=n_candidatos if n_candidatos is not None else 0,
    )


def _iteracion_error(
    *,
    numero: int,
    etiqueta_im: str,
    variable: str,
    umbral_txt: str,
    percentil: str,
    origen_regla: str,
    motivo: str,
    error_code: str = "INDICADOR_CLIMA_FALTANTE",
    estados: list | None = None,
) -> IteracionResultado:
    return IteracionResultado(
        numero=numero,
        modo_fallo=etiqueta_im,
        variable_climatica=variable,
        umbral=umbral_txt or "—",
        indicador_seleccionado="—",
        percentil=percentil,
        origen_regla=origen_regla,
        indicadores_evaluados=estados or [],
        advertencias=[motivo],
        estado="error",
        motivo=motivo,
        error_code=error_code,
    )


def calcular(
    datos: object,
    params: ParametrosEntrada | None = None,
    *,
    info_clima: dict | None = None,
    config_puerto: pd.DataFrame | None = None,
    df_relacion: pd.DataFrame | None = None,
    por_hoja_umbrales: dict[str, pd.DataFrame] | None = None,
) -> ResultadoPIAgitacion:
    """Ejecuta PI superación de umbral de forma autónoma.

    Recorre los modos de fallo del activo (exceso de oleaje, viento, corriente y visibilidad),
    volviendo al paso 5 tras cada iteración IM según el diagrama de flujo.
    """
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
        return ResultadoPIAgitacion.error(
            "Se requiere la configuración del puerto (Configuración_del_puerto.xlsx)."
        )

    fila_cfg = fila_configuracion(
        config_puerto,
        tipo_uo=params.tipo_uo,
        activo=params.activo,
    )
    if fila_cfg is None:
        return ResultadoPIAgitacion.error("No se encontró fila en la configuración del puerto.")

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
    modos = modos_superacion_umbral(impactos)
    if not modos:
        # Activo sin modos PI aplicables: omitir en silencio (no es un error).
        return ResultadoPIAgitacion(
            metadatos=METADATOS,
            ok=True,
            error="",
            iteraciones=[],
            metadatos_ejecucion={
                "activo": activo_resumen,
                "activo_raw": activo_raw,
                "omitido": "sin_modos_superacion_umbral",
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
        n_rel = int(fila_rel["Nº"]) if pd.notna(fila_rel.get("Nº")) else None
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
        es_inundacion = es_modo_inundacion_costera(
            modo_fallo, variable, estado_limite
        )

        umbral_txt = ""
        umbral_m: float | None = None
        referencia_m: float | None = None
        origen_referencia = ""
        pestana_clima = variable

        if es_inundacion:
            # Caso especial: referencia = Fb; si Fb vacío → umbral Excel 2 (como francobordo).
            if regla_modelo.desde_excel and regla_ind.usa_predefinido:
                umbral_txt = "Indicador fijado en Excel de relación modelos"
                origen_referencia = "predefinido"
            elif fb_activo is not None:
                referencia_m = fb_activo
                umbral_m = fb_activo
                umbral_txt = f"Fb = {fb_activo:g} m"
                origen_referencia = "Fb"
            else:
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
                    iteraciones.append(_iteracion_error(
                        numero=numero,
                        etiqueta_im=etiqueta_im,
                        variable=variable,
                        umbral_txt=umbral_txt,
                        percentil=percentil,
                        origen_regla=regla_modelo.origen,
                        motivo=(
                            f"No se pudo determinar referencia (Fb o umbral) para "
                            f"«{modo_fallo}» / {variable}. "
                            f"Fb vacío en Configuración del puerto y sin umbral en Excel 2."
                        ),
                        error_code="REFERENCIA_FB_UMBRAL_FALTANTE",
                    ))
                    continue
                if umbral_info is not None:
                    umbral_txt, umbral_m = umbral_info
                    referencia_m = umbral_m
                    origen_referencia = "umbral (Fb vacío)"
                elif regla_ind.usa_predefinido:
                    umbral_txt = "Sin referencia numérica"
                    origen_referencia = "predefinido"

            df_clima, pestana_clima = pestana_clima_francobordo(info_clima, variable)
            col_hist, columnas_fut = columnas_oleaje(
                info_clima, params.baseline_year, variable=pestana_clima
            )
            if col_hist is None or not columnas_fut:
                iteraciones.append(_iteracion_error(
                    numero=numero,
                    etiqueta_im=etiqueta_im,
                    variable=variable,
                    umbral_txt=umbral_txt,
                    percentil=percentil,
                    origen_regla=regla_modelo.origen,
                    motivo=(
                        f"No se encontraron columnas climáticas para {pestana_clima} "
                        f"en {nombre_excel_clima(datos)}."
                    ),
                    error_code="COLUMNAS_CLIMA_FALTANTES",
                ))
                continue

            fila_ind, estados = clasificar_indicadores_francobordo(
                df_clima,
                referencia_m,
                percentil=percentil,
                tipo_uo=tipo_uo,
                regla=regla_ind,
            )
            if fila_ind is None:
                iteraciones.append(_iteracion_error(
                    numero=numero,
                    etiqueta_im=etiqueta_im,
                    variable=variable,
                    umbral_txt=umbral_txt,
                    percentil=percentil,
                    origen_regla=regla_modelo.origen,
                    motivo=_texto_error_indicador(
                        datos=datos,
                        df_clima=df_clima,
                        hoja=pestana_clima,
                        variable=variable,
                        percentil=percentil,
                        umbral_txt=umbral_txt,
                        umbral_m=umbral_m,
                        regla=regla_ind,
                        inundacion_fb=True,
                        origen_referencia=origen_referencia,
                        referencia_m=referencia_m,
                    ),
                    estados=estados,
                ))
                continue
        else:
            if regla_modelo.desde_excel and regla_ind.usa_predefinido:
                umbral_txt = "Indicador fijado en Excel de relación modelos"
            else:
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
                    iteraciones.append(_iteracion_error(
                        numero=numero,
                        etiqueta_im=etiqueta_im,
                        variable=variable,
                        umbral_txt=umbral_txt,
                        percentil=percentil,
                        origen_regla=regla_modelo.origen,
                        motivo=(
                            f"No se pudo determinar el umbral para "
                            f"«{modo_fallo}» / {variable}."
                        ),
                        error_code="UMBRAL_FALTANTE",
                    ))
                    continue
                if umbral_info is not None:
                    umbral_txt, umbral_m = umbral_info
                elif regla_ind.usa_predefinido:
                    umbral_txt = "Sin umbral numérico"

            df_clima = info_clima["por_variable"].get(variable, {}).get("df", pd.DataFrame())
            pestana_clima = variable
            col_hist, columnas_fut = columnas_oleaje(
                info_clima, params.baseline_year, variable=variable
            )
            if col_hist is None or not columnas_fut:
                iteraciones.append(_iteracion_error(
                    numero=numero,
                    etiqueta_im=etiqueta_im,
                    variable=variable,
                    umbral_txt=umbral_txt,
                    percentil=percentil,
                    origen_regla=regla_modelo.origen,
                    motivo=(
                        f"No se encontraron columnas climáticas para {variable} "
                        f"en {nombre_excel_clima(datos)}."
                    ),
                    error_code="COLUMNAS_CLIMA_FALTANTES",
                ))
                continue

            fila_ind, estados = clasificar_indicadores_umbral(
                df_clima,
                umbral_m,
                percentil=percentil,
                variable=variable,
                regla=regla_ind,
            )
            if fila_ind is None:
                iteraciones.append(_iteracion_error(
                    numero=numero,
                    etiqueta_im=etiqueta_im,
                    variable=variable,
                    umbral_txt=umbral_txt,
                    percentil=percentil,
                    origen_regla=regla_modelo.origen,
                    motivo=_texto_error_indicador(
                        datos=datos,
                        df_clima=df_clima,
                        hoja=pestana_clima,
                        variable=variable,
                        percentil=percentil,
                        umbral_txt=umbral_txt,
                        umbral_m=umbral_m,
                        regla=regla_ind,
                    ),
                    estados=estados,
                ))
                continue

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
            umbral_m=umbral_m,
            umbral_txt=umbral_txt,
            percentil=percentil,
            origen_regla=regla_modelo.origen,
            indicador_predefinido=regla_ind.usa_predefinido,
            indicador_config=regla_ind.indicador if regla_ind.usa_predefinido else None,
            fila_excel=regla_modelo.fila,
            fila_ind=fila_ind,
            col_hist=col_hist,
            columnas_fut=columnas_fut,
            tabla_variacion=tabla,
            seleccion_especial=(
                "Fb / inundación costera en atraque"
                if es_inundacion and not regla_ind.usa_predefinido
                else None
            ),
            nota_paso6=(
                (
                    f"Referencia desde {origen_referencia}. "
                    "Paso 6 de umbral clásico omitido si Fb tiene valor."
                    if origen_referencia == "Fb"
                    else (
                        f"Fb vacío → umbral Excel 2 como referencia "
                        f"({origen_referencia})."
                        if origen_referencia.startswith("umbral")
                        else ""
                    )
                )
                if es_inundacion
                else None
            ),
        )
        pasos_totales.extend(pasos_modo)

        if regla_ind.usa_predefinido:
            indicador_resumen = regla_ind.etiqueta_mostrar()
        elif es_inundacion:
            seleccionados = [e for e in estados if e.seleccionado]
            if seleccionados:
                indicador_resumen = seleccionados[0].nombre
            elif referencia_m is not None:
                indicador_resumen = (
                    f"Inundacion costera en un atraque ≥ {referencia_m:g} m"
                )
            else:
                indicador_resumen = etiqueta_indicador_corta(umbral_m, variable=variable)
        else:
            indicador_resumen = etiqueta_indicador_corta(umbral_m, variable=variable)

        iteraciones.append(IteracionResultado(
            numero=numero,
            modo_fallo=etiqueta_im,
            variable_climatica=variable,
            umbral=umbral_txt,
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
        "modos_superacion_umbral": len(iteraciones),
        "modos_omitidos_no_factibles": omitidos_no_factibles,
        "baseline_year": params.baseline_year,
    }
    if not iteraciones:
        # Todos los modos aplicables estaban marcados como no factibles.
        return ResultadoPIAgitacion(
            metadatos=METADATOS,
            ok=True,
            error="",
            iteraciones=[],
            metadatos_ejecucion={
                **meta_ejec,
                "activo_raw": activo_raw,
                "omitido": "todos_impactos_no_factibles",
            },
            resultados_por_pasos=ResultadosPorPasos(pasos=pasos_totales),
        )

    return ResultadoPIAgitacion.desde_calculo(
        metadatos_ejecucion=meta_ejec,
        iteraciones=iteraciones,
        resultados_por_pasos=ResultadosPorPasos(pasos=pasos_totales),
    )


__all__ = [
    "METADATOS",
    "ParametrosEntrada",
    "ResultadoPIAgitacion",
    "calcular",
]
