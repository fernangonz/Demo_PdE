"""Inputs del activo leidos de Configuracion del puerto (ArcGIS -> Excel)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.data_loader import _normalizar
from core.modelos.impacto.pi_agitacion.utilidades import columna_por_patron


@dataclass(frozen=True)
class CampoInputActivo:
    id: str
    etiqueta: str
    unidad: str
    patrones_columna: tuple[str, ...]


INPUTS_CONFIG_PUERTO: tuple[CampoInputActivo, ...] = (
    CampoInputActivo(
        id="calado_buque",
        etiqueta="Dc",
        unidad="m",
        patrones_columna=(
            "dc",
            "calado del buque (dc)",
            "calado del buque",
            "calado buque",
        ),
    ),
    CampoInputActivo(
        id="cota_muelle",
        etiqueta="Rc",
        unidad="m",
        patrones_columna=(
            "rc",
            "cota del muelle",
            "cota muelle",
        ),
    ),
    CampoInputActivo(
        id="francobordo",
        etiqueta="Fb",
        unidad="m",
        patrones_columna=(
            "fb",
            "francobordo",
            "franco bordo",
        ),
    ),
)

# Falta de calado solo exige Dc; Rc y Fb son opcionales segun activo.
INPUTS_CALADO_ACTIVO: tuple[CampoInputActivo, ...] = (INPUTS_CONFIG_PUERTO[0],)

# Alias historico
INPUTS_FALTA_CALADO = INPUTS_CALADO_ACTIVO

INDICADOR_HSEDIMENTACION = "Tasa de sedimentacion anual"

IDS_MODOS_FALTA_CALADO = frozenset({
    "falta_calado_elo",
    "falta_calado_els",
    "falta_calado_elu",
})


def es_modo_falta_calado(entrada_id: str) -> bool:
    return entrada_id in IDS_MODOS_FALTA_CALADO


def _parse_valor_positivo(valor: object) -> float | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip()
    if not texto or texto.lower() in ("nan", "none", "-"):
        return None
    try:
        numero = float(texto.replace(",", "."))
    except ValueError:
        return None
    return numero if numero > 0 else None


def _parse_valor_no_negativo(valor: object) -> float | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    try:
        numero = float(str(valor).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None
    return numero if numero >= 0 else None


def _coincidencia_exacta(columnas: list[str], patron: str) -> str | None:
    objetivo = _normalizar(patron)
    for col in columnas:
        if _normalizar(col) == objetivo:
            return col
    return None


def _resolver_columna(columnas: list[str], patrones: tuple[str, ...]) -> str | None:
    for patron in patrones:
        exacta = _coincidencia_exacta(columnas, patron)
        if exacta:
            return exacta
    for patron in patrones:
        col = columna_por_patron(columnas, patron)
        if col:
            return col
    return None


def leer_inputs_desde_fila(
    fila: pd.Series,
    columnas: list[str],
    campos: tuple[CampoInputActivo, ...],
) -> dict[str, float | None]:
    """Valores del Excel para el activo; None si la celda esta vacia o no es valida."""
    valores: dict[str, float | None] = {}
    for campo in campos:
        col = _resolver_columna(columnas, campo.patrones_columna)
        valores[campo.id] = _parse_valor_positivo(fila.get(col)) if col else None
    return valores


def leer_inputs_config_activo_desde_fila(
    fila: pd.Series,
    columnas: list[str],
) -> dict[str, float | None]:
    """Dc, Rc y Fb del activo desde Configuracion del puerto."""
    return leer_inputs_desde_fila(fila, columnas, INPUTS_CONFIG_PUERTO)


def leer_calado_activo_desde_fila(
    fila: pd.Series,
    columnas: list[str],
) -> dict[str, float | None]:
    """Dc del activo desde Configuracion del puerto."""
    return leer_inputs_desde_fila(fila, columnas, INPUTS_CALADO_ACTIVO)


def valores_calado_desde_session(session_state: dict) -> dict[str, float | None]:
    return {
        campo.id: session_state.get(f"input_activo_{campo.id}")
        for campo in INPUTS_CALADO_ACTIVO
    }


def validar_inputs_positivos(
    valores: dict[str, float | None],
    campos: tuple[CampoInputActivo, ...],
) -> list[str]:
    """Devuelve mensajes de error si falta algun input requerido o no es positivo."""
    errores: list[str] = []
    for campo in campos:
        valor = valores.get(campo.id)
        if valor is None:
            errores.append(
                f"{campo.etiqueta} ({campo.unidad}): obligatorio, valor numerico positivo."
            )
        elif valor <= 0:
            errores.append(
                f"{campo.etiqueta} ({campo.unidad}): debe ser mayor que 0."
            )
    return errores
