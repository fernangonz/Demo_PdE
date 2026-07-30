"""Contrato de trazabilidad: cada activo/modo deja una ejecucion auditable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import pandas as pd

EstadoEjecucion = Literal["ok", "warning", "error", "skipped"]

STEP_ID_POR_NUMERO: dict[int, str] = {
    3: "iterar_activos",
    4: "buscar_impacto",
    5: "definir_im",
    6: "resolver_umbral",
    7: "resolver_indicadores",
    8: "calcular_impacto",
    9: "interpretar_resultado",
}


@dataclass
class PasoEjecucion:
    """Un paso de trazabilidad (compatible con PasoResultado de la UI)."""

    numero: int
    nombre: str
    excel: str = ""
    step_id: str = ""
    status: EstadoEjecucion = "ok"
    error_code: str | None = None
    procedimiento: str = ""
    tablas: list[Any] = field(default_factory=list)

    @classmethod
    def desde_paso(cls, paso: Any, *, status: EstadoEjecucion = "ok") -> PasoEjecucion:
        numero = int(getattr(paso, "numero", 0) or 0)
        step_id = str(getattr(paso, "step_id", "") or "")
        if not step_id:
            step_id = STEP_ID_POR_NUMERO.get(numero, f"paso_{numero}")
        status_raw = getattr(paso, "status", status) or status
        return cls(
            numero=numero,
            nombre=str(getattr(paso, "nombre", "")),
            excel=str(getattr(paso, "excel", "") or ""),
            step_id=step_id,
            status=status_raw,  # type: ignore[arg-type]
            error_code=getattr(paso, "error_code", None),
            procedimiento=str(getattr(paso, "procedimiento", "") or ""),
            tablas=list(getattr(paso, "tablas", []) or []),
        )


@dataclass
class IteracionEjecucion:
    """Una iteracion IM (activo + modo de fallo) con diagnostico y pasos."""

    numero: int
    activo: str
    modo_fallo: str
    motor_id: str
    tipo_impacto: str
    familia: str
    estado: EstadoEjecucion = "ok"
    motivo: str | None = None
    error_code: str | None = None
    modo_fallo_excel: str = ""
    variable: str = ""
    umbral: str = ""
    percentil: str = ""
    indicador_seleccionado: str = ""
    origen_regla: str = ""
    inputs_usados: dict[str, Any] = field(default_factory=dict)
    pasos: list[PasoEjecucion] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    _tabla_resultado_df: pd.DataFrame = field(
        default_factory=pd.DataFrame,
        repr=False,
        compare=False,
    )

    @property
    def tabla_resultado(self) -> pd.DataFrame:
        return self._tabla_resultado_df

    @property
    def ok(self) -> bool:
        return self.estado == "ok"

    def resumen_una_linea(self) -> str:
        if self.estado == "ok":
            return f"OK | {self.familia} | {self.motor_id}"
        if self.motivo:
            return f"{self.estado.upper()} | {self.motivo}"
        return f"{self.estado.upper()} | {self.error_code or 'sin detalle'}"


def familia_desde_tipo_impacto(tipo_impacto: str) -> str:
    t = (tipo_impacto or "").strip().upper()
    if t == "ELO":
        return "PI"
    if t == "ELS":
        return "OPEX"
    if t == "ELU":
        return "CAPEX"
    return ""


def envolver_pasos(pasos: list[Any], *, status: EstadoEjecucion = "ok") -> list[PasoEjecucion]:
    return [PasoEjecucion.desde_paso(p, status=status) for p in pasos]


__all__ = [
    "EstadoEjecucion",
    "STEP_ID_POR_NUMERO",
    "PasoEjecucion",
    "IteracionEjecucion",
    "familia_desde_tipo_impacto",
    "envolver_pasos",
]
