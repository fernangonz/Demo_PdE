"""Interpretación de cambios para impactos de cierre (horas o días según indicador)."""

from __future__ import annotations

import pandas as pd

from core.data_loader import _normalizar
from core.modelos.impacto.pi_agitacion.schemas import (
    ADVERTENCIA_INDICADOR_NEGATIVO,
    SintesisCambios,
)


def usa_dias_cierre(
    *,
    variable: str | None = None,
    indicador: str | None = None,
) -> bool:
    """True si el impacto se expresa en días/año; False si en horas/año."""
    texto = _normalizar(indicador or "")
    if "dia" in texto and "hora" not in texto:
        return True
    if "hora" in texto:
        return False
    if variable:
        return str(variable).lower() in ("viento", "corriente", "visibilidad")
    return False


def _frase_cierre(
    verbo: str,
    *,
    variable: str | None = None,
    indicador: str | None = None,
) -> str:
    """Frase auxiliar: «aumentan/disminuyen los días/las horas de cierre…»."""
    if usa_dias_cierre(variable=variable, indicador=indicador):
        return f"{verbo.capitalize()} los días de cierre respecto al histórico."
    return f"{verbo.capitalize()} las horas de cierre respecto al histórico."


def interpretar_cambio(
    cambio: float | None,
    *,
    es_historico: bool,
    variable: str | None = None,
    indicador: str | None = None,
) -> tuple[str, str]:
    if es_historico:
        return (
            "Referencia",
            "Escenario base usado para calcular los cambios.",
        )
    if cambio is None or (isinstance(cambio, float) and pd.isna(cambio)):
        return ("—", "")
    if cambio > 0:
        return (
            "Empeora",
            _frase_cierre("aumentan", variable=variable, indicador=indicador),
        )
    if cambio < 0:
        return (
            "Mejora",
            _frase_cierre("disminuyen", variable=variable, indicador=indicador),
        )
    return (
        "Sin cambios",
        "No se observan cambios respecto al histórico.",
    )


def etiqueta_interpretacion_paso(interpretacion: str, texto_auxiliar: str) -> str:
    """Etiqueta corta del paso 8 reutilizando el texto auxiliar del escenario."""
    if interpretacion in ("Referencia", "—", "-", ""):
        return "-"
    if interpretacion in ("Mejora", "Empeora") and texto_auxiliar:
        detalle = texto_auxiliar.rstrip(".")
        return f"{interpretacion}: {detalle[0].lower()}{detalle[1:]}"
    if interpretacion == "Sin cambios":
        return "Sin cambios respecto al histórico"
    return texto_auxiliar or interpretacion


def sintesis_cambios(tabla: pd.DataFrame) -> SintesisCambios:
    col_cambio = "Cambio respecto al histórico"
    futuros = tabla[tabla["Escenario"] != "Histórico"].copy()
    futuros = futuros[futuros[col_cambio].notna()]

    empeoran = futuros[futuros[col_cambio] > 0]
    mejoran = futuros[futuros[col_cambio] < 0]

    mayor_empeoramiento = None
    mayor_empeoramiento_cambio = None
    if not empeoran.empty:
        fila = empeoran.loc[empeoran[col_cambio].idxmax()]
        mayor_empeoramiento = str(fila["Escenario"])
        mayor_empeoramiento_cambio = float(fila[col_cambio])

    mayor_mejora = None
    mayor_mejora_cambio = None
    if not mejoran.empty:
        fila = mejoran.loc[mejoran[col_cambio].idxmin()]
        mayor_mejora = str(fila["Escenario"])
        mayor_mejora_cambio = float(fila[col_cambio])

    return SintesisCambios(
        mayor_empeoramiento=mayor_empeoramiento,
        mayor_empeoramiento_cambio=mayor_empeoramiento_cambio,
        mayor_mejora=mayor_mejora,
        mayor_mejora_cambio=mayor_mejora_cambio,
        n_empeoran=len(empeoran),
        n_mejoran=len(mejoran),
    )


def advertencia_valores_negativos(tabla: pd.DataFrame) -> str | None:
    indicadores = tabla["Indicador"].dropna()
    if indicadores.empty:
        return None
    if (indicadores.astype(float) < 0).any():
        return ADVERTENCIA_INDICADOR_NEGATIVO
    return None
