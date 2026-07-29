"""Utilidades del modelo PI_CALADO_ELS."""

from __future__ import annotations

import re

import pandas as pd

from core.data_loader import _a_numero, _normalizar
from core.modelos.impacto.pi_agitacion.schemas import IndicadorEvaluado
from core.modelos.impacto.pi_agitacion.utilidades import (
    ColumnaEscenario,
    columnas_oleaje,
    indicador_coincide_nombre,
    match_texto,
)
from core.relacion_modelos import IndicadorRelacion

_FALLBACK_SEDIMENTACION = "Tasa de sedimentación anual"


def es_modo_falta_calado(modo: object, variable: object) -> bool:
    modo_n = _normalizar(modo)
    if "calado" not in modo_n:
        return False
    var_n = _normalizar(variable)
    return var_n in ("nivel del mar", "calado")


def modos_falta_calado(
    impactos: pd.DataFrame,
    *,
    tipo_impacto: str | None = "ELO",
) -> list[pd.Series]:
    filas: list[pd.Series] = []
    for _, row in impactos.iterrows():
        if not es_modo_falta_calado(
            row.get("Modos de fallo / Modos de parada"),
            row.get("Variable"),
        ):
            continue
        if tipo_impacto:
            tipo = str(row.get("Tipo de impacto", "")).strip()
            if tipo and not match_texto(tipo, tipo_impacto):
                continue
        filas.append(row)
    return filas


def resolver_indicadores_calado(
    indicadores: tuple[IndicadorRelacion, ...],
) -> dict[str, IndicadorRelacion | None]:
    """Asigna los 3 indicadores del Excel de relación por posición."""
    roles: dict[str, IndicadorRelacion | None] = {
        "nm": None,
        "h0": None,
        "hsedim": None,
    }
    if len(indicadores) >= 1:
        roles["nm"] = indicadores[0]
    if len(indicadores) >= 2:
        roles["h0"] = indicadores[1]
    if len(indicadores) >= 3:
        tercero = indicadores[2]
        if (
            roles["h0"] is not None
            and match_texto(tercero.indicador, roles["h0"].indicador)
            and "sediment" not in _normalizar(tercero.indicador)
        ):
            pest = tercero.pestaña or roles["h0"].pestaña or "Nivel del mar"
            roles["hsedim"] = IndicadorRelacion(
                pestaña=pest,
                indicador=_FALLBACK_SEDIMENTACION,
                etiqueta="Tasa de sedimentación anual (m/año)",
            )
        else:
            roles["hsedim"] = tercero

    if roles["hsedim"] is None and len(indicadores) >= 2:
        pest = indicadores[1].pestaña or "Nivel del mar"
        if "sediment" in _normalizar(indicadores[1].indicador):
            roles["hsedim"] = indicadores[1]
        else:
            roles["hsedim"] = IndicadorRelacion(
                pestaña=pest,
                indicador=_FALLBACK_SEDIMENTACION,
                etiqueta="Tasa de sedimentación anual (m/año)",
            )

    return roles


def dataframe_pestana(info_clima: dict, pestaña: str) -> pd.DataFrame:
    por_variable = info_clima.get("por_variable", {})
    for var, datos in por_variable.items():
        if match_texto(var, pestaña):
            return datos.get("df", pd.DataFrame())
    pest_n = _normalizar(pestaña)
    for var, datos in por_variable.items():
        if pest_n in _normalizar(var):
            return datos.get("df", pd.DataFrame())
    return por_variable.get("Nivel del mar", {}).get("df", pd.DataFrame())


def buscar_fila_indicador(
    df_clima: pd.DataFrame,
    *,
    nombre_indicador: str,
    percentil: str,
) -> tuple[pd.Series | None, list[IndicadorEvaluado]]:
    if df_clima.empty or "Indicador" not in df_clima.columns:
        return None, []

    sub = df_clima.copy()
    if "Percentil" in sub.columns and percentil:
        mask_pct = sub["Percentil"].astype(str).str.strip().str.upper() == percentil.upper()
        if mask_pct.any():
            sub = sub[mask_pct]

    candidato: pd.Series | None = None
    estados: list[IndicadorEvaluado] = []
    for _, row in sub.iterrows():
        ind = str(row.get("Indicador", "")).strip()
        if not ind or ind.lower() == "nan":
            continue
        if indicador_coincide_nombre(ind, nombre_indicador):
            if candidato is None:
                candidato = row
                estados.append(IndicadorEvaluado(nombre=ind, seleccionado=True))
            else:
                estados.append(IndicadorEvaluado(nombre=ind[:80], seleccionado=False, descartado=True))
        else:
            estados.append(IndicadorEvaluado(nombre=ind[:80], seleccionado=False, descartado=True))

    if candidato is None:
        estados.insert(
            0,
            IndicadorEvaluado(nombre=nombre_indicador, seleccionado=False, descartado=True),
        )
    return candidato, estados


