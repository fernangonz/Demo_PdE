"""Utilidades para serializar resultados de modelos (JSON / API / otra UI)."""

from __future__ import annotations

from dataclasses import asdict, fields, is_dataclass
from typing import Any

import pandas as pd


def valor_serializable(valor: Any) -> Any:
    """Convierte un valor a tipos estándar de Python/JSON."""
    if valor is None:
        return None
    if isinstance(valor, (str, int, bool)):
        return valor
    if isinstance(valor, float):
        if pd.isna(valor):
            return None
        return valor
    if isinstance(valor, pd.DataFrame):
        return dataframe_a_registros(valor)
    if isinstance(valor, pd.Series):
        return valor.to_dict()
    if is_dataclass(valor):
        return dataclass_a_dict(valor)
    if isinstance(valor, dict):
        return {str(k): valor_serializable(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [valor_serializable(v) for v in valor]
    return str(valor)


def dataclass_a_dict(obj: Any) -> dict[str, Any]:
    """Serializa un dataclass recursivamente."""
    if not is_dataclass(obj):
        raise TypeError(f"No es un dataclass: {type(obj)!r}")
    return {f.name: valor_serializable(getattr(obj, f.name)) for f in fields(obj)}


def dataframe_a_registros(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame → lista de dicts (orient='records') con NaN → None."""
    if df.empty:
        return []
    limpio = df.where(pd.notna(df), None)
    return [
        {str(k): valor_serializable(v) for k, v in fila.items()}
        for fila in limpio.to_dict(orient="records")
    ]
