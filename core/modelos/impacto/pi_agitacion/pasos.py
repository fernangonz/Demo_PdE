"""Resultados por pasos del diagrama de flujo — PI superación de umbral."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from core.data_loader import _a_numero
from core.modelos.impacto.pi_agitacion.interpretacion import etiqueta_interpretacion_paso
from core.modelos.impacto.pi_agitacion.utilidades import ColumnaEscenario


@dataclass
class TablaPaso:
    titulo: str | None
    columnas: list[str]
    filas: list[dict[str, Any]]


@dataclass
class PasoResultado:
    numero: int
    nombre: str
    excel: str
    tablas: list[TablaPaso] = field(default_factory=list)


@dataclass
class ResultadosPorPasos:
    modelo_id: str = "PI_AGITACION"
    pasos: list[PasoResultado] = field(default_factory=list)


def _celda(valor: object) -> object:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    return valor


def _interpretacion_paso8(interpretacion: str, texto_auxiliar: str) -> str:
    return etiqueta_interpretacion_paso(interpretacion, texto_auxiliar)


def construir_pasos_activo(
    *,
    tipo_uo: str,
    activo_raw: str,
    impactos: pd.DataFrame,
) -> list[PasoResultado]:
    """Pasos 3–4: activo e impactos asociados."""
    pasos: list[PasoResultado] = []

    pasos.append(PasoResultado(
        numero=3,
        nombre="Iterar por activos del puerto",
        excel="Configuración del puerto",
        tablas=[TablaPaso(
            titulo="Output",
            columnas=["Tipo UO", "Activo físico u Operacional"],
            filas=[{"Tipo UO": tipo_uo, "Activo físico u Operacional": activo_raw}],
        )],
    ))

    cols_imp = [
        "Nº",
        "Tipo de impacto",
        "Modos de fallo / Modos de parada",
        "Variable",
        "Activo físico u Operacional",
        "Tipo activo/servicio",
    ]
    filas_imp: list[dict[str, Any]] = []
    for _, row in impactos.iterrows():
        filas_imp.append({c: _celda(row.get(c)) for c in cols_imp if c in impactos.columns})

    pasos.append(PasoResultado(
        numero=4,
        nombre="Buscar impacto",
        excel="Relación umbrales y curvas de daño vs activos · ListRelacion impactos-indicador",
        tablas=[
            TablaPaso(
                titulo="Input",
                columnas=["Activo físico u Operacional"],
                filas=[{"Activo físico u Operacional": activo_raw}],
            ),
            TablaPaso(
                titulo="Output",
                columnas=[c for c in cols_imp if c in impactos.columns],
                filas=filas_imp,
            ),
        ],
    ))
    return pasos


def _etiqueta_origen_regla(origen: str) -> str:
    if origen == "excel":
        return "Excel (Relacion_modelos_activos_e_indicadores)"
    return "Diagrama (umbral + P99 + filtros por Tipo UO)"


def construir_pasos_modo_fallo(
    *,
    numero_iteracion: int,
    tipo_uo: str,
    activo_raw: str,
    modo_fallo: str,
    variable: str,
    umbral_m: float | None,
    umbral_txt: str,
    percentil: str,
    origen_regla: str = "diagrama",
    indicador_predefinido: bool = False,
    indicador_config: str | None = None,
    fila_excel: int | None = None,
    fila_ind: pd.Series,
    col_hist: ColumnaEscenario,
    columnas_fut: list[ColumnaEscenario],
    tabla_variacion: pd.DataFrame,
) -> list[PasoResultado]:
    """Pasos 5–8 para una iteración IM (modo de fallo)."""
    pasos: list[PasoResultado] = []
    umbral_mostrar = umbral_m if umbral_m is not None else umbral_txt

    pasos.append(PasoResultado(
        numero=5,
        nombre=f"Iteración por Modos de fallo (IM={numero_iteracion})",
        excel="Relación umbrales y curvas de daño vs activos · ListRelacion impactos-indicador",
        tablas=[TablaPaso(
            titulo="Input",
            columnas=["Modos de fallo / Modos de parada"],
            filas=[{"Modos de fallo / Modos de parada": modo_fallo}],
        )],
    ))

    filas_5b: list[dict[str, Any]] = [
        {
            "Campo": "Origen de la regla",
            "Valor": _etiqueta_origen_regla(origen_regla),
        },
        {"Campo": "Percentil", "Valor": percentil.upper()},
        {
            "Campo": "Selección indicador",
            "Valor": "Predefinido" if indicador_predefinido else "Por umbral",
        },
    ]
    if fila_excel is not None:
        filas_5b.append({"Campo": "Fila Excel", "Valor": fila_excel})
    if indicador_config:
        filas_5b.append({"Campo": "Indicador (Excel)", "Valor": indicador_config})

    pasos.append(PasoResultado(
        numero=5,
        nombre="5b. Regla en Relacion_modelos_activos_e_indicadores",
        excel="Relacion_modelos_activos_e_indicadores",
        tablas=[
            TablaPaso(
                titulo="Input",
                columnas=[
                    "Activo físico u Operacional",
                    "Modos de fallo / Modos de parada",
                    "Variable",
                ],
                filas=[{
                    "Activo físico u Operacional": activo_raw,
                    "Modos de fallo / Modos de parada": modo_fallo,
                    "Variable": variable,
                }],
            ),
            TablaPaso(
                titulo="Output",
                columnas=["Campo", "Valor"],
                filas=filas_5b,
            ),
        ],
    ))

    pasos.append(PasoResultado(
        numero=6,
        nombre="Buscar el umbral correspondiente",
        excel="Relación umbrales y curvas de daño vs activos",
        tablas=[
            TablaPaso(
                titulo="Input",
                columnas=[
                    "Activo físico u Operacional",
                    "Modos de fallo / Modos de parada",
                    "Variable",
                    "Tipo UO",
                ],
                filas=[{
                    "Activo físico u Operacional": activo_raw,
                    "Modos de fallo / Modos de parada": modo_fallo,
                    "Variable": variable,
                    "Tipo UO": tipo_uo,
                }],
            ),
            TablaPaso(
                titulo="Output",
                columnas=[
                    "Modos de fallo / Modos de parada",
                    "Variable",
                    "Activo físico u Operacional",
                    "Umbral",
                    "Nota",
                ],
                filas=[{
                    "Modos de fallo / Modos de parada": modo_fallo,
                    "Variable": variable,
                    "Activo físico u Operacional": activo_raw,
                    "Umbral": umbral_mostrar,
                    "Nota": (
                        "No aplica: indicador predefinido en Excel (paso 5b)"
                        if indicador_predefinido and origen_regla == "excel"
                        else ""
                    ),
                }],
            ),
        ],
    ))

    nombre_ind = str(fila_ind.get("Indicador", "")).strip()
    pct_num = percentil.upper().replace("P", "")
    filas_escenario: list[dict[str, Any]] = [
        {"Campo": "Indicador", "Valor": nombre_ind},
        {"Campo": "Percentil", "Valor": pct_num},
        {"Campo": "Percentil", "Valor": percentil.upper()},
    ]
    todas_cols = [col_hist] + columnas_fut
    for col in todas_cols:
        val = _a_numero(fila_ind.get(col.columna))
        if val is not None and not pd.isna(val):
            val = int(round(val))
        filas_escenario.append({"Campo": col.columna, "Valor": _celda(val)})

    pasos.append(PasoResultado(
        numero=7,
        nombre="Buscar el indicador climático",
        excel="Indicadores climáticos",
        tablas=[
            TablaPaso(
                titulo="Input",
                columnas=["Variable", "Percentil", "Origen regla", "Modo selección"],
                filas=[{
                    "Variable": variable,
                    "Percentil": pct_num,
                    "Origen regla": _etiqueta_origen_regla(origen_regla),
                    "Modo selección": (
                        "Predefinido (Excel)" if indicador_predefinido
                        else "Por umbral"
                    ),
                }],
            ),
            TablaPaso(
                titulo="Output",
                columnas=["Campo", "Valor"],
                filas=filas_escenario,
            ),
        ],
    ))

    from core.modelos.impacto.pi_agitacion.utilidades import etiqueta_escenario

    filas_var: list[dict[str, Any]] = []
    fila_hist = tabla_variacion[tabla_variacion["Escenario"] == "Histórico"]
    hist_ind = fila_hist.iloc[0]["Indicador"] if not fila_hist.empty else None
    filas_var.append({
        "Indicador": col_hist.columna,
        "Valor indicador": _celda(hist_ind),
        "Variación": "-",
        "Interpretación": "-",
    })

    for col in columnas_fut:
        etiqueta = etiqueta_escenario(col.escenario, col.anio)
        sub = tabla_variacion[tabla_variacion["Escenario"] == etiqueta]
        if sub.empty:
            val_ind = _a_numero(fila_ind.get(col.columna))
            if val_ind is not None and not pd.isna(val_ind):
                val_ind = int(round(val_ind))
            else:
                val_ind = None
            cambio = None
            interp = "—"
            texto = ""
        else:
            r = sub.iloc[0]
            val_ind = r["Indicador"]
            cambio = r["Cambio respecto al histórico"]
            interp = str(r["Interpretación"])
            texto = str(r.get("Texto auxiliar", ""))

        if cambio is None or (isinstance(cambio, float) and pd.isna(cambio)):
            cambio_mostrar = ""
        else:
            cambio_mostrar = int(cambio)

        filas_var.append({
            "Indicador": col.columna,
            "Valor indicador": _celda(val_ind),
            "Variación": cambio_mostrar,
            "Interpretación": _interpretacion_paso8(interp, texto),
        })

    pasos.append(PasoResultado(
        numero=8,
        nombre="Calcular la variación",
        excel="-",
        tablas=[TablaPaso(
            titulo=None,
            columnas=["Indicador", "Valor indicador", "Variación", "Interpretación"],
            filas=filas_var,
        )],
    ))
    return pasos


def construir_resultados_por_pasos(
    *,
    tipo_uo: str,
    activo_raw: str,
    impactos: pd.DataFrame,
    modo_fallo: str,
    variable: str,
    umbral_m: float | None,
    percentil: str,
    fila_ind: pd.Series,
    col_hist: ColumnaEscenario,
    columnas_fut: list[ColumnaEscenario],
    tabla_variacion: pd.DataFrame,
    umbral_txt: str | None = None,
    numero_iteracion: int = 1,
) -> ResultadosPorPasos:
    """Construye la trazabilidad paso a paso (estructura del Excel de comprobación)."""
    umbral_etiqueta = umbral_txt or (str(umbral_m) if umbral_m is not None else "")
    pasos = construir_pasos_activo(
        tipo_uo=tipo_uo,
        activo_raw=activo_raw,
        impactos=impactos,
    )
    pasos.extend(construir_pasos_modo_fallo(
        numero_iteracion=numero_iteracion,
        tipo_uo=tipo_uo,
        activo_raw=activo_raw,
        modo_fallo=modo_fallo,
        variable=variable,
        umbral_m=umbral_m,
        umbral_txt=umbral_etiqueta,
        percentil=percentil,
        fila_ind=fila_ind,
        col_hist=col_hist,
        columnas_fut=columnas_fut,
        tabla_variacion=tabla_variacion,
    ))
    return ResultadosPorPasos(pasos=pasos)
