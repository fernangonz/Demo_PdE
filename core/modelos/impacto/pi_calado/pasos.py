"""Resultados por pasos — PI (ELO), OPEX (ELS) y CAPEX (ELU) falta de calado.

Cada paso es un PROCEDURE auditable: Excel | INPUT/MATCH | ACCION | OUTPUT.
"""

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

_TITULO_ENTRADA = "1. Entrada (claves de busqueda)"
_TITULO_MATCH = "2. Match / accion"
_TITULO_SALIDA = "3. Salida"

_EXCEL_CONFIG = "Configuracion del puerto"
_EXCEL_LIST_REL = (
    "Relacion umbrales y curvas de dano vs activos | ListRelacion impactos-indicador"
)
_EXCEL_REL_MODELOS = "Relacion_modelos_activos_e_indicadores"
_EXCEL_UMBRALES = "Relacion umbrales y curvas de dano vs activos"
_EXCEL_CLIMA = "Indicadores climaticos"


def construir_pasos_activo_calado(
    *,
    nombre_modelo: str,
    tipo_impacto: str,
    tipo_uo: str,
    activo_raw: str,
    calado_buque: float,
    filas_im: list[pd.Series],
) -> list[PasoResultado]:
    """Pasos 3-4 del diagrama de falta de calado (por modelo: OPEX o CAPEX)."""
    pasos: list[PasoResultado] = []

    pasos.append(PasoResultado(
        numero=3,
        nombre="Extraer activo y Dc desde Configuracion del puerto",
        excel=_EXCEL_CONFIG,
        procedimiento=(
            "1. Abro Excel: Configuracion del puerto\n"
            "2. Localizo la fila del activo en calculo\n"
            "3. Extraigo: Tipo UO, Activo, Dc (calado del buque)"
        ),
        tablas=[
            TablaPaso(
                titulo=_TITULO_ENTRADA,
                columnas=["Activo buscado", "Modelo"],
                filas=[{"Activo buscado": activo_raw, "Modelo": nombre_modelo}],
            ),
            TablaPaso(
                titulo=_TITULO_SALIDA,
                columnas=[
                    "Modelo",
                    "Tipo UO",
                    "Activo fisico u Operacional",
                    "Dc",
                ],
                filas=[{
                    "Modelo": nombre_modelo,
                    "Tipo UO": tipo_uo,
                    "Activo fisico u Operacional": activo_raw,
                    "Dc": calado_buque,
                }],
            ),
        ],
    ))

    cols_imp_excel = [
        "Nº",
        "Tipo de impacto",
        "Modos de fallo / Modos de parada",
        "Variable",
        "Activo físico u Operacional",
        "Tipo activo/servicio",
    ]
    filas_imp: list[dict[str, Any]] = []
    for row in filas_im:
        filas_imp.append({c: _celda(row.get(c)) for c in cols_imp_excel if c in row.index})

    pasos.append(PasoResultado(
        numero=4,
        nombre="Filtrar filas IM de falta de calado en ListRelacion",
        excel=_EXCEL_LIST_REL,
        procedimiento=(
            "1. Abro Excel: Relacion umbrales... hoja ListRelacion impactos-indicador\n"
            f"2. Filtro / match: Activo = [{activo_raw}] AND Tipo de impacto = "
            f"[{tipo_impacto}] AND modo contiene Falta de Calado\n"
            "3. Extraigo las filas IM de este modelo"
        ),
        tablas=[
            TablaPaso(
                titulo=_TITULO_ENTRADA,
                columnas=[
                    "Modelo",
                    "Activo fisico u Operacional",
                    "Tipo de impacto (IM)",
                    "Filtro modo",
                ],
                filas=[{
                    "Modelo": nombre_modelo,
                    "Activo fisico u Operacional": activo_raw,
                    "Tipo de impacto (IM)": tipo_impacto,
                    "Filtro modo": "contiene Falta de Calado",
                }],
            ),
            TablaPaso(
                titulo=_TITULO_SALIDA,
                columnas=[c for c in cols_imp_excel if filas_imp and c in filas_imp[0]],
                filas=filas_imp,
            ),
        ],
    ))
    return pasos


def _filas_indicadores_encontrados(
    estados: list[IndicadorEvaluado],
) -> list[dict[str, Any]]:
    """Seleccionados primero; despues descartados (sin duplicar nombre)."""
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


