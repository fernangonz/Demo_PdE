# -*- coding: utf-8 -*-
"""Punto de entrada del modelo PI_PRECIPITACION (exceso de precipitación / ELO)."""

from __future__ import annotations

import pandas as pd

from core.relacion_modelos import buscar_regla_modelo
from core.modelos.impacto.pi_agitacion.pasos import (
    PasoResultado,
    ResultadosPorPasos,
    TablaPaso,
    construir_pasos_activo,
)
from core.modelos.impacto.pi_agitacion.utilidades import (
    columna_por_patron,
    columnas_oleaje,
    fila_configuracion,
    impactos_por_activo,
    nombre_activo_resumen,
)
from core.modelos.impacto.impactos_no_factibles import (
    MOTIVO_NO_FACTIBLE,
    debe_omitir_im,
)
from core.modelos.impacto.mensajes_indicador import nombre_excel_clima
from core.modelos.impacto.pi_precipitacion.pasos import construir_pasos_precipitacion
from core.modelos.impacto.pi_precipitacion.schemas import (
    METADATOS,
    MODELO_ID,
    NUM_INDICADORES_REQUERIDOS,
    IteracionResultado,
    ParametrosEntrada,
    ResultadoPIPrecipitacion,
)
from core.modelos.impacto.pi_precipitacion.utilidades import (
    buscar_fila_indicador_predefinido,
    indicadores_predefinidos_precipitacion,
    modos_exceso_precipitacion,
    resolver_pestana_clima_precipitacion,
    tabla_resultado_dos_indicadores,
)


