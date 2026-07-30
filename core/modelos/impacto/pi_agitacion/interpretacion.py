"""Interpretación de cambios para impactos de cierre (horas o días según indicador)."""

from __future__ import annotations

from typing import Literal

import pandas as pd

from core.data_loader import _normalizar
from core.modelos.impacto.pi_agitacion.schemas import (
    ADVERTENCIA_INDICADOR_NEGATIVO,
    SintesisCambios,
)

UnidadCierre = Literal["horas", "dias"]

_VARIABLES_DIAS = frozenset({"viento", "corriente", "visibilidad"})
_VARIABLES_HORAS = frozenset({"oleaje", "hs", "agitacion"})


def _normalizar_unidad_explicita(unidad: str | None) -> UnidadCierre | None:
    """Mapea etiquetas de unidad (Excel, ficha, UI) a horas|dias."""
    if not unidad:
        return None
    u = _normalizar(unidad.replace("/", " "))
    if not u:
        return None
    if u in {"dias", "dia", "d", "d ano", "dias ano", "d/ano", "dias/ano"}:
        return "dias"
    if u in {"horas", "hora", "h", "h ano", "horas ano", "h/ano", "horas/ano"}:
        return "horas"
    tiene_dia = "dia" in u
    tiene_hora = "hora" in u
    if tiene_dia and not tiene_hora:
        return "dias"
    if tiene_hora and not tiene_dia:
        return "horas"
    return None


def resolver_unidad_cierre(
    *,
    unidad: str | None = None,
    variable: str | None = None,
    indicador: str | None = None,
) -> UnidadCierre | None:
    """Resuelve unidad de cierre: ``horas``, ``dias`` o ``None`` si es desconocida.

    Orden: unidad explícita → nombre de indicador → variable climática
    (viento/corriente/visibilidad → días; oleaje → horas).
    """
    explicita = _normalizar_unidad_explicita(unidad)
    if explicita is not None:
        return explicita

    texto_ind = _normalizar(indicador or "")
    if texto_ind:
        if "dia" in texto_ind and "hora" not in texto_ind:
            return "dias"
        if "hora" in texto_ind:
            return "horas"

    var = _normalizar(variable or "")
    if var:
        if var in _VARIABLES_DIAS or any(v in var for v in _VARIABLES_DIAS):
            return "dias"
        if (
            var in _VARIABLES_HORAS
            or "oleaje" in var
            or "agitacion" in var
        ):
            return "horas"
    return None


def usa_dias_cierre(
    *,
    variable: str | None = None,
    indicador: str | None = None,
    unidad: str | None = None,
) -> bool:
    """True si el impacto se expresa en días/año; False si en horas/año.

    Si la unidad no se puede determinar, se asume horas (comportamiento histórico).
    """
    return resolver_unidad_cierre(
        unidad=unidad, variable=variable, indicador=indicador
    ) == "dias"


def etiqueta_unidad_cierre(unidad: UnidadCierre | None) -> str | None:
    """Etiqueta UI con acento: ``horas`` | ``días`` | None."""
    if unidad == "dias":
        return "días"
    if unidad == "horas":
        return "horas"
    return None


def regla_variacion_cierre(
    unidad: UnidadCierre | str | None = None,
    *,
    variable: str | None = None,
    indicador: str | None = None,
) -> str:
    """Caption de variación Δ según unidad de cierre.

    - horas/días conocidos: menciona solo esa unidad
    - desconocida: neutro, sin inventar «horas/días»
    """
    u: UnidadCierre | None
    if unidad in ("horas", "dias"):
        u = unidad  # type: ignore[assignment]
    else:
        u = resolver_unidad_cierre(
            unidad=unidad if isinstance(unidad, str) else None,
            variable=variable,
            indicador=indicador,
        )

    if u == "dias":
        return (
            "Variación > 0 → aumentan días de cierre (Empeora); "
            "< 0 → disminuyen (Mejora); = 0 → sin cambios."
        )
    if u == "horas":
        return (
            "Variación > 0 → aumentan horas de cierre (Empeora); "
            "< 0 → disminuyen (Mejora); = 0 → sin cambios."
        )
    return (
        "Variación > 0 → Empeora; < 0 → Mejora; = 0 → sin cambios."
    )


def _frase_cierre(
    verbo: str,
    *,
    variable: str | None = None,
    indicador: str | None = None,
    unidad: str | None = None,
) -> str:
    """Frase auxiliar: «aumentan/disminuyen los días/las horas de cierre…»."""
    if resolver_unidad_cierre(
        unidad=unidad, variable=variable, indicador=indicador
    ) == "dias":
        return f"{verbo.capitalize()} los días de cierre respecto al histórico."
    return f"{verbo.capitalize()} las horas de cierre respecto al histórico."


def interpretar_cambio(
    cambio: float | None,
    *,
    es_historico: bool,
    variable: str | None = None,
    indicador: str | None = None,
    unidad: str | None = None,
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
            _frase_cierre(
                "aumentan",
                variable=variable,
                indicador=indicador,
                unidad=unidad,
            ),
        )
    if cambio < 0:
        return (
            "Mejora",
            _frase_cierre(
                "disminuyen",
                variable=variable,
                indicador=indicador,
                unidad=unidad,
            ),
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
