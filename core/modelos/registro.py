"""Registro central de modelos — punto único para listar y ejecutar."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.modelos.impacto.pi_agitacion.calcular import calcular as calcular_pi_agitacion
from core.modelos.impacto.pi_agitacion.schemas import (
    METADATOS as PI_AGITACION_META,
    ParametrosEntrada,
    ResultadoPIAgitacion,
)
from core.modelos.impacto.pi_calado.calcular import calcular as calcular_pi_calado
from core.modelos.impacto.pi_calado.schemas import (
    METADATOS as PI_CALADO_ELS_META,
    METADATOS_ELO as PI_CALADO_ELO_META,
    METADATOS_ELU as PI_CALADO_ELU_META,
    ParametrosEntrada as ParametrosCalado,
    ResultadoPICalado,
)
from core.modelos.impacto.pi_francobordo.calcular import calcular as calcular_pi_francobordo
from core.modelos.impacto.pi_francobordo.schemas import (
    METADATOS as PI_FRANCOBORDO_META,
    ParametrosEntrada as ParametrosFrancobordo,
    ResultadoPIFrancobordo,
)
from core.modelos.impacto.pi_precipitacion.calcular import calcular as calcular_pi_precipitacion
from core.modelos.impacto.pi_precipitacion.schemas import (
    METADATOS as PI_PRECIPITACION_META,
    ParametrosEntrada as ParametrosPrecipitacion,
    ResultadoPIPrecipitacion,
)
from core.schemas.base import MetadatosModelo, ResultadoModelo


@dataclass(frozen=True)
class DefinicionModelo:
    """Descriptor de un modelo registrado."""

    metadatos: MetadatosModelo
    calcular: Callable[..., ResultadoModelo]
    parametros_tipo: type


MODELOS_IMPACTO: dict[str, DefinicionModelo] = {
    PI_AGITACION_META.id: DefinicionModelo(
        metadatos=PI_AGITACION_META,
        calcular=calcular_pi_agitacion,
        parametros_tipo=ParametrosEntrada,
    ),
    PI_CALADO_ELO_META.id: DefinicionModelo(
        metadatos=PI_CALADO_ELO_META,
        calcular=calcular_pi_calado,
        parametros_tipo=ParametrosCalado,
    ),
    PI_CALADO_ELS_META.id: DefinicionModelo(
        metadatos=PI_CALADO_ELS_META,
        calcular=calcular_pi_calado,
        parametros_tipo=ParametrosCalado,
    ),
    PI_CALADO_ELU_META.id: DefinicionModelo(
        metadatos=PI_CALADO_ELU_META,
        calcular=calcular_pi_calado,
        parametros_tipo=ParametrosCalado,
    ),
    PI_FRANCOBORDO_META.id: DefinicionModelo(
        metadatos=PI_FRANCOBORDO_META,
        calcular=calcular_pi_francobordo,
        parametros_tipo=ParametrosFrancobordo,
    ),
    PI_PRECIPITACION_META.id: DefinicionModelo(
        metadatos=PI_PRECIPITACION_META,
        calcular=calcular_pi_precipitacion,
        parametros_tipo=ParametrosPrecipitacion,
    ),
}

MODELOS_ECONOMICO: dict[str, DefinicionModelo] = {}


def listar_modelos_impacto() -> list[MetadatosModelo]:
    return [m.metadatos for m in MODELOS_IMPACTO.values()]


def listar_modelos_economico() -> list[MetadatosModelo]:
    return [m.metadatos for m in MODELOS_ECONOMICO.values()]


def ejecutar_modelo_impacto(
    modelo_id: str,
    datos: Any,
    params: Any | None = None,
) -> ResultadoModelo:
    """Ejecuta un modelo de impacto por id."""
    definicion = MODELOS_IMPACTO.get(modelo_id)
    if definicion is None:
        return ResultadoModelo(
            metadatos=MetadatosModelo(
                id=modelo_id,
                nombre=modelo_id,
                version="0",
                categoria="impacto",
            ),
            ok=False,
            error=f"Modelo de impacto no registrado: {modelo_id}",
        )
    if params is None:
        params = definicion.parametros_tipo()
    return definicion.calcular(datos, params)


def ejecutar_pi_agitacion(
    datos: Any,
    params: ParametrosEntrada | None = None,
    **kwargs: Any,
) -> ResultadoPIAgitacion:
    """Atajo tipado para PI_AGITACION."""
    if params is None:
        params = ParametrosEntrada(**kwargs) if kwargs else ParametrosEntrada()
    resultado = ejecutar_modelo_impacto(PI_AGITACION_META.id, datos, params)
    assert isinstance(resultado, ResultadoPIAgitacion)
    return resultado


def ejecutar_pi_calado(
    datos: Any,
    params: ParametrosCalado | None = None,
    **kwargs: Any,
) -> ResultadoPICalado:
    """Atajo tipado para PI_CALADO_ELO / PI_CALADO_ELS / PI_CALADO_ELU."""
    if params is None:
        params = ParametrosCalado(**kwargs) if kwargs else ParametrosCalado()
    resultado = ejecutar_modelo_impacto(params.modelo_id, datos, params)
    assert isinstance(resultado, ResultadoPICalado)
    return resultado


def ejecutar_pi_francobordo(
    datos: Any,
    params: ParametrosFrancobordo | None = None,
    **kwargs: Any,
) -> ResultadoPIFrancobordo:
    """Atajo tipado para PI_FRANCOBORDO."""
    if params is None:
        params = ParametrosFrancobordo(**kwargs) if kwargs else ParametrosFrancobordo()
    resultado = ejecutar_modelo_impacto(PI_FRANCOBORDO_META.id, datos, params)
    assert isinstance(resultado, ResultadoPIFrancobordo)
    return resultado


def ejecutar_pi_precipitacion(
    datos: Any,
    params: ParametrosPrecipitacion | None = None,
    **kwargs: Any,
) -> ResultadoPIPrecipitacion:
    """Atajo tipado para PI_PRECIPITACION."""
    if params is None:
        params = (
            ParametrosPrecipitacion(**kwargs) if kwargs else ParametrosPrecipitacion()
        )
    resultado = ejecutar_modelo_impacto(PI_PRECIPITACION_META.id, datos, params)
    assert isinstance(resultado, ResultadoPIPrecipitacion)
    return resultado
