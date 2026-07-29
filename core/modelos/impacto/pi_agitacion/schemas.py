"""Esquemas del modelo PI_AGITACION (independientes del resto de modelos)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from core.schemas.base import MetadatosModelo, ResultadoModelo
from core.schemas.serializacion import dataframe_a_registros

MODELO_ID = "PI_AGITACION"
MODELO_VERSION = "1.0.0"
BASELINE_YEAR = 2005
MODO_FALLO_DEFAULT = "Exceso de oleaje"
VARIABLE_DEFAULT = "Oleaje"

METADATOS = MetadatosModelo(
    id=MODELO_ID,
    nombre="PI superación de umbral (oleaje, viento, corriente y visibilidad)",
    version=MODELO_VERSION,
    categoria="impacto",
    descripcion=(
        "Diagrama único «Superación de umbral»: paso 5b consulta "
        "Relacion_modelos_activos_e_indicadores.xlsx; si hay fila explícita usa "
        "percentil e indicador del Excel, si no sigue umbral + P99 + filtros del diagrama."
    ),
)

ADVERTENCIA_INDICADOR_NEGATIVO = (
    "Advertencia: este indicador representa horas de cierre y no debería tener "
    "valores negativos. Revisar el dato de origen o la fórmula de cálculo."
)


@dataclass
class ParametrosEntrada:
    """Parámetros de entrada del modelo (percentil/indicador en Excel paso 5b o diagrama)."""

    tipo_uo: str | None = None
    activo: str | None = None
    modo_fallo: str = MODO_FALLO_DEFAULT
    variable_climatica: str = VARIABLE_DEFAULT
    baseline_year: int = BASELINE_YEAR


@dataclass
class IndicadorEvaluado:
    nombre: str
    seleccionado: bool
    descartado: bool = False


@dataclass
class IteracionResultado:
    """Una iteración IM (modo de fallo) dentro del activo actual."""

    numero: int
    modo_fallo: str
    variable_climatica: str
    umbral: str
    indicador_seleccionado: str
    percentil: str
    origen_regla: str = "diagrama"
    indicadores_evaluados: list[IndicadorEvaluado] = field(default_factory=list)
    sintesis_cambios: SintesisCambios | None = None
    advertencias: list[str] = field(default_factory=list)
    _tabla_resultado_df: pd.DataFrame = field(
        default_factory=pd.DataFrame,
        repr=False,
        compare=False,
    )

    @property
    def tabla_resultado(self) -> pd.DataFrame:
        return self._tabla_resultado_df


@dataclass
class SintesisCambios:
    mayor_empeoramiento: str | None = None
    mayor_empeoramiento_cambio: float | None = None
    mayor_mejora: str | None = None
    mayor_mejora_cambio: float | None = None
    n_empeoran: int = 0
    n_mejoran: int = 0


@dataclass
class ResultadoPIAgitacion(ResultadoModelo):
    """Salida completa del modelo PI_AGITACION."""

    iteraciones: list[IteracionResultado] = field(default_factory=list)
    indicadores_evaluados: list[IndicadorEvaluado] = field(default_factory=list)
    sintesis_cambios: SintesisCambios | None = None
    resultados_por_pasos: Any = None
    _tabla_resultado_df: pd.DataFrame = field(
        default_factory=pd.DataFrame,
        repr=False,
        compare=False,
    )

    @property
    def tabla_resultado(self) -> pd.DataFrame:
        """DataFrame para la UI actual (Streamlit)."""
        if not self._tabla_resultado_df.empty:
            return self._tabla_resultado_df
        return self.tabla_como_dataframe("resultado_escenarios")

    @classmethod
    def error(cls, mensaje: str) -> ResultadoPIAgitacion:
        return cls(metadatos=METADATOS, ok=False, error=mensaje)

    @classmethod
    def desde_calculo(
        cls,
        *,
        metadatos_ejecucion: dict[str, Any],
        iteraciones: list[IteracionResultado],
        resultados_por_pasos=None,
    ) -> ResultadoPIAgitacion:
        if not iteraciones:
            return cls.error("No se generó ninguna iteración.")

        primera = iteraciones[0]
        advertencias = [
            adv
            for it in iteraciones
            for adv in it.advertencias
        ]
        tablas = {
            f"resultado_escenarios_iter_{it.numero}": dataframe_a_registros(it.tabla_resultado)
            for it in iteraciones
        }
        sintesis = primera.sintesis_cambios or SintesisCambios()

        return cls(
            metadatos=METADATOS,
            ok=True,
            advertencias=advertencias,
            metadatos_ejecucion=metadatos_ejecucion,
            tablas=tablas,
            sintesis={
                "mayor_empeoramiento": sintesis.mayor_empeoramiento,
                "mayor_empeoramiento_cambio": sintesis.mayor_empeoramiento_cambio,
                "mayor_mejora": sintesis.mayor_mejora,
                "mayor_mejora_cambio": sintesis.mayor_mejora_cambio,
            },
            iteraciones=iteraciones,
            indicadores_evaluados=primera.indicadores_evaluados,
            sintesis_cambios=primera.sintesis_cambios,
            resultados_por_pasos=resultados_por_pasos,
            _tabla_resultado_df=primera.tabla_resultado,
        )

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base["iteraciones"] = [
            {
                "numero": it.numero,
                "modo_fallo": it.modo_fallo,
                "variable_climatica": it.variable_climatica,
                "umbral": it.umbral,
                "indicador_seleccionado": it.indicador_seleccionado,
                "percentil": it.percentil,
                "origen_regla": it.origen_regla,
                "tabla_resultado": dataframe_a_registros(it.tabla_resultado),
            }
            for it in self.iteraciones
        ]
        base["indicadores_evaluados"] = [
            {"nombre": i.nombre, "seleccionado": i.seleccionado, "descartado": i.descartado}
            for i in self.indicadores_evaluados
        ]
        if self.sintesis_cambios:
            base["sintesis_cambios"] = {
                "mayor_empeoramiento": self.sintesis_cambios.mayor_empeoramiento,
                "mayor_empeoramiento_cambio": self.sintesis_cambios.mayor_empeoramiento_cambio,
                "mayor_mejora": self.sintesis_cambios.mayor_mejora,
                "mayor_mejora_cambio": self.sintesis_cambios.mayor_mejora_cambio,
            }
        base.pop("_tabla_resultado_df", None)
        return base
