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
from core.modelos.impacto.pi_agitacion.interpretacion import (
    advertencia_valores_negativos,
    sintesis_cambios,
)
from core.modelos.impacto.pi_agitacion.pasos import (
    ResultadosPorPasos,
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
from core.modelos.impacto.pi_agitacion.utilidades import (
    buscar_umbral_umbrales,
    clasificar_indicadores_umbral,
    columna_por_patron,
    columnas_oleaje,
    etiqueta_indicador_corta,
    fila_configuracion,
    impactos_por_activo,
    modos_superacion_umbral,
    nombre_activo_resumen,
    tabla_resultado_indicador,
)


def _texto_error_indicador(
    variable: str,
    umbral_txt: str,
    percentil: str,
    *,
    regla: ReglaIndicador | None = None,
) -> str:
    if regla and regla.usa_predefinido:
        return (
            f"No se encontró el indicador predefinido «{regla.indicador}» "
            f"({variable}, {percentil}). Revisa Relacion_modelos_activos_e_indicadores.xlsx."
        )
    if variable.lower() == "viento":
        return f"No se encontró indicador de viento ({umbral_txt}, {percentil})."
    if variable.lower() == "corriente":
        return (
            f"No se encontró indicador de corriente ({umbral_txt}, {percentil}). "
            "Revisa Indicadores climáticos y Relacion_modelos_activos_e_indicadores.xlsx."
        )
    if variable.lower() == "visibilidad":
        return (
            f"No se encontró indicador de visibilidad ({umbral_txt}, {percentil}). "
            "Revisa Indicadores climáticos y Relacion_modelos_activos_e_indicadores.xlsx."
        )
    return f"No se encontró indicador de horas/año con {umbral_txt} ({percentil})."


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

        umbral_txt = ""
        umbral_m: float | None = None
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
                return ResultadoPIAgitacion.error(
                    f"No se pudo determinar el umbral para «{modo_fallo}» / {variable}."
                )
            if umbral_info is not None:
                umbral_txt, umbral_m = umbral_info
            elif regla_ind.usa_predefinido:
                umbral_txt = "Sin umbral numérico"

        df_clima = info_clima["por_variable"].get(variable, {}).get("df", pd.DataFrame())
        col_hist, columnas_fut = columnas_oleaje(
            info_clima, params.baseline_year, variable=variable
        )
        if col_hist is None or not columnas_fut:
            return ResultadoPIAgitacion.error(
                f"No se encontraron columnas climáticas para {variable}."
            )

        fila_ind, estados = clasificar_indicadores_umbral(
            df_clima,
            umbral_m,
            percentil=percentil,
            variable=variable,
            regla=regla_ind,
        )
        if fila_ind is None:
            return ResultadoPIAgitacion.error(
                _texto_error_indicador(
                    variable, umbral_txt, percentil, regla=regla_ind
                )
            )

        tabla = tabla_resultado_indicador(
            fila_ind,
            col_hist,
            columnas_fut,
            variable=variable,
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
        )
        pasos_totales.extend(pasos_modo)

        if regla_ind.usa_predefinido:
            indicador_resumen = regla_ind.etiqueta_mostrar()
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

    return ResultadoPIAgitacion.desde_calculo(
        metadatos_ejecucion={
            "activo": activo_resumen,
            "tipo_uo": tipo_uo,
            "modelo_id": MODELO_ID,
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
            "baseline_year": params.baseline_year,
        },
        iteraciones=iteraciones,
        resultados_por_pasos=ResultadosPorPasos(pasos=pasos_totales),
    )


__all__ = [
    "METADATOS",
    "ParametrosEntrada",
    "ResultadoPIAgitacion",
    "calcular",
]
