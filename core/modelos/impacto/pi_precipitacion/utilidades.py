# -*- coding: utf-8 -*-

"""Utilidades del modelo PI_PRECIPITACION (exceso de precipitación / ELO)."""



from __future__ import annotations



import pandas as pd



from core.data_loader import _a_numero, _normalizar

from core.modelos.impacto.pi_agitacion.schemas import IndicadorEvaluado

from core.modelos.impacto.pi_agitacion.utilidades import (

    ColumnaEscenario,

    es_tipo_impacto_pi_operacional,

    etiqueta_escenario,

    indicador_coincide_nombre,

)

from core.modelos.impacto.pi_precipitacion.schemas import (

    ANALISIS_INCREMENTA,

    ANALISIS_NO,

    COL_ANALISIS_1,

    COL_ANALISIS_2,

    COL_INCREMENTO_1,

    COL_INCREMENTO_2,

    NUM_INDICADORES_REQUERIDOS,

)

from core.relacion_modelos import IndicadorRelacion, ReglaModeloActivo





def es_modo_exceso_precipitacion(
    modo: object,
    variable: object,
    tipo_impacto: object | None = None,
) -> bool:
    """ELO + Exceso de precipitacion / Precipitacion (sin umbral; 2 indicadores).

    Matching robusto via ``_normalizar`` (acentos, mayusculas, espacios).
    """
    if tipo_impacto is not None and str(tipo_impacto).strip() != "":
        if not es_tipo_impacto_pi_operacional(tipo_impacto):
            return False
    modo_n = _normalizar(modo)
    var_n = _normalizar(variable)
    if not modo_n and not var_n:
        return False
    if "precipitacion" in var_n:
        return (
            "precipitacion" in modo_n
            or "exceso" in modo_n
            or "lluvia" in modo_n
        )
    return "precipitacion" in modo_n


def modos_exceso_precipitacion(impactos: pd.DataFrame) -> list[pd.Series]:

    """Filas IM de exceso de precipitación para el activo actual."""

    filas: list[pd.Series] = []

    for _, row in impactos.iterrows():

        if es_modo_exceso_precipitacion(

            row.get("Modos de fallo / Modos de parada"),

            row.get("Variable"),

            row.get("Tipo de impacto"),

        ):

            filas.append(row)

    return filas





def resolver_pestana_clima_precipitacion(

    info_clima: dict,

    *,

    variable: str,

    pestana: str = "",

) -> tuple[pd.DataFrame, str]:

    """Localiza la hoja climática de precipitación (con/sin acento)."""

    por_variable = info_clima.get("por_variable", {}) or {}

    candidatos = [p for p in (pestana, variable, "Precipitacion", "Precipitación") if p]

    for cand in candidatos:

        if cand in por_variable:

            return por_variable[cand].get("df", pd.DataFrame()), cand

        target = _normalizar(cand)

        for nombre, datos in por_variable.items():

            if _normalizar(nombre) == target:

                return datos.get("df", pd.DataFrame()), nombre

    for nombre, datos in por_variable.items():

        if "precipitacion" in _normalizar(nombre):

            return datos.get("df", pd.DataFrame()), nombre

    return pd.DataFrame(), pestana or variable or "Precipitacion"





def indicadores_predefinidos_precipitacion(

    regla: ReglaModeloActivo,

    *,

    minimo: int = NUM_INDICADORES_REQUERIDOS,

) -> tuple[tuple[IndicadorRelacion, ...], str | None]:

    """Toma los indicadores predefinidos de Excel 4 (?2; si hay más, los primeros N)."""

    if not regla.desde_excel:

        return (), (

            "Exceso de precipitación requiere fila explícita en Excel 4 "

            "(Relacion_modelos_activos_e_indicadores) con Selección indicador = Predefinido "

            f"y al menos {minimo} indicadores."

        )

    if not regla.regla_indicador.usa_predefinido:

        return (), (

            "Exceso de precipitación exige Selección indicador = Predefinido en Excel 4 "

            "(no se busca umbral)."

        )



    encontrados = [ind for ind in regla.indicadores if (ind.indicador or "").strip()]

    if len(encontrados) < minimo:

        nombres = ", ".join(f"«{i.indicador}»" for i in encontrados) or "(ninguno)"

        return (), (

            f"Se requieren al menos {minimo} indicadores predefinidos en Excel 4; "

            f"encontrados {len(encontrados)}: {nombres}."

        )

    return tuple(encontrados[:minimo]), None