def valor_celda_fila(fila: pd.Series, nombre_columna: str) -> object:
    """Lee una celda admitiendo columnas duplicadas en el Excel de clima."""
    if nombre_columna not in fila.index:
        return None
    val = fila[nombre_columna]
    if isinstance(val, pd.Series):
        for item in val:
            num = _a_numero(item)
            if num is not None:
                return num
        return val.iloc[0] if len(val) else None
    return val


def valor_columna(fila: pd.Series, col: ColumnaEscenario) -> float | None:
    return _a_numero(valor_celda_fila(fila, col.columna))


def interpretar_dragado(*, umbral: float, h: float | None) -> str:
    if h is None:
        return "—"
    if umbral <= h:
        return "Es necesario dragar"
    return "No es necesario dragar"


def etiqueta_escenario_calado(col: ColumnaEscenario) -> str:
    if col.es_historico:
        return "Histórico"
    if re.search(r"\d{4}", col.etiqueta):
        m = re.search(r"(\d{4})\)", col.etiqueta)
        anio = m.group(1) if m else col.anio
        return f"{col.escenario} {anio}".strip()
    return f"{col.escenario} {col.anio}".strip()


def filas_clima_calado_por_escenario(
    *,
    fila_nm: pd.Series,
    fila_h0: pd.Series,
    fila_hsedim: pd.Series,
    col_hist: ColumnaEscenario,
    columnas_fut: list[ColumnaEscenario],
) -> list[dict[str, object]]:
    """Valores NM, h₀ y h sedimentación por escenario (lectura manual)."""
    filas: list[dict[str, object]] = []

    def _fila(escenario: str, col: ColumnaEscenario) -> None:
        filas.append({
            "Escenario": escenario,
            "NM (m)": valor_columna(fila_nm, col),
            "h0 (m)": valor_columna(fila_h0, col),
            "h sedimentacion (m)": valor_columna(fila_hsedim, col),
        })

    _fila("Histórico", col_hist)
    for col in columnas_fut:
        _fila(etiqueta_escenario_calado(col), col)
    return filas


def construir_tabla_calado(
    *,
    fila_nm: pd.Series,
    fila_h0: pd.Series,
    fila_hsedim: pd.Series,
    umbral: float,
    umbral_txt: str,
    col_hist: ColumnaEscenario,
    columnas_fut: list[ColumnaEscenario],
) -> pd.DataFrame:
    filas: list[dict[str, object]] = []

    def _fila_escenario(
        escenario: str,
        col: ColumnaEscenario,
        *,
        es_historico: bool = False,
    ) -> None:
        nm = valor_columna(fila_nm, col)
        h0 = valor_columna(fila_h0, col)
        hsed = valor_columna(fila_hsedim, col)
        h = None
        if nm is not None and h0 is not None and hsed is not None:
            h = nm - h0 - hsed
        filas.append({
            "Escenario": escenario,
            "NM": nm,
            "h sedimentacion": hsed,
            "h0": h0,
            "h": h,
            "Umbral": umbral,
            "Interpretación": (
                "Referencia" if es_historico else interpretar_dragado(umbral=umbral, h=h)
            ),
            "Texto auxiliar": umbral_txt if not es_historico else "",
        })

    _fila_escenario("Histórico", col_hist, es_historico=True)
    for col in columnas_fut:
        _fila_escenario(etiqueta_escenario_calado(col), col)

    return pd.DataFrame(filas)


def columnas_nivel_mar(
    info_clima: dict,
    baseline_year: int,
) -> tuple[ColumnaEscenario | None, list[ColumnaEscenario]]:
    col_hist, futuras = columnas_oleaje(info_clima, baseline_year, variable="Nivel del mar")
    vistos: set[tuple[str, int]] = set()
    dedup: list[ColumnaEscenario] = []
    for col in futuras:
        clave = (col.escenario, col.anio)
        if clave in vistos:
            continue
        vistos.add(clave)
        dedup.append(col)
    return col_hist, dedup
