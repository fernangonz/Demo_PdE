"""Funciones económicas legacy (MATLAB) — se migrarán a modelos independientes."""

from __future__ import annotations

import math

from core.modelos.economico.schemas import ParametrosEconomicos


class ColumnaEscenario:
    """Columna de proyección climática / económica (compatibilidad)."""

    def __init__(
        self,
        etiqueta: str,
        escenario: str,
        anio: int,
        columna: str = "",
        es_historico: bool = False,
    ):
        self.etiqueta = etiqueta
        self.escenario = escenario
        self.anio = anio
        self.columna = columna
        self.es_historico = es_historico


def revenue_descont(
    annual_revenue_musd: float,
    average_occupation: float,
    growth_rate: float,
    baseline_year: int,
    columnas: list[ColumnaEscenario],
) -> dict[str, float]:
    if average_occupation <= 0:
        return {c.etiqueta: 0.0 for c in columnas}

    max_revenue = annual_revenue_musd / average_occupation
    ingresos: dict[str, float] = {}
    for col in columnas:
        if col.es_historico:
            ingresos[col.etiqueta] = annual_revenue_musd
        else:
            factor = (1 + growth_rate) ** (col.anio - baseline_year)
            ingresos[col.etiqueta] = min(annual_revenue_musd * factor, max_revenue)
    return ingresos


def resultado_acumulado(
    incrementos: dict[str, float],
    columnas: list[ColumnaEscenario],
    *,
    baseline_year: int,
    discount_rate: float,
) -> dict[str, float]:
    r = discount_rate
    acumulados: dict[str, float] = {}
    prev_acumulado = 0.0

    for i, col in enumerate(columnas):
        val = incrementos.get(col.etiqueta)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            acumulados[col.etiqueta] = float("nan")
            continue

        yscenario = col.anio
        if i == 0:
            gradiente = val / (yscenario - baseline_year) if yscenario > baseline_year else 0.0
        else:
            col_prev = columnas[i - 1]
            v_prev = incrementos.get(col_prev.etiqueta)
            if v_prev is None or (isinstance(v_prev, float) and math.isnan(v_prev)):
                acumulados[col.etiqueta] = float("nan")
                continue
            dy = yscenario - col_prev.anio
            gradiente = (val - v_prev) / dy if dy else 0.0

        sumatoria_descontada = 0.0
        if i == 0:
            for yiter in range(yscenario - baseline_year + 1):
                year_analizado = baseline_year + yiter
                acumu = gradiente * yiter
                sumatoria_descontada += acumu / (1 + r) ** (year_analizado - baseline_year)
        else:
            col_prev = columnas[i - 1]
            y0 = col_prev.anio
            acumu = prev_acumulado if prev_acumulado else incrementos.get(col_prev.etiqueta, 0.0)
            for yiter in range(yscenario - y0 + 1):
                year_analizado = y0 + yiter
                if yiter > 0:
                    acumu += gradiente
                sumatoria_descontada += acumu / (1 + r) ** (year_analizado - baseline_year)

        acumulado_descont = sumatoria_descontada

        if i >= 2 and not math.isnan(prev_acumulado):
            prev_label = columnas[i - 2].etiqueta
            prev_b = acumulados.get(prev_label)
            if prev_b is not None and not math.isnan(prev_b):
                acumulado_descont += prev_b

        acumulados[col.etiqueta] = acumulado_descont
        prev_acumulado = acumulados[col.etiqueta]

    return acumulados


def resultado_equivalente_anual(
    acumulados: dict[str, float],
    columnas: list[ColumnaEscenario],
    *,
    baseline_year: int,
    discount_rate: float,
) -> dict[str, float]:
    r = discount_rate
    equivalentes: dict[str, float] = {}

    for col in columnas:
        acum = acumulados.get(col.etiqueta)
        if acum is None or (isinstance(acum, float) and math.isnan(acum)):
            equivalentes[col.etiqueta] = float("nan")
            continue
        year = col.anio
        n = year - baseline_year + 1
        if r == 0 or n <= 0:
            equivalentes[col.etiqueta] = acum / max(n, 1)
        else:
            factor = ((1 / (1 + r) ** n) - (1 / (1 + r))) / (1 / (1 + r) - 1)
            equivalentes[col.etiqueta] = acum / factor if factor else float("nan")

    return equivalentes