def _iteracion_error(
    *,
    numero: int,
    etiqueta_im: str,
    variable: str,
    percentil: str,
    origen_regla: str,
    motivo: str,
    error_code: str,
    estados: list | None = None,
) -> IteracionResultado:
    return IteracionResultado(
        numero=numero,
        modo_fallo=etiqueta_im,
        variable_climatica=variable,
        umbral="Sin umbral (indicadores predefinidos)",
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
) -> ResultadoPIPrecipitacion:
    """Ejecuta PI exceso de precipitación: 2 indicadores predefinidos, sin umbral."""
    params = params or ParametrosEntrada(
        modo_fallo="Exceso de precipitación",
        variable_climatica="Precipitación",
    )

    if info_clima is None:
        info_clima = getattr(datos, "info_clima", None) or datos  # type: ignore[assignment]
    if config_puerto is None:
        config_puerto = getattr(datos, "config_puerto", None)
    if df_relacion is None:
        df_relacion = getattr(datos, "relacion_impactos", None)

    if config_puerto is None or config_puerto.empty:
        return ResultadoPIPrecipitacion.error(
            "Se requiere la configuración del puerto (Configuración_del_puerto.xlsx)."
        )

    fila_cfg = fila_configuracion(
        config_puerto,
        tipo_uo=params.tipo_uo,
        activo=params.activo,
    )
    if fila_cfg is None:
        return ResultadoPIPrecipitacion.error(
            "No se encontró fila en la configuración del puerto."
        )

    cols_cfg = list(config_puerto.columns)
    col_activo = columna_por_patron(cols_cfg, "activo fisico u operacional", "activo")
    col_tipo = columna_por_patron(cols_cfg, "tipo de uo", "tipo")
    activo_raw = str(fila_cfg[col_activo]).strip() if col_activo else (params.activo or "")
    activo_resumen = nombre_activo_resumen(activo_raw)
    tipo_uo = str(fila_cfg[col_tipo]).strip() if col_tipo else (params.tipo_uo or "")

    if df_relacion is None or df_relacion.empty:
        from core.data_loader import cargar_relacion_impactos_indicadores

        df_relacion, _ = cargar_relacion_impactos_indicadores()

    impactos = impactos_por_activo(df_relacion, activo_raw)
    modos = modos_exceso_precipitacion(impactos)
    if not modos:
        return ResultadoPIPrecipitacion(
            metadatos=METADATOS,
            ok=True,
            error="",
            iteraciones=[],
            metadatos_ejecucion={
                "activo": activo_resumen,
                "activo_raw": activo_raw,
                "omitido": "sin_modos_exceso_precipitacion",
            },
        )

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

        regla_modelo = buscar_regla_modelo(
            relacion_modelos,
            modelo_id=MODELO_ID,
            activo=activo_raw,
            modo_fallo=modo_fallo,
            variable=variable,
            estado_limite=estado_limite,
        )
        percentil = regla_modelo.percentil
        indicadores, error_inds = indicadores_predefinidos_precipitacion(regla_modelo)
        if error_inds:
            iteraciones.append(_iteracion_error(
                numero=numero,
                etiqueta_im=etiqueta_im,
                variable=variable,
                percentil=percentil,
                origen_regla=regla_modelo.origen,
                motivo=error_inds,
                error_code="INDICADORES_PREDEFINIDOS_INSUFICIENTES",
            ))
            continue

        pestana_ref = next((i.pestaña for i in indicadores if i.pestaña), "")
        df_clima, pestana_clima = resolver_pestana_clima_precipitacion(
            info_clima,
            variable=variable,
            pestana=pestana_ref,
        )
        col_hist, columnas_fut = columnas_oleaje(
            info_clima, params.baseline_year, variable=pestana_clima
        )
        if col_hist is None or not columnas_fut:
            iteraciones.append(_iteracion_error(
                numero=numero,
                etiqueta_im=etiqueta_im,
                variable=variable,
                percentil=percentil,
                origen_regla=regla_modelo.origen,
                motivo=(
                    f"No se encontraron columnas climáticas para {pestana_clima} "
                    f"en {nombre_excel_clima(datos)}."
                ),
                error_code="COLUMNAS_CLIMA_FALTANTES",
            ))
            continue

        filas_ok: list[pd.Series] = []
        estados_todos: list = []
        faltantes: list[str] = []
        for ind in indicadores:
            fila_ind, estados = buscar_fila_indicador_predefinido(
                df_clima,
                percentil=percentil,
                nombre_indicador=ind.indicador,
            )
            estados_todos.extend(estados)
            if fila_ind is None:
                faltantes.append(ind.indicador)
            else:
                filas_ok.append(fila_ind)

        if len(filas_ok) < NUM_INDICADORES_REQUERIDOS or faltantes:
            encontrados = [i.indicador for i in indicadores if i.indicador not in faltantes]
            motivo = (
                f"No se encontraron en {nombre_excel_clima(datos)} "
                f"(hoja '{pestana_clima}', {percentil}) todos los indicadores "
                f"predefinidos de Excel 4. "
                f"Faltan: {', '.join(f'«{f}»' for f in faltantes)}. "
                f"Encontrados: "
                + (
                    ", ".join(f"«{e}»" for e in encontrados)
                    if encontrados
                    else "(ninguno)"
                )
                + "."
            )
            iteraciones.append(_iteracion_error(
                numero=numero,
                etiqueta_im=etiqueta_im,
                variable=variable,
                percentil=percentil,
                origen_regla=regla_modelo.origen,
                motivo=motivo,
                error_code="INDICADOR_CLIMA_FALTANTE",
                estados=estados_todos,
            ))
            continue

        tabla = tabla_resultado_dos_indicadores(
            filas_ok[0],
            filas_ok[1],
            col_hist,
            columnas_fut,
        )
        pasos_modo = construir_pasos_precipitacion(
            numero_iteracion=numero,
            tipo_uo=tipo_uo,
            activo_raw=activo_raw,
            modo_fallo=etiqueta_im,
            variable=variable,
            percentil=percentil,
            origen_regla=regla_modelo.origen,
            fila_excel=regla_modelo.fila,
            indicadores=indicadores,
            pestana_clima=pestana_clima,
            col_hist=col_hist,
            columnas_fut=columnas_fut,
            tabla_variacion=tabla,
        )
        pasos_totales.extend(pasos_modo)

        indicador_resumen = " | ".join(
            (ind.etiqueta or ind.indicador) for ind in indicadores
        )
        iteraciones.append(IteracionResultado(
            numero=numero,
            modo_fallo=etiqueta_im,
            variable_climatica=variable,
            umbral="Sin umbral (indicadores predefinidos)",
            indicador_seleccionado=indicador_resumen,
            percentil=percentil,
            origen_regla=regla_modelo.origen,
            indicadores_evaluados=estados_todos,
            advertencias=[],
            _tabla_resultado_df=tabla,
        ))

    meta_ejec = {
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
        "modos_exceso_precipitacion": len(iteraciones),
        "modos_omitidos_no_factibles": omitidos_no_factibles,
        "baseline_year": params.baseline_year,
    }
    if not iteraciones:
        return ResultadoPIPrecipitacion(
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

    return ResultadoPIPrecipitacion.desde_calculo(
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
    "ResultadoPIPrecipitacion",
    "calcular",
]
