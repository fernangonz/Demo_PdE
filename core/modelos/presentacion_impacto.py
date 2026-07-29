"""Metadatos de presentación en UI para modelos de impacto."""

from __future__ import annotations

from dataclasses import dataclass

from core.modelos.registro import MODELOS_IMPACTO


@dataclass(frozen=True)
class PresentacionModeloImpacto:
    """Textos y etiquetas mostrados en la fila horizontal de cada modelo."""

    modelo_id: str
    boton_calcular: str
    titulo_opciones: str = "Opciones"


_PRESENTACION: dict[str, PresentacionModeloImpacto] = {
    "PI_AGITACION": PresentacionModeloImpacto(
        modelo_id="PI_AGITACION",
        boton_calcular="Calcular PI superación de umbral",
    ),
}


def presentacion(modelo_id: str) -> PresentacionModeloImpacto:
    if modelo_id in _PRESENTACION:
        return _PRESENTACION[modelo_id]
    meta = MODELOS_IMPACTO[modelo_id].metadatos
    return PresentacionModeloImpacto(
        modelo_id=modelo_id,
        boton_calcular=f"Calcular {meta.nombre}",
    )