def buscar_fila_indicador_predefinido(

    df_clima: pd.DataFrame,

    *,

    percentil: str,

    nombre_indicador: str,

) -> tuple[pd.Series | None, list[IndicadorEvaluado]]:

    """Localiza un indicador predefinido en la hoja climática (percentil filtrado)."""

    if df_clima.empty or "Indicador" not in df_clima.columns:

        return None, []



    sub = df_clima.copy()

    if "Percentil" in sub.columns and percentil:

        mask_pct = sub["Percentil"].astype(str).str.strip().str.upper() == percentil.upper()

        if mask_pct.any():

            sub = sub[mask_pct]



    etiqueta = (nombre_indicador or "").strip() or "—"

    candidato: pd.Series | None = None

    estados: list[IndicadorEvaluado] = []

    for _, row in sub.iterrows():

        ind = str(row.get("Indicador", "")).strip()

        if not ind or ind.lower() == "nan":

            continue

        if indicador_coincide_nombre(ind, nombre_indicador):

            if candidato is None:

                candidato = row

        else:

            estados.append(IndicadorEvaluado(nombre=ind[:80], seleccionado=False, descartado=True))



    if candidato is not None:

        estados.insert(0, IndicadorEvaluado(nombre=etiqueta, seleccionado=True))

    else:

        estados.insert(0, IndicadorEvaluado(nombre=etiqueta, seleccionado=False, descartado=True))

    return candidato, estados





def analisis_incremento(delta: float | int | None) -> str:

    """INCREMENTA si el delta futuro?histórico es > 0; si no, NO."""

    if delta is None or (isinstance(delta, float) and pd.isna(delta)):

        return ANALISIS_NO

    try:

        return ANALISIS_INCREMENTA if float(delta) > 0 else ANALISIS_NO

    except (TypeError, ValueError):

        return ANALISIS_NO





def _valor_indicador(fila: pd.Series, columna: str) -> int | None:

    raw = _a_numero(fila.get(columna))

    if raw is None or (isinstance(raw, float) and pd.isna(raw)):

        return None

    return int(round(raw))





def tabla_resultado_dos_indicadores(

    fila_ind_1: pd.Series,

    fila_ind_2: pd.Series,

    col_hist: ColumnaEscenario,

    columnas_fut: list[ColumnaEscenario],

) -> pd.DataFrame:

    """Tabla por escenario: incremento y análisis para cada uno de los 2 indicadores."""

    hist_1 = _valor_indicador(fila_ind_1, col_hist.columna)

    hist_2 = _valor_indicador(fila_ind_2, col_hist.columna)



    filas: list[dict] = [{

        "Escenario": "Histórico",

        COL_INCREMENTO_1: 0,

        COL_ANALISIS_1: ANALISIS_NO,

        COL_INCREMENTO_2: 0,

        COL_ANALISIS_2: ANALISIS_NO,

    }]

    for col in columnas_fut:

        val_1 = _valor_indicador(fila_ind_1, col.columna)

        val_2 = _valor_indicador(fila_ind_2, col.columna)

        delta_1 = (val_1 - hist_1) if val_1 is not None and hist_1 is not None else None

        delta_2 = (val_2 - hist_2) if val_2 is not None and hist_2 is not None else None

        filas.append({

            "Escenario": etiqueta_escenario(col.escenario, col.anio),

            COL_INCREMENTO_1: delta_1,

            COL_ANALISIS_1: analisis_incremento(delta_1),

            COL_INCREMENTO_2: delta_2,

            COL_ANALISIS_2: analisis_incremento(delta_2),

        })

    return pd.DataFrame(filas)





__all__ = [

    "analisis_incremento",

    "buscar_fila_indicador_predefinido",

    "es_modo_exceso_precipitacion",

    "indicadores_predefinidos_precipitacion",

    "modos_exceso_precipitacion",

    "resolver_pestana_clima_precipitacion",

    "tabla_resultado_dos_indicadores",

]

