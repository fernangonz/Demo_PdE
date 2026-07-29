"""Resultados por pasos — OPEX (ELS) y CAPEX (ELU) falta de calado."""

from __future__ import annotations

from typing import Any

import pandas as pd

from core.modelos.impacto.pi_agitacion.pasos import (
    PasoResultado,
    ResultadosPorPasos,
    TablaPaso,
    _celda,
    _etiqueta_origen_regla,
)
from core.modelos.impacto.pi_agitacion.schemas import IndicadorEvaluado
from core.modelos.impacto.pi_agitacion.utilidades import ColumnaEscenario, nota_umbral_paso6
from core.modelos.impacto.pi_calado.utilidades import filas_clima_calado_por_escenario
from core.relacion_modelos import IndicadorRelacion


def construir_pasos_activo_calado(
    *,
    nombre_modelo: str,
    tipo_impacto: str,
    tipo_uo: str,
    activo_raw: str,
    calado_buque: float,
    filas_im: list[pd.Series],
) -> list[PasoResultado]:
    """Pasos 3–4 del diagrama de falta de calado (por modelo: OPEX o CAPEX)."""
    pasos: list[PasoResultado] = []

    pasos.append(PasoResultado(
        numero=3,
        nombre=f"Iterar por activos del puerto ({nombre_modelo})",
        excel="Configuración del puerto",
        tablas=[TablaPaso(
            titulo="Output",
            columnas=[
                "Modelo",
                "Tipo UO",
                "Activo físico u Operacional",
                "Dc",
            ],
            filas=[{
                "Modelo": nombre_modelo,
                "Tipo UO": tipo_uo,
                "Activo físico u Operacional": activo_raw,
                "Dc": calado_buque,
            }],
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
    for row in filas_im:
        filas_imp.append({c: _celda(row.get(c)) for c in cols_imp if c in row.index})

    pasos.append(PasoResultado(
        numero=4,
        nombre=f"Buscar impactos asociados al activo ({nombre_modelo})",
        excel="Relación umbrales y curvas de daño vs activos · ListRelacion impactos-indicador",
        tablas=[
            TablaPaso(
                titulo="Input",
                columnas=[
                    "Modelo",
                    "Activo físico u Operacional",
                    "Tipo de impacto (IM)",
                ],
                filas=[{
                    "Modelo": nombre_modelo,
                    "Activo físico u Operacional": activo_raw,
                    "Tipo de impacto (IM)": tipo_impacto,
                }],
            ),
            TablaPaso(
                titulo="Output — filas IM de este modelo",
                columnas=[c for c in cols_imp if filas_imp and c in filas_imp[0]],
                filas=filas_imp,
            ),
        ],
    ))
    return pasos


def _filas_indicadores_encontrados(
    estados: list[IndicadorEvaluado],
) -> list[dict[str, Any]]:
    """Seleccionados primero; después descartados (sin duplicar nombre)."""
    vistos: set[str] = set()
    seleccionados: list[dict[str, Any]] = []
    descartados: list[dict[str, Any]] = []
    for item in estados:
        nombre = str(item.nombre).strip()
        if not nombre or nombre in vistos:
            continue
        vistos.add(nombre)
        fila = {
            "Indicador": nombre,
            "Estado": "Seleccionado" if item.seleccionado else "Descartado",
        }
        if item.seleccionado:
            seleccionados.append(fila)
        else:
            descartados.append(fila)
    return seleccionados + descartados


def construir_pasos_modo_calado(
    *,
    numero_iteracion: int,
    tipo_uo: str,
    activo_raw: str,
    modo_fallo: str,
    modo_fallo_excel: str | None = None,
    etiqueta_im: str,
    nombre_modelo: str,
    variable: str,
    tipo_impacto: str,
    n_relacion: int | None,
    calado_buque: float,
    umbral_m: float,
    umbral_txt: str,
    percentil: str,
    origen_regla: str,
    fila_excel: int | None,
    num_indicadores: int,
    indicadores: tuple[IndicadorRelacion, ...],
    ind_nm: IndicadorRelacion,
    ind_h0: IndicadorRelacion,
    ind_hsed: IndicadorRelacion,
    fila_nm: pd.Series,
    fila_h0: pd.Series,
    fila_hsed: pd.Series,
    col_hist: ColumnaEscenario,
    columnas_fut: list[ColumnaEscenario],
    tabla_resultado: pd.DataFrame,
    indicadores_clima: list[IndicadorEvaluado] | None = None,
) -> list[PasoResultado]:
    """Pasos 5–10 para una iteración IM de falta de calado."""
    pasos: list[PasoResultado] = []
    modo_excel = (modo_fallo_excel or modo_fallo).strip()

    pasos.append(PasoResultado(
        numero=5,
        nombre=f"Iteración por Modos de fallo (IM={numero_iteracion}, {nombre_modelo})",
        excel="Relación umbrales y curvas de daño vs activos · ListRelacion impactos-indicador",
        tablas=[TablaPaso(
            titulo="Output",
            columnas=[
                "Modelo",
                "Nº relación",
                "Modo de fallo / Modo de parada",
                "Variable climática",
                "Tipo de impacto",
            ],
            filas=[{
                "Modelo": nombre_modelo,
                "Nº relación": n_relacion if n_relacion is not None else "",
                "Modo de fallo / Modo de parada": modo_fallo,
                "Variable climática": variable,
                "Tipo de impacto": tipo_impacto,
            }],
        )],
    ))

    filas_5b: list[dict[str, Any]] = [
        {"Campo": "Origen de la regla", "Valor": _etiqueta_origen_regla(origen_regla)},
        {"Campo": "Percentil", "Valor": percentil.upper()},
        {"Campo": "Selección indicador", "Valor": "Predefinido"},
        {"Campo": "No indicadores", "Valor": num_indicadores},
    ]
    if fila_excel is not None:
        filas_5b.append({"Campo": "Fila Excel", "Valor": fila_excel})

    filas_ind_rel: list[dict[str, Any]] = []
    for i, ind in enumerate(indicadores[:num_indicadores], start=1):
        filas_ind_rel.append({
            "Nº": i,
            "Pestaña": ind.pestaña,
            "Indicador climático": ind.indicador,
            "Etiqueta": ind.etiqueta or ind.indicador,
        })

    pasos.append(PasoResultado(
        numero=5,
        nombre="5b. Regla en Relacion_modelos_activos_e_indicadores",
        excel="Relacion_modelos_activos_e_indicadores",
        tablas=[
            TablaPaso(
                titulo="Input",
                columnas=[
                    "Modelo",
                    "Activo físico u Operacional",
                    "Modo de fallo / Modo de parada",
                    "Variable",
                    "Tipo de impacto",
                ],
                filas=[{
                    "Modelo": nombre_modelo,
                    "Activo físico u Operacional": activo_raw,
                    "Modo de fallo / Modo de parada": modo_excel,
                    "Variable": variable,
                    "Tipo de impacto": tipo_impacto,
                }],
            ),
            TablaPaso(
                titulo="Output — regla",
                columnas=["Campo", "Valor"],
                filas=filas_5b,
            ),
            TablaPaso(
                titulo="Output — indicadores",
                columnas=["Nº", "Pestaña", "Indicador climático", "Etiqueta"],
                filas=filas_ind_rel,
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
                    "Nº relación impactos",
                    "Activo físico u Operacional",
                    "Modo de fallo / Modo de parada",
                    "Variable",
                    "Tipo de impacto",
                    "Tipo UO",
                    "Dc",
                ],
                filas=[{
                    "Nº relación impactos": n_relacion if n_relacion is not None else "",
                    "Activo físico u Operacional": activo_raw,
                    "Modo de fallo / Modo de parada": modo_excel,
                    "Variable": variable,
                    "Tipo de impacto": tipo_impacto,
                    "Tipo UO": tipo_uo,
                    "Dc": calado_buque,
                }],
            ),
            TablaPaso(
                titulo="Output",
                columnas=[
                    "Formulación umbral",
                    "Umbral calculado (m)",
                    "Nota",
                ],
                filas=[{
                    "Formulación umbral": umbral_txt,
                    "Umbral calculado (m)": umbral_m,
                    "Nota": nota_umbral_paso6(
                        umbral_txt,
                        umbral_m,
                        calado_buque=calado_buque,
                    ),
                }],
            ),
        ],
    ))

    pasos.append(PasoResultado(
        numero=7,
        nombre="Buscar indicadores climáticos (predefinidos)",
        excel="Indicadores climáticos",
        tablas=[
            TablaPaso(
                titulo="Input",
                columnas=["Modelo", "Variable", "Percentil", "Pestaña"],
                filas=[{
                    "Modelo": nombre_modelo,
                    "Variable": variable,
                    "Percentil": percentil.upper(),
                    "Pestaña": ind_nm.pestaña or "Nivel del mar",
                }],
            ),
            TablaPaso(
                titulo="Indicadores encontrados (seleccionados primero)",
                columnas=["Indicador", "Estado"],
                filas=_filas_indicadores_encontrados(indicadores_clima or []),
            ),
            TablaPaso(
                titulo="Indicadores usados en el cálculo",
                columnas=["Nº", "Rol", "Pestaña", "Indicador climático"],
                filas=[
                    {
                        "Nº": 1,
                        "Rol": "NM",
                        "Pestaña": ind_nm.pestaña,
                        "Indicador climático": ind_nm.indicador,
                    },
                    {
                        "Nº": 2,
                        "Rol": "h0",
                        "Pestaña": ind_h0.pestaña,
                        "Indicador climático": ind_h0.indicador,
                    },
                    {
                        "Nº": 3,
                        "Rol": "h sedimentación",
                        "Pestaña": ind_hsed.pestaña,
                        "Indicador climático": ind_hsed.indicador,
                    },
                ],
            ),
            TablaPaso(
                titulo="Valores por escenario (NM, h0, h sedimentación)",
                columnas=[
                    "Escenario",
                    "NM (m)",
                    "h0 (m)",
                    "h sedimentacion (m)",
                ],
                filas=filas_clima_calado_por_escenario(
                    fila_nm=fila_nm,
                    fila_h0=fila_h0,
                    fila_hsedim=fila_hsed,
                    col_hist=col_hist,
                    columnas_fut=columnas_fut,
                ),
            ),
        ],
    ))

    filas_tabla: list[dict[str, Any]] = []
    for _, row in tabla_resultado.iterrows():
        filas_tabla.append({
            "Escenario": row.get("Escenario"),
            "NM": _celda(row.get("NM")),
            "h sedimentacion": _celda(row.get("h sedimentacion")),
            "h0": _celda(row.get("h0")),
            "h": _celda(row.get("h")),
            "Umbral": _celda(row.get("Umbral")),
            "Interpretación": row.get("Interpretación"),
        })

    pasos.append(PasoResultado(
        numero=8,
        nombre="Aplicar h = NM − h₀ − h sedimentación",
        excel="-",
        tablas=[TablaPaso(
            titulo="Tabla de resultados",
            columnas=[
                "Escenario",
                "NM",
                "h sedimentacion",
                "h0",
                "h",
                "Umbral",
                "Interpretación",
            ],
            filas=filas_tabla,
        )],
    ))

    filas_interp: list[dict[str, Any]] = []
    for _, row in tabla_resultado.iterrows():
        esc = str(row.get("Escenario", ""))
        h = row.get("h")
        interp = str(row.get("Interpretación", ""))
        regla = ""
        if esc != "Histórico" and h is not None and not pd.isna(h):
            regla = "umbral ≤ h → dragar; umbral > h → no dragar"
        filas_interp.append({
            "Escenario": esc,
            "Umbral (m)": umbral_m,
            "h (m)": _celda(h),
            "Interpretación": interp,
            "Regla": regla if regla else "-",
        })

    pasos.append(PasoResultado(
        numero=9,
        nombre="Interpretar el resultado (dragado)",
        excel="-",
        tablas=[TablaPaso(
            titulo=None,
            columnas=["Escenario", "Umbral (m)", "h (m)", "Interpretación", "Regla"],
            filas=filas_interp,
        )],
    ))
    return pasos
