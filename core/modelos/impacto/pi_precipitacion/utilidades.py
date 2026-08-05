# -*- coding: utf-8 -*-
"""Utilidades del modelo PI_PRECIPITACION (exceso de precipitacion / ELO)."""

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
    INTERP_MEJORA,
    INTERP_NO_MEJORA,
    INTERP_REFERENCIA,
    INTERP_SIN_CAMBIOS,
    NUM_INDICADORES_MAX,
    NUM_INDICADORES_MIN,
    PREF_CAMBIO,
    PREF_INTERP,
    col_cambio_indicador,
    col_interpretacion_indicador,
    umbral_mm_desde_indicador,
)
from core.relacion_modelos import (
    IndicadorRelacion,
    ReglaModeloActivo,
    diagnosticar_busqueda_regla,
)


def es_modo_exceso_precipitacion(
    modo: object,
    variable: object,
    tipo_impacto: object | None = None,
) -> bool:
    """ELO + Exceso de precipitacion / Precipitacion (sin umbral; 1 o 2 indicadores)."""
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
    """Filas IM de exceso de precipitacion para el activo actual."""
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
    """Localiza la hoja climatica de precipitacion."""
    por_variable = info_clima.get("por_variable", {}) or {}
    candidatos = [
        p for p in (pestana, variable, "Precipitacion", "Precipitaci\u00f3n") if p
    ]
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
    minimo: int = NUM_INDICADORES_MIN,
    maximo: int = NUM_INDICADORES_MAX,
    df_relacion: object | None = None,
    modelo_id: str = "pi_precipitacion",
    activo: str = "",
    modo_fallo: str = "",
    variable: str = "",
    estado_limite: str | None = None,
) -> tuple[tuple[IndicadorRelacion, ...], str | None]:
    """Toma 1 o 2 indicadores predefinidos de Excel 4 (si hay mas, los primeros N<=max)."""
    if not regla.desde_excel:
        detalle = ""
        if df_relacion is not None and (activo or modo_fallo or variable):
            detalle = " " + diagnosticar_busqueda_regla(
                df_relacion,  # type: ignore[arg-type]
                modelo_id=modelo_id,
                activo=activo,
                modo_fallo=modo_fallo,
                variable=variable,
                estado_limite=estado_limite,
            )
        return (), (
            "Exceso de precipitacion requiere fila explicita en Excel 4 "
            "(Relacion_modelos_activos_e_indicadores) con Seleccion indicador = Predefinido "
            f"y entre {minimo} y {maximo} indicadores.{detalle}"
        )
    if not regla.regla_indicador.usa_predefinido:
        fila = f" (fila {regla.fila})" if regla.fila else ""
        return (), (
            "Exceso de precipitacion exige Seleccion indicador = Predefinido en Excel 4"
            f"{fila} (no se busca umbral)."
        )

    encontrados = [ind for ind in regla.indicadores if (ind.indicador or "").strip()]
    if len(encontrados) < minimo:
        nombres = ", ".join(f"\u00ab{i.indicador}\u00bb" for i in encontrados) or "(ninguno)"
        fila = f" fila {regla.fila}" if regla.fila else ""
        return (), (
            f"Se requiere al menos {minimo} indicador(es) predefinido(s) en Excel 4"
            f"{fila} (maximo {maximo}); encontrados {len(encontrados)}: {nombres}. "
            "Revise columnas Indicador climatico / Indicador climatico.1."
        )
    tomar = min(len(encontrados), maximo)
    return tuple(encontrados[:tomar]), None


def _percentil_num(valor: object) -> int | None:
    texto = str(valor or "").strip().upper().lstrip("P")
    if texto.isdigit():
        return int(texto)
    return None


def _elegir_fila_por_percentil(
    candidatas: list[pd.Series],
    percentil: str,
) -> pd.Series | None:
    """Prefiere coincidencia exacta de percentil; si no, el mas cercano disponible."""
    if not candidatas:
        return None
    objetivo = (percentil or "").strip().upper()
    exactas = [
        r
        for r in candidatas
        if str(r.get("Percentil", "")).strip().upper() == objetivo
    ]
    if exactas:
        return exactas[0]

    objetivo_n = _percentil_num(objetivo)
    if objetivo_n is None:
        # Sin percentil pedible: preferir P99 si existe, si no la primera.
        for pref in ("P99", "P95", "P90", "P50"):
            for r in candidatas:
                if str(r.get("Percentil", "")).strip().upper() == pref:
                    return r
        return candidatas[0]

    def _clave(row: pd.Series) -> tuple[int, int]:
        n = _percentil_num(row.get("Percentil"))
        if n is None:
            return (10_000, 10_000)
        # Empate: preferir percentil mas alto (extremos) frente al mas bajo.
        return (abs(n - objetivo_n), -n)

    return sorted(candidatas, key=_clave)[0]