def _tabla_match(accion: str, claves: str = "") -> TablaPaso:
    filas: list[dict[str, Any]] = [{"Accion": accion}]
    if claves:
        filas[0]["Claves"] = claves
    cols = ["Accion"] + (["Claves"] if claves else [])
    return TablaPaso(titulo=_TITULO_MATCH, columnas=cols, filas=filas)


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
    """Pasos 5, 5b, 6, 7, 8, 9 para una iteracion IM de falta de calado."""
    pasos: list[PasoResultado] = []
    modo_excel = (modo_fallo_excel or modo_fallo).strip()
    n_txt = n_relacion if n_relacion is not None else ""

    pasos.append(PasoResultado(
        numero=5,
        nombre=f"Identificar IM (iteracion {numero_iteracion}) desde ListRelacion",
        excel=_EXCEL_LIST_REL,
        procedimiento=(
            "1. Abro Excel: Relacion umbrales | hoja ListRelacion impactos-indicador\n"
            f"2. Localizo la fila IM={numero_iteracion} del activo [{activo_raw}]\n"
            "3. Extraigo: modo, variable, tipo impacto, N relacion"
        ),
        tablas=[
            TablaPaso(
                titulo=_TITULO_ENTRADA,
                columnas=["IM", "Activo", "Modelo"],
                filas=[{
                    "IM": numero_iteracion,
                    "Activo": activo_raw,
                    "Modelo": nombre_modelo,
                }],
            ),
            _tabla_match(
                "Leer fila IM en ListRelacion",
                f"Activo={activo_raw} | Tipo impacto={tipo_impacto}",
            ),
            TablaPaso(
                titulo=_TITULO_SALIDA,
                columnas=[
                    "Modelo",
                    "Nº relacion",
                    "Modo de fallo / Modo de parada",
                    "Variable climatica",
                    "Tipo de impacto",
                ],
                filas=[{
                    "Modelo": nombre_modelo,
                    "Nº relacion": n_txt,
                    "Modo de fallo / Modo de parada": modo_fallo,
                    "Variable climatica": variable,
                    "Tipo de impacto": tipo_impacto,
                }],
            ),
        ],
    ))

    filas_5b: list[dict[str, Any]] = [
        {"Campo": "Origen de la regla", "Valor": _etiqueta_origen_regla(origen_regla)},
        {"Campo": "Percentil", "Valor": percentil.upper()},
        {"Campo": "Seleccion indicador", "Valor": "Predefinido"},
        {"Campo": "No indicadores", "Valor": num_indicadores},
    ]
    if fila_excel is not None:
        filas_5b.append({"Campo": "Fila Excel", "Valor": fila_excel})

    filas_ind_rel: list[dict[str, Any]] = []
    for i, ind in enumerate(indicadores[:num_indicadores], start=1):
        filas_ind_rel.append({
            "Nº": i,
            "Pestana": ind.pestaña,
            "Indicador climatico": ind.indicador,
            "Etiqueta": ind.etiqueta or ind.indicador,
        })

    pasos.append(PasoResultado(
        numero=5,
        nombre="5b. Extraer percentil e indicadores (NM, h0, h sed) de la regla",
        excel=_EXCEL_REL_MODELOS,
        procedimiento=(
            f"1. Abro Excel: {_EXCEL_REL_MODELOS}\n"
            "2. Match: Modelo + Activo + Modo + Variable + Tipo impacto\n"
            "3. Extraigo: percentil + 3 indicadores (NM, h0, h sed)"
        ),
        tablas=[
            TablaPaso(
                titulo=_TITULO_ENTRADA,
                columnas=[
                    "Modelo",
                    "Activo fisico u Operacional",
                    "Modo de fallo / Modo de parada",
                    "Variable",
                    "Tipo de impacto",
                ],
                filas=[{
                    "Modelo": nombre_modelo,
                    "Activo fisico u Operacional": activo_raw,
                    "Modo de fallo / Modo de parada": modo_excel,
                    "Variable": variable,
                    "Tipo de impacto": tipo_impacto,
                }],
            ),
            _tabla_match(
                "Match fila de regla",
                "Modelo+Activo+Modo+Variable+Tipo impacto",
            ),
            TablaPaso(
                titulo=_TITULO_SALIDA + " — regla",
                columnas=["Campo", "Valor"],
                filas=filas_5b,
            ),
            TablaPaso(
                titulo=_TITULO_SALIDA + " — indicadores",
                columnas=["Nº", "Pestana", "Indicador climatico", "Etiqueta"],
                filas=filas_ind_rel,
            ),
        ],
    ))

    pasos.append(PasoResultado(
        numero=6,
        nombre="Obtener formulacion y umbral (con Dc) desde Relacion umbrales",
        excel=_EXCEL_UMBRALES,
        procedimiento=(
            f"1. Abro Excel: {_EXCEL_UMBRALES}\n"
            "2. Match: activo / modo / variable / N relacion (+ Tipo UO, Dc)\n"
            "3. Extraigo formulacion y umbral calculado con Dc"
        ),
        tablas=[
            TablaPaso(
                titulo=_TITULO_ENTRADA,
                columnas=[
                    "Nº relacion impactos",
                    "Activo fisico u Operacional",
                    "Modo de fallo / Modo de parada",
                    "Variable",
                    "Tipo de impacto",
                    "Tipo UO",
                    "Dc",
                ],
                filas=[{
                    "Nº relacion impactos": n_txt,
                    "Activo fisico u Operacional": activo_raw,
                    "Modo de fallo / Modo de parada": modo_excel,
                    "Variable": variable,
                    "Tipo de impacto": tipo_impacto,
                    "Tipo UO": tipo_uo,
                    "Dc": calado_buque,
                }],
            ),
            _tabla_match(
                "Buscar umbral / formulacion",
                f"N={n_txt} | Activo={activo_raw} | Modo | Variable | Dc={calado_buque}",
            ),
            TablaPaso(
                titulo=_TITULO_SALIDA,
                columnas=[
                    "Formulacion umbral",
                    "Umbral calculado (m)",
                    "Nota",
                ],
                filas=[{
                    "Formulacion umbral": umbral_txt,
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
        nombre="Extraer valores climaticos por escenario (NM, h0, h sed)",
        excel=_EXCEL_CLIMA,
        procedimiento=(
            f"1. Abro Excel: {_EXCEL_CLIMA}\n"
            "2. Match: nombre indicador + percentil en la pestana correspondiente\n"
            "3. Extraigo valores por escenario (historico y futuros)"
        ),
        tablas=[
            TablaPaso(
                titulo=_TITULO_ENTRADA,
                columnas=["Modelo", "Variable", "Percentil", "Pestana"],
                filas=[{
                    "Modelo": nombre_modelo,
                    "Variable": variable,
                    "Percentil": percentil.upper(),
                    "Pestana": ind_nm.pestaña or "Nivel del mar",
                }],
            ),
            _tabla_match(
                "Buscar filas de indicador por nombre + percentil",
                f"NM={ind_nm.indicador} | h0={ind_h0.indicador} | hsed={ind_hsed.indicador}",
            ),
            TablaPaso(
                titulo=_TITULO_SALIDA + " — indicadores encontrados",
                columnas=["Indicador", "Estado"],
                filas=_filas_indicadores_encontrados(indicadores_clima or []),
            ),
            TablaPaso(
                titulo=_TITULO_SALIDA + " — indicadores usados",
                columnas=["Nº", "Rol", "Pestana", "Indicador climatico"],
                filas=[
                    {
                        "Nº": 1,
                        "Rol": "NM",
                        "Pestana": ind_nm.pestaña,
                        "Indicador climatico": ind_nm.indicador,
                    },
                    {
                        "Nº": 2,
                        "Rol": "h0",
                        "Pestana": ind_h0.pestaña,
                        "Indicador climatico": ind_h0.indicador,
                    },
                    {
                        "Nº": 3,
                        "Rol": "h sedimentacion",
                        "Pestana": ind_hsed.pestaña,
                        "Indicador climatico": ind_hsed.indicador,
                    },
                ],
            ),
            TablaPaso(
                titulo=_TITULO_SALIDA + " — valores por escenario",
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
        if "Interpretación" in row.index:
            interp = row.get("Interpretación")
        else:
            interp = row.get("Interpretacion")
        filas_tabla.append({
            "Escenario": row.get("Escenario"),
            "NM": _celda(row.get("NM")),
            "h sedimentacion": _celda(row.get("h sedimentacion")),
            "h0": _celda(row.get("h0")),
            "h": _celda(row.get("h")),
            "Umbral": _celda(row.get("Umbral")),
            "Interpretacion": interp,
        })

    pasos.append(PasoResultado(
        numero=8,
        nombre="Calcular h = NM - h0 - h sedimentacion y comparar con umbral",
        excel="-",
        procedimiento=(
            "1. CALCULO (sin Excel)\n"
            "2. Accion: h = NM - h0 - h sedimentacion por escenario "
            "(NM = MA + MM + SLR)\n"
            "3. Comparo h con el umbral obtenido en el paso 6"
        ),
        tablas=[
            TablaPaso(
                titulo=_TITULO_ENTRADA,
                columnas=["Formula", "Umbral (m)"],
                filas=[
                    {"Formula": "h = NM - h0 - h sedimentacion", "Umbral (m)": umbral_m},
                    {"Formula": "NM = MA + MM + SLR", "Umbral (m)": ""},
                ],
            ),
            _tabla_match("Calcular h y comparar con umbral"),
            TablaPaso(
                titulo=_TITULO_SALIDA,
                columnas=[
                    "Escenario",
                    "NM",
                    "h sedimentacion",
                    "h0",
                    "h",
                    "Umbral",
                    "Interpretacion",
                ],
                filas=filas_tabla,
            ),
        ],
    ))

    filas_interp: list[dict[str, Any]] = []
    for _, row in tabla_resultado.iterrows():
        esc = str(row.get("Escenario", ""))
        h = row.get("h")
        if "Interpretación" in getattr(row, "index", []):
            interp_raw = row.get("Interpretación")
        else:
            interp_raw = row.get("Interpretacion")
        interp = str(interp_raw if interp_raw is not None else "")
        regla = ""
        if esc not in ("Histórico", "Historico") and h is not None and not pd.isna(h):
            regla = "umbral ≤ h → dragar; umbral > h → no dragar"
        filas_interp.append({
            "Escenario": esc,
            "Umbral (m)": umbral_m,
            "h (m)": _celda(h),
            "Interpretacion": interp,
            "Regla": regla if regla else "-",
        })

    pasos.append(PasoResultado(
        numero=9,
        nombre="Interpretar regla dragar / no dragar",
        excel="-",
        procedimiento=(
            "1. CALCULO (sin Excel)\n"
            "2. Accion: aplicar regla de interpretacion por escenario\n"
            "3. Salida: dragar si umbral ≤ h; no dragar si umbral > h"
        ),
        tablas=[
            TablaPaso(
                titulo=_TITULO_ENTRADA,
                columnas=["Regla"],
                filas=[{"Regla": "umbral ≤ h → dragar; umbral > h → no dragar"}],
            ),
            _tabla_match("Aplicar regla dragar / no dragar"),
            TablaPaso(
                titulo=_TITULO_SALIDA,
                columnas=["Escenario", "Umbral (m)", "h (m)", "Interpretacion", "Regla"],
                filas=filas_interp,
            ),
        ],
    ))
    return pasos


def _numero_paso_fallo(error_code: str) -> int:
    code = (error_code or "").upper()
    if code in {"PROCEDIMIENTO_FLUJO_FALTANTE", "DIAGRAMA_FLUJO_FALTANTE"}:
        return 0
    if code.startswith("UMBRAL_"):
        return 6
    if code == "INDICADORES_MODELO_FALTANTES":
        return 5
    if code.startswith("INDICADOR_") and code.endswith("_FALTANTE"):
        return 7
    return 5


def _indicador_faltante_etiqueta(error_code: str) -> str:
    code = (error_code or "").upper()
    if code == "INDICADOR_NM_FALTANTE":
        return "NM (indicador 1)"
    if code == "INDICADOR_H0_FALTANTE":
        return "h0 (indicador 2)"
    if code == "INDICADOR_HSED_FALTANTE":
        return "h sedimentacion (indicador 3)"
    return "indicador climatico"


def _procedimiento_fixo(error_code: str, motivo: str) -> str:
    code = (error_code or "").upper()
    n = _numero_paso_fallo(code)
    if code in {"PROCEDIMIENTO_FLUJO_FALTANTE", "DIAGRAMA_FLUJO_FALTANTE"}:
        return (
            "FALLO de prerrequisito del procedimiento (diagrama en Flujo de modelos).\n"
            "1. Abro carpeta: Flujo de modelos/\n"
            "2. Compruebo que exista el diagrama del modo "
            "(p.ej. PI FALTA DE CALADO para ELO; no reutilizar OPEX/CAPEX)\n"
            f"3. Motivo: {motivo}"
        )
    if code.startswith("UMBRAL_"):
        return (
            f"FALLO en paso {n} (umbral).\n"
            f"1. Abro Excel: {_EXCEL_UMBRALES}\n"
            "2. Reviso que exista fila para activo/modo/variable/N con formulacion usable\n"
            f"3. Motivo: {motivo}"
        )
    if code == "INDICADORES_MODELO_FALTANTES":
        return (
            f"FALLO en paso {n} / 5b (regla del modelo).\n"
            f"1. Abro Excel: {_EXCEL_REL_MODELOS}\n"
            "2. Match Modelo+Activo+Modo+Variable+Tipo impacto\n"
            "3. Completo los 3 indicadores (NM, h0, h sed) en esa fila\n"
            f"4. Motivo: {motivo}"
        )
    if code.startswith("INDICADOR_") and code.endswith("_FALTANTE"):
        cual = _indicador_faltante_etiqueta(code)
        return (
            f"FALLO en paso {n} (indicadores climaticos).\n"
            f"1. Abro Excel: {_EXCEL_CLIMA}\n"
            f"2. Busco el indicador faltante: {cual}\n"
            "3. Verifico nombre exacto + percentil en la pestana\n"
            f"4. Motivo: {motivo}"
        )
    return (
        f"FALLO en paso {n}.\n"
        f"Motivo: {motivo}\n"
        "Revisar Excel segun el procedimiento del paso afectado."
    )


def construir_pasos_modo_calado_error(
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
    calado_buque: float | None = None,
    error_code: str,
    motivo: str,
    percentil: str = "",
    origen_regla: str = "",
    fila_excel: int | None = None,
    num_indicadores: int = 0,
    indicadores: tuple = (),
    umbral_txt: str = "",
    umbral_m: float | None = None,
) -> list[PasoResultado]:
    """Pasos parciales + diagnostico cuando una iteracion IM falla."""
    pasos: list[PasoResultado] = []
    modo_excel = (modo_fallo_excel or modo_fallo).strip()
    n_txt = n_relacion if n_relacion is not None else ""
    code = (error_code or "").upper()
    paso_fallo = _numero_paso_fallo(code)

    pasos.append(PasoResultado(
        numero=5,
        nombre=f"Identificar IM (iteracion {numero_iteracion}) desde ListRelacion",
        excel=_EXCEL_LIST_REL,
        procedimiento=(
            "1. Abro Excel: Relacion umbrales | hoja ListRelacion impactos-indicador\n"
            f"2. Localizo la fila IM={numero_iteracion} del activo [{activo_raw}]\n"
            "3. Extraigo: modo, variable, tipo impacto, N relacion"
        ),
        tablas=[
            TablaPaso(
                titulo=_TITULO_ENTRADA,
                columnas=["IM", "Activo", "Modelo", "Etiqueta IM"],
                filas=[{
                    "IM": numero_iteracion,
                    "Activo": activo_raw,
                    "Modelo": nombre_modelo,
                    "Etiqueta IM": etiqueta_im,
                }],
            ),
            _tabla_match(
                "Leer fila IM en ListRelacion",
                f"Activo={activo_raw} | Tipo impacto={tipo_impacto}",
            ),
            TablaPaso(
                titulo=_TITULO_SALIDA,
                columnas=[
                    "Modelo",
                    "Nº relacion",
                    "Modo de fallo / Modo de parada",
                    "Variable climatica",
                    "Tipo de impacto",
                    "Tipo UO",
                ],
                filas=[{
                    "Modelo": nombre_modelo,
                    "Nº relacion": n_txt,
                    "Modo de fallo / Modo de parada": modo_fallo,
                    "Variable climatica": variable,
                    "Tipo de impacto": tipo_impacto,
                    "Tipo UO": tipo_uo,
                }],
            ),
        ],
    ))

    filas_5b: list[dict[str, Any]] = []
    if origen_regla:
        filas_5b.append({
            "Campo": "Origen de la regla",
            "Valor": _etiqueta_origen_regla(origen_regla),
        })
    if percentil:
        filas_5b.append({"Campo": "Percentil", "Valor": str(percentil).upper()})
    filas_5b.append({"Campo": "No indicadores", "Valor": num_indicadores})
    if fila_excel is not None:
        filas_5b.append({"Campo": "Fila Excel", "Valor": fila_excel})

    filas_ind_rel: list[dict[str, Any]] = []
    inds = tuple(indicadores or ())
    limite = num_indicadores if num_indicadores > 0 else len(inds)
    for i, ind in enumerate(inds[:limite], start=1):
        pest = getattr(ind, "pestaña", "") or getattr(ind, "pestana", "") or ""
        nombre_ind = getattr(ind, "indicador", "") or ""
        etq = getattr(ind, "etiqueta", "") or nombre_ind
        filas_ind_rel.append({
            "Nº": i,
            "Pestana": pest,
            "Indicador climatico": nombre_ind,
            "Etiqueta": etq,
        })

    enfasis_5b = code == "INDICADORES_MODELO_FALTANTES"
    proc_5b = (
        f"1. Abro Excel: {_EXCEL_REL_MODELOS}\n"
        "2. Match: Modelo + Activo + Modo + Variable + Tipo impacto\n"
    )
    if enfasis_5b:
        proc_5b += (
            "3. FALLO: no se obtienen los 3 indicadores requeridos (NM, h0, h sed)\n"
            f"4. Motivo: {motivo}"
        )
        nombre_5b = "5b. FALLO al extraer los 3 indicadores de la regla"
    elif code.startswith("INDICADOR_") and code.endswith("_FALTANTE"):
        proc_5b += (
            "3. Extraigo percentil + indicadores (regla OK hasta aqui)\n"
            "4. El fallo ocurre despues, al buscar valores en Indicadores climaticos"
        )
        nombre_5b = "5b. Regla OK (percentil e indicadores definidos)"
    else:
        proc_5b += "3. Extraigo lo disponible de la regla (contexto parcial)"
        nombre_5b = "5b. Contexto de regla (parcial / previo al fallo)"

    tablas_5b: list[TablaPaso] = [
        TablaPaso(
            titulo=_TITULO_ENTRADA,
            columnas=[
                "Modelo",
                "Activo fisico u Operacional",
                "Modo de fallo / Modo de parada",
                "Variable",
                "Tipo de impacto",
            ],
            filas=[{
                "Modelo": nombre_modelo,
                "Activo fisico u Operacional": activo_raw,
                "Modo de fallo / Modo de parada": modo_excel,
                "Variable": variable,
                "Tipo de impacto": tipo_impacto,
            }],
        ),
        _tabla_match(
            "Match fila de regla" + (" — FALLO" if enfasis_5b else ""),
            "Modelo+Activo+Modo+Variable+Tipo impacto",
        ),
    ]
    if filas_5b:
        tablas_5b.append(TablaPaso(
            titulo=_TITULO_SALIDA + " — regla",
            columnas=["Campo", "Valor"],
            filas=filas_5b,
        ))
    if filas_ind_rel:
        tablas_5b.append(TablaPaso(
            titulo=_TITULO_SALIDA + " — indicadores",
            columnas=["Nº", "Pestana", "Indicador climatico", "Etiqueta"],
            filas=filas_ind_rel,
        ))
    elif enfasis_5b:
        tablas_5b.append(TablaPaso(
            titulo=_TITULO_SALIDA + " — indicadores",
            columnas=["Esperado", "Encontrado"],
            filas=[
                {"Esperado": "NM", "Encontrado": "FALTANTE"},
                {"Esperado": "h0", "Encontrado": "FALTANTE"},
                {"Esperado": "h sedimentacion", "Encontrado": "FALTANTE"},
            ],
        ))

    tablas_5b.append(TablaPaso(
        titulo="FALLO AQUI",
        columnas=["error_code", "motivo"],
        filas=[{"error_code": error_code, "motivo": motivo}],
    ))

    pasos.append(PasoResultado(
        numero=5,
        nombre=nombre_5b,
        excel=_EXCEL_REL_MODELOS,
        procedimiento=proc_5b,
        tablas=tablas_5b,
    ))

    if code.startswith("UMBRAL_"):
        sin_umbral = umbral_m is None and not str(umbral_txt or "").strip()
        pasos.append(PasoResultado(
            numero=6,
            nombre="FALLO al obtener formulacion/umbral desde Relacion umbrales",
            excel=_EXCEL_UMBRALES,
            procedimiento=(
                f"1. Abro Excel: {_EXCEL_UMBRALES}\n"
                "2. Match: activo / modo / variable / N relacion\n"
                f"3. FALLO: {motivo}"
                + ("" if not sin_umbral else " (sin umbral usable)")
            ),
            tablas=[
                TablaPaso(
                    titulo=_TITULO_ENTRADA,
                    columnas=[
                        "Nº relacion impactos",
                        "Activo fisico u Operacional",
                        "Modo de fallo / Modo de parada",
                        "Variable",
                        "Tipo de impacto",
                        "Tipo UO",
                        "Dc",
                    ],
                    filas=[{
                        "Nº relacion impactos": n_txt,
                        "Activo fisico u Operacional": activo_raw,
                        "Modo de fallo / Modo de parada": modo_excel,
                        "Variable": variable,
                        "Tipo de impacto": tipo_impacto,
                        "Tipo UO": tipo_uo,
                        "Dc": calado_buque if calado_buque is not None else "",
                    }],
                ),
                _tabla_match(
                    "Buscar umbral / formulacion — FALLO",
                    f"N={n_txt} | Activo={activo_raw} | Modo | Variable",
                ),
                TablaPaso(
                    titulo="FALLO AQUI",
                    columnas=["error_code", "motivo", "Formulacion", "Umbral (m)"],
                    filas=[{
                        "error_code": error_code,
                        "motivo": motivo,
                        "Formulacion": umbral_txt or "(no encontrada)",
                        "Umbral (m)": umbral_m if umbral_m is not None else "",
                    }],
                ),
            ],
        ))

    if code.startswith("INDICADOR_") and code.endswith("_FALTANTE"):
        cual = _indicador_faltante_etiqueta(code)
        pasos.append(PasoResultado(
            numero=7,
            nombre=f"FALLO al buscar {cual} en Indicadores climaticos",
            excel=_EXCEL_CLIMA,
            procedimiento=(
                f"1. Abro Excel: {_EXCEL_CLIMA}\n"
                f"2. Match: indicador + percentil [{percentil or '?'}] en pestana\n"
                f"3. FALLO: no encuentro {cual}\n"
                f"4. Motivo: {motivo}"
            ),
            tablas=[
                TablaPaso(
                    titulo=_TITULO_ENTRADA,
                    columnas=["Modelo", "Variable", "Percentil", "Indicador buscado"],
                    filas=[{
                        "Modelo": nombre_modelo,
                        "Variable": variable,
                        "Percentil": str(percentil).upper() if percentil else "",
                        "Indicador buscado": cual,
                    }],
                ),
                _tabla_match(
                    f"Buscar {cual} — FALLO",
                    f"nombre indicador + percentil={percentil or '?'}",
                ),
                TablaPaso(
                    titulo="FALLO AQUI",
                    columnas=["error_code", "motivo", "Indicador faltante"],
                    filas=[{
                        "error_code": error_code,
                        "motivo": motivo,
                        "Indicador faltante": cual,
                    }],
                ),
            ],
        ))

    if code == "INDICADORES_MODELO_FALTANTES":
        que_corregir = "Completar 3 indicadores en Relacion_modelos..."
    elif code in {"PROCEDIMIENTO_FLUJO_FALTANTE", "DIAGRAMA_FLUJO_FALTANTE"}:
        que_corregir = "Anadir el diagrama del modo en Flujo de modelos/"
    elif code.startswith("UMBRAL_"):
        que_corregir = "Completar/arreglar umbral en Relacion umbrales"
    elif code.startswith("INDICADOR_"):
        que_corregir = "Anadir/renombrar indicador en Indicadores climaticos"
    else:
        que_corregir = "Revisar Excel del paso indicado"

    if paso_fallo == 0:
        excel_fallo = "Flujo de modelos/"
    elif paso_fallo == 6:
        excel_fallo = _EXCEL_UMBRALES
    elif paso_fallo == 7:
        excel_fallo = _EXCEL_CLIMA
    else:
        excel_fallo = _EXCEL_REL_MODELOS

    pasos.append(PasoResultado(
        numero=paso_fallo,
        nombre="FALLO EN ESTE PASO",
        excel=excel_fallo,
        procedimiento=_procedimiento_fixo(code, motivo),
        tablas=[TablaPaso(
            titulo="FALLO AQUI",
            columnas=["Paso", "error_code", "motivo", "Que corregir"],
            filas=[{
                "Paso": paso_fallo,
                "error_code": error_code,
                "motivo": motivo,
                "Que corregir": que_corregir,
            }],
        )],
    ))
    return pasos