def buscar_fila_indicador_predefinido(
    df_clima: pd.DataFrame,
    *,
    percentil: str,
    nombre_indicador: str,
) -> tuple[pd.Series | None, list[IndicadorEvaluado]]:
    """Localiza un indicador predefinido en la hoja climatica.

    1. Busca por nombre en toda la hoja (no filtra el sheet entero por percentil:
       un P98 de otro indicador no debe ocultar lluvia intensa en P99).
    2. Prefiere la fila con el percentil pedido; si no existe, el percentil mas
       cercano disponible para ese mismo indicador.
    """
    if df_clima.empty or "Indicador" not in df_clima.columns:
        return None, []

    etiqueta = (nombre_indicador or "").strip() or "\u2014"
    candidatas: list[pd.Series] = []
    estados: list[IndicadorEvaluado] = []
    vistos_descartados: set[str] = set()

    for _, row in df_clima.iterrows():
        ind = str(row.get("Indicador", "")).strip()
        if not ind or ind.lower() == "nan":
            continue
        if indicador_coincide_nombre(ind, nombre_indicador):
            candidatas.append(row)
            continue
        clave = ind[:80]
        if clave not in vistos_descartados:
            vistos_descartados.add(clave)
            estados.append(
                IndicadorEvaluado(nombre=clave, seleccionado=False, descartado=True)
            )

    candidato = _elegir_fila_por_percentil(candidatas, percentil)

    if candidato is not None:
        pct_usado = str(candidato.get("Percentil", "")).strip().upper()
        pct_pedido = (percentil or "").strip().upper()
        etiqueta_sel = etiqueta
        if pct_usado and pct_pedido and pct_usado != pct_pedido:
            etiqueta_sel = f"{etiqueta} ({pct_usado}; pedido {pct_pedido})"
        estados.insert(0, IndicadorEvaluado(nombre=etiqueta_sel, seleccionado=True))
    else:
        estados.insert(
            0,
            IndicadorEvaluado(nombre=etiqueta, seleccionado=False, descartado=True),
        )
    return candidato, estados


def interpretar_delta_precip(
    delta: float | int | None,
    *,
    es_historico: bool = False,
) -> str:
    """Polaridad como PI agitacion (>0 adverso), etiquetas Mejora / no mejora.

    - historico -> Referencia
    - delta > 0 (mas dias) -> no mejora
    - delta < 0 (menos dias) -> Mejora
    - delta == 0 -> Sin cambios
    """
    if es_historico:
        return INTERP_REFERENCIA
    if delta is None or (isinstance(delta, float) and pd.isna(delta)):
        return "\u2014"
    try:
        cambio = float(delta)
    except (TypeError, ValueError):
        return "\u2014"
    if cambio > 0:
        return INTERP_NO_MEJORA
    if cambio < 0:
        return INTERP_MEJORA
    return INTERP_SIN_CAMBIOS


def _valor_indicador(fila: pd.Series, columna: str) -> int | None:
    raw = _a_numero(fila.get(columna))
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    return int(round(raw))


def _nombre_indicador_fila(fila: pd.Series, fallback: str = "") -> str:
    raw = str(fila.get("Indicador", "") or "").strip()
    if raw and raw.lower() != "nan":
        return raw
    return fallback


def tabla_resultado_indicadores(
    filas_indicadores: list[pd.Series],
    col_hist: ColumnaEscenario,
    columnas_fut: list[ColumnaEscenario],
    *,
    nombres_indicadores: list[str] | tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Tabla por escenario: un par Cambio + Interpretacion por cada indicador (1 o 2)."""
    if not filas_indicadores:
        raise ValueError("Se requiere al menos una fila de indicador.")
    nombres = list(nombres_indicadores or [])
    while len(nombres) < len(filas_indicadores):
        i = len(nombres)
        nombres.append(
            _nombre_indicador_fila(filas_indicadores[i], f"indicador {i + 1}")
        )
    nombres = nombres[: len(filas_indicadores)]

    pares = [
        (
            col_cambio_indicador(nom, i),
            col_interpretacion_indicador(nom, i),
        )
        for i, nom in enumerate(nombres, start=1)
    ]
    hist_vals = [_valor_indicador(fila, col_hist.columna) for fila in filas_indicadores]

    fila_hist: dict = {"Escenario": "Hist\u00f3rico"}
    for c_cambio, c_interp in pares:
        fila_hist[c_cambio] = 0
        fila_hist[c_interp] = interpretar_delta_precip(0, es_historico=True)
    filas: list[dict] = [fila_hist]

    for col in columnas_fut:
        fila_esc: dict = {"Escenario": etiqueta_escenario(col.escenario, col.anio)}
        for idx, (fila_ind, hist) in enumerate(zip(filas_indicadores, hist_vals)):
            c_cambio, c_interp = pares[idx]
            val = _valor_indicador(fila_ind, col.columna)
            delta = (val - hist) if val is not None and hist is not None else None
            fila_esc[c_cambio] = delta
            fila_esc[c_interp] = interpretar_delta_precip(delta)
        filas.append(fila_esc)
    return pd.DataFrame(filas)


def tabla_resultado_dos_indicadores(
    fila_ind_1: pd.Series,
    fila_ind_2: pd.Series,
    col_hist: ColumnaEscenario,
    columnas_fut: list[ColumnaEscenario],
    *,
    nombre_ind_1: str = "",
    nombre_ind_2: str = "",
) -> pd.DataFrame:
    """Compat: dos indicadores. Preferir ``tabla_resultado_indicadores``."""
    return tabla_resultado_indicadores(
        [fila_ind_1, fila_ind_2],
        col_hist,
        columnas_fut,
        nombres_indicadores=[nombre_ind_1, nombre_ind_2],
    )


__all__ = [
    "PREF_CAMBIO",
    "PREF_INTERP",
    "buscar_fila_indicador_predefinido",
    "es_modo_exceso_precipitacion",
    "indicadores_predefinidos_precipitacion",
    "interpretar_delta_precip",
    "modos_exceso_precipitacion",
    "resolver_pestana_clima_precipitacion",
    "tabla_resultado_dos_indicadores",
    "tabla_resultado_indicadores",
    "umbral_mm_desde_indicador",
]
