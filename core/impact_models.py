"""Modelos de impacto — capa de compatibilidad.

La implementación vive en ``core/modelos/impacto/pi_agitacion/``.
Este módulo mantiene la API anterior para no romper imports existentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.modelos.impacto.pi_agitacion import (
    ParametrosEntrada,
    ResultadoPIAgitacion,
    SintesisCambios,
    calcular,
)
from core.modelos.impacto.pi_calado import ResultadoPICalado
from core.modelos.impacto.pi_agitacion.schemas import (
    BASELINE_YEAR,
    MODO_FALLO_DEFAULT,
    VARIABLE_DEFAULT,
)

# Alias históricos
MODO_FALLO_AGITACION = MODO_FALLO_DEFAULT
VARIABLE_OLEAJE = VARIABLE_DEFAULT
ParametrosPIAgitacion = ParametrosEntrada
ParametrosAgitacion = ParametrosEntrada


@dataclass
class IndicadorEstado:
    nombre: str
    seleccionado: bool
    descartado: bool = False


ResumenCambios = SintesisCambios

HORIZONTE_POR_ANIO = {
    2040: "2020-2040",
    2050: "2030-2050",
    2060: "2040-2060",
    2070: "2050-2070",
    2080: "2060-2080",
    2090: "2070-2090",
    2100: "2080-2100",
}


def _parse_etiqueta_escenario(
    escenario: str,
    *,
    baseline_year: int = BASELINE_YEAR,
) -> tuple[str, str, int | None, tuple[int, int]]:
    """Devuelve escenario, horizonte, año representativo y clave de orden."""
    texto = str(escenario).strip()
    if texto.lower() in ("histórico", "historico"):
        return "Histórico", "1995-2014", baseline_year, (0, 0)

    partes = texto.rsplit(" ", 1)
    if len(partes) == 2 and partes[1].isdigit():
        esc = partes[0]
        anio = int(partes[1])
        horizonte = HORIZONTE_POR_ANIO.get(anio, "")
        esc_ord = 0 if "2-4.5" in esc or esc.upper().startswith("SSP2") else 1
        return esc, horizonte, anio, (anio, esc_ord)

    return texto, "", None, (9999, 0)


MODOS_FALLO_PLANTILLA = [
    "PI Exceso de Oleaje",
    "PI Falta de francobordo",
    "PI Exceso de Viento",
    "PI Exceso de Corriente",
    "PI Visibilidad reducida",
    "OPEX Falta de Calado",
    "CAPEX Falta de Calado",
]

PLANTILLA_FILAS_RESUMEN = [
    ("Histórico", "1995-2014", 2005),
    ("SSP2-4.5", "2020-2040", 2040),
    ("SSP2-8.5", "2020-2040", 2040),
    ("SSP2-4.5", "2030-2050", 2050),
    ("SSP2-8.5", "2030-2050", 2050),
    ("SSP2-4.5", "2040-2060", 2060),
    ("SSP2-8.5", "2040-2060", 2060),
    ("SSP2-4.5", "2050-2070", 2070),
    ("SSP2-8.5", "2050-2070", 2070),
    ("SSP2-4.5", "2060-2080", 2080),
    ("SSP2-8.5", "2060-2080", 2080),
    ("SSP2-4.5", "2070-2090", 2090),
    ("SSP2-8.5", "2070-2090", 2090),
    ("SSP2-4.5", "2080-2100", 2100),
    ("SSP2-8.5", "2080-2100", 2100),
]

COL_CAMBIO = "Cambio respecto al historico"
COL_INTERP = "Interpretación"


@dataclass
class ResumenIteracion:
    activo: str
    tipo_uo: str
    modo_fallo: str
    variable_climatica: str
    umbral: str
    indicador_seleccionado: str
    percentil: str
    indicadores: list[IndicadorEstado]
    tabla_resultado: pd.DataFrame
    numero: int = 1
    origen_regla: str = "diagrama"
    log: list[str] = field(default_factory=list)
    impactos_asociados: int = 0
    advertencia_negativos: str | None = None
    resumen_cambios: ResumenCambios | None = None
    resultados_por_pasos: object | None = None


@dataclass
class ResumenActivo:
    """Tabla consolidada del activo (plantilla Excel escenarios × modos de fallo)."""

    activo: str
    filas: list[dict[str, object]] = field(default_factory=list)
    modos_fallo: list[str] = field(default_factory=lambda: list(MODOS_FALLO_PLANTILLA))

    @property
    def tabla_resumen(self) -> pd.DataFrame:
        return tabla_resumen_activo_a_dataframe(self)

    @property
    def columnas(self) -> list[str]:
        return columnas_export_resumen_activo(self.modos_fallo)


@dataclass
class ResultadosImpacto:
    resumen_iteracion: ResumenIteracion | None = None
    resumenes_iteracion: list[ResumenIteracion] = field(default_factory=list)
    resumen_activo: ResumenActivo | None = None
    comentario: str = ""
    modelo: str = "PI_AGITACION"
    variable: str = VARIABLE_OLEAJE
    referencia: str = f"Histórico ({BASELINE_YEAR})"
    incremento: pd.DataFrame = field(default_factory=pd.DataFrame)
    acumulado: pd.DataFrame = field(default_factory=pd.DataFrame)
    equivalente_anual: pd.DataFrame = field(default_factory=pd.DataFrame)
    detalle_modelo: pd.DataFrame = field(default_factory=pd.DataFrame)
    resultado: ResultadoPIAgitacion | None = None


def _escenario_plantilla_a_datos(escenario: str) -> str:
    if escenario == "SSP2-8.5":
        return "SSP5-8.5"
    return escenario


def _es_tabla_calado(tabla: pd.DataFrame) -> bool:
    return "h" in tabla.columns and "NM" in tabla.columns


def _indexar_variaciones_por_modo(
    iteraciones: list[ResumenIteracion],
    *,
    baseline_year: int = BASELINE_YEAR,
) -> dict[tuple[str, str, int], dict[str, object]]:
    """Clave: (modo_fallo, escenario_datos, año) → cambio e interpretación."""
    indice: dict[tuple[str, str, int], dict[str, object]] = {}
    for r in iteraciones:
        if r.tabla_resultado is None or r.tabla_resultado.empty:
            continue
        if _es_tabla_calado(r.tabla_resultado):
            for _, row in r.tabla_resultado.iterrows():
                esc, _horizonte, anio, _orden = _parse_etiqueta_escenario(
                    str(row.get("Escenario", "")),
                    baseline_year=baseline_year,
                )
                if esc == "Histórico" or anio is None:
                    continue
                h_val = row.get("h")
                indice[(r.modo_fallo, esc, anio)] = {
                    COL_CAMBIO: h_val,
                    COL_INTERP: row.get("Interpretación", ""),
                }
            continue
        for _, row in r.tabla_resultado.iterrows():
            esc, _horizonte, anio, _orden = _parse_etiqueta_escenario(
                str(row.get("Escenario", "")),
                baseline_year=baseline_year,
            )
            if esc == "Histórico" or anio is None:
                continue
            indice[(r.modo_fallo, esc, anio)] = {
                COL_CAMBIO: row.get("Cambio respecto al histórico"),
                COL_INTERP: row.get("Interpretación", ""),
            }
    return indice


def _valor_celda_resumen(
    *,
    es_historico: bool,
    cambio: object,
    interpretacion: object,
    es_calado: bool = False,
) -> tuple[str, str]:
    if es_historico:
        return "", ""
    if cambio is None or (isinstance(cambio, float) and pd.isna(cambio)):
        cambio_txt = ""
    elif es_calado and isinstance(cambio, (int, float)):
        cambio_txt = f"{float(cambio):.3f}"
    else:
        cambio_txt = str(int(cambio))
    interp_txt = "" if interpretacion is None else str(interpretacion)
    if interp_txt.lower() in ("referencia",):
        interp_txt = ""
    return cambio_txt, interp_txt


def columnas_export_resumen_activo(
    modos: list[str] | None = None,
) -> list[str]:
    modos = modos or MODOS_FALLO_PLANTILLA
    cols = ["Escenarios", "Horizontes temporales", "Año representativo"]
    for modo in modos:
        cols.append(f"{modo} | {COL_CAMBIO}")
        cols.append(f"{modo} | {COL_INTERP}")
    return cols


def tabla_resumen_activo_a_dataframe(resumen: ResumenActivo) -> pd.DataFrame:
    columnas = columnas_export_resumen_activo(resumen.modos_fallo)
    filas_export: list[dict[str, object]] = []
    for fila in resumen.filas:
        registro = {
            "Escenarios": fila["Escenarios"],
            "Horizontes temporales": fila["Horizontes temporales"],
            "Año representativo": fila["Año representativo"],
        }
        modos = fila.get("modos", {})
        for modo in resumen.modos_fallo:
            datos = modos.get(modo, {})
            registro[f"{modo} | {COL_CAMBIO}"] = datos.get(COL_CAMBIO, "")
            registro[f"{modo} | {COL_INTERP}"] = datos.get(COL_INTERP, "")
        filas_export.append(registro)
    return pd.DataFrame(filas_export, columns=columnas)


def construir_tabla_resumen_activo(
    iteraciones: list[ResumenIteracion],
    *,
    baseline_year: int = BASELINE_YEAR,
) -> ResumenActivo | None:
    """Construye la plantilla fija del resumen del activo."""
    if not iteraciones:
        return None

    indice = _indexar_variaciones_por_modo(iteraciones, baseline_year=baseline_year)
    modos_presentes = {r.modo_fallo for r in iteraciones}
    modos = [m for m in MODOS_FALLO_PLANTILLA if m in modos_presentes]
    extra = sorted(m for m in modos_presentes if m not in MODOS_FALLO_PLANTILLA)
    modos.extend(extra)
    if not modos:
        modos = list(MODOS_FALLO_PLANTILLA)

    filas: list[dict[str, object]] = []
    for esc, horizonte, anio in PLANTILLA_FILAS_RESUMEN:
        es_historico = esc == "Histórico"
        esc_datos = _escenario_plantilla_a_datos(esc)
        modos_valores: dict[str, dict[str, str]] = {}
        for modo in modos:
            if es_historico:
                modos_valores[modo] = {COL_CAMBIO: "", COL_INTERP: ""}
                continue
            datos = indice.get((modo, esc_datos, anio), {})
            es_calado = "Calado" in modo
            cambio_txt, interp_txt = _valor_celda_resumen(
                es_historico=False,
                cambio=datos.get(COL_CAMBIO),
                interpretacion=datos.get(COL_INTERP),
                es_calado=es_calado,
            )
            modos_valores[modo] = {COL_CAMBIO: cambio_txt, COL_INTERP: interp_txt}

        filas.append({
            "Escenarios": esc,
            "Horizontes temporales": horizonte,
            "Año representativo": anio,
            "modos": modos_valores,
        })

    return ResumenActivo(
        activo=iteraciones[0].activo,
        filas=filas,
        modos_fallo=modos,
    )


def html_tabla_resumen_activo(resumen: ResumenActivo) -> str:
    """HTML con cabeceras agrupadas como la plantilla Excel."""
    import html as html_lib

    modos = resumen.modos_fallo

    def esc(val: object) -> str:
        if val is None:
            return ""
        return html_lib.escape(str(val))

    filas_html: list[str] = []
    for fila in resumen.filas:
        celdas = [
            f"<td>{esc(fila['Escenarios'])}</td>",
            f"<td>{esc(fila['Horizontes temporales'])}</td>",
            f"<td>{esc(fila['Año representativo'])}</td>",
        ]
        modos_datos = fila.get("modos", {})
        for modo in modos:
            datos = modos_datos.get(modo, {})
            celdas.append(f"<td>{esc(datos.get(COL_CAMBIO, ''))}</td>")
            celdas.append(f"<td>{esc(datos.get(COL_INTERP, ''))}</td>")
        filas_html.append(f"<tr>{''.join(celdas)}</tr>")

    subcols = "".join(
        f"<th>{COL_CAMBIO}</th><th>{COL_INTERP}</th>"
        for _ in modos
    )
    modos_hdr = "".join(
        f'<th colspan="2">{esc(modo)}</th>'
        for modo in modos
    )

    return f"""
<div class="resumen-activo-tabla">
<style>
.resumen-activo-tabla table {{
  border-collapse: collapse;
  width: 100%;
  font-size: 0.82rem;
}}
.resumen-activo-tabla th,
.resumen-activo-tabla td {{
  border: 1px solid #000;
  padding: 5px 8px;
  text-align: center;
  vertical-align: middle;
}}
.resumen-activo-tabla thead th {{
  background: #ffffff;
  color: #000000;
  font-weight: 600;
}}
</style>
<table>
  <thead>
    <tr>
      <th rowspan="3">Escenarios</th>
      <th rowspan="3">Horizontes temporales</th>
      <th rowspan="3">Año representativo</th>
      <th colspan="{len(modos) * 2}">Modos de fallo / Modos de parada</th>
    </tr>
    <tr>
      {modos_hdr}
    </tr>
    <tr>
      {subcols}
    </tr>
  </thead>
  <tbody>
    {''.join(filas_html)}
  </tbody>
</table>
</div>
""".strip()


def export_resumen_activo_xlsx(resumen: ResumenActivo, *, hoja: str = "Resumen activo") -> bytes:
    """Excel con cabeceras combinadas como la plantilla."""
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, Side

    wb = Workbook()
    ws = wb.active
    ws.title = hoja[:31]

    thin = Side(style="thin", color="000000")
    borde = Border(left=thin, right=thin, top=thin, bottom=thin)
    centro = Alignment(horizontal="center", vertical="center", wrap_text=True)
    negrita = Font(bold=True)

    modos = resumen.modos_fallo
    n_modos = len(modos)

    ws.merge_cells(start_row=1, start_column=1, end_row=3, end_column=1)
    ws.cell(1, 1, "Escenarios")
    ws.merge_cells(start_row=1, start_column=2, end_row=3, end_column=2)
    ws.cell(1, 2, "Horizontes temporales")
    ws.merge_cells(start_row=1, start_column=3, end_row=3, end_column=3)
    ws.cell(1, 3, "Año representativo")
    ws.merge_cells(start_row=1, start_column=4, end_row=1, end_column=3 + n_modos * 2)
    ws.cell(1, 4, "Modos de fallo / Modos de parada")

    col = 4
    for modo in modos:
        ws.merge_cells(start_row=2, start_column=col, end_row=2, end_column=col + 1)
        ws.cell(2, col, modo)
        ws.cell(3, col, COL_CAMBIO)
        ws.cell(3, col + 1, COL_INTERP)
        col += 2

    fila_excel = 4
    for fila in resumen.filas:
        ws.cell(fila_excel, 1, fila["Escenarios"])
        ws.cell(fila_excel, 2, fila["Horizontes temporales"])
        ws.cell(fila_excel, 3, fila["Año representativo"])
        col = 4
        modos_datos = fila.get("modos", {})
        for modo in modos:
            datos = modos_datos.get(modo, {})
            ws.cell(fila_excel, col, datos.get(COL_CAMBIO, ""))
            ws.cell(fila_excel, col + 1, datos.get(COL_INTERP, ""))
            col += 2
        fila_excel += 1

    for row in ws.iter_rows(min_row=1, max_row=fila_excel - 1, min_col=1, max_col=3 + n_modos * 2):
        for cell in row:
            cell.border = borde
            cell.alignment = centro
            if cell.row <= 3:
                cell.font = negrita

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


def resumen_activo_desde_iteraciones(
    iteraciones: list[ResumenIteracion],
) -> ResumenActivo | None:
    return construir_tabla_resumen_activo(iteraciones)


def _iteracion_a_resumen(
    resultado: ResultadoPIAgitacion,
    it: object,
    *,
    activo: str,
    tipo_uo: str,
    impactos_asociados: int,
    resultados_por_pasos: object | None,
) -> ResumenIteracion:
    indicadores = [
        IndicadorEstado(i.nombre, i.seleccionado, i.descartado)
        for i in it.indicadores_evaluados
    ]
    advertencia = it.advertencias[0] if it.advertencias else None
    return ResumenIteracion(
        numero=it.numero,
        activo=activo,
        tipo_uo=tipo_uo,
        modo_fallo=it.modo_fallo,
        variable_climatica=it.variable_climatica,
        umbral=it.umbral,
        indicador_seleccionado=it.indicador_seleccionado,
        percentil=it.percentil,
        origen_regla=it.origen_regla,
        indicadores=indicadores,
        tabla_resultado=it.tabla_resultado,
        impactos_asociados=impactos_asociados,
        advertencia_negativos=advertencia,
        resumen_cambios=it.sintesis_cambios,
        resultados_por_pasos=resultados_por_pasos,
    )


def _adaptar_resultado(resultado: ResultadoPIAgitacion) -> ResultadosImpacto:
    if not resultado.ok:
        return ResultadosImpacto(
            comentario=resultado.error or "Error desconocido.",
            resultado=resultado,
        )

    meta = resultado.metadatos_ejecucion
    activo = str(meta.get("activo", ""))
    tipo_uo = str(meta.get("tipo_uo", ""))
    impactos = int(meta.get("impactos_asociados", 0))
    pasos = resultado.resultados_por_pasos

    resumenes = [
        _iteracion_a_resumen(
            resultado,
            it,
            activo=activo,
            tipo_uo=tipo_uo,
            impactos_asociados=impactos,
            resultados_por_pasos=pasos,
        )
        for it in resultado.iteraciones
    ]
    return ResultadosImpacto(
        resumen_iteracion=resumenes[0] if resumenes else None,
        resumenes_iteracion=resumenes,
        resumen_activo=resumen_activo_desde_iteraciones(resumenes),
        resultado=resultado,
    )


def resumen_para_ui(resultado: ResultadoPIAgitacion) -> ResumenIteracion | None:
    """Adapta la salida del modelo al formato de la UI Streamlit (primera iteración)."""
    return _adaptar_resultado(resultado).resumen_iteracion


def iteraciones_para_ui(resultado: ResultadoPIAgitacion) -> list[ResumenIteracion]:
    """Todas las iteraciones IM del cálculo."""
    return _adaptar_resultado(resultado).resumenes_iteracion


def _iteracion_calado_a_resumen(
    resultado: ResultadoPICalado,
    it: object,
    *,
    activo: str,
    tipo_uo: str,
    impactos_asociados: int,
) -> ResumenIteracion:
    indicadores = [
        IndicadorEstado(i.nombre, i.seleccionado, i.descartado)
        for i in it.indicadores_evaluados
    ]
    return ResumenIteracion(
        numero=it.numero,
        activo=activo,
        tipo_uo=tipo_uo,
        modo_fallo=it.modo_fallo,
        variable_climatica=it.variable_climatica,
        umbral=it.umbral,
        indicador_seleccionado=it.indicador_seleccionado,
        percentil=it.percentil,
        origen_regla=it.origen_regla,
        indicadores=indicadores,
        tabla_resultado=it.tabla_resultado,
        impactos_asociados=impactos_asociados,
        advertencia_negativos=None,
        resumen_cambios=None,
        resultados_por_pasos=None,
    )


def iteraciones_desde_calculo_activo(resultado) -> list[ResumenIteracion]:
    """Todas las iteraciones IM del cálculo unificado por activo."""
    resumenes: list[ResumenIteracion] = []
    if getattr(resultado, "resultado_agitacion", None) and resultado.resultado_agitacion.ok:
        resumenes.extend(iteraciones_para_ui(resultado.resultado_agitacion))

    if getattr(resultado, "resultado_francobordo", None) and resultado.resultado_francobordo.ok:
        resumenes.extend(iteraciones_para_ui(resultado.resultado_francobordo))

    calado_resultados = []
    if getattr(resultado, "resultado_calado_opex", None) and resultado.resultado_calado_opex.ok:
        calado_resultados.append(resultado.resultado_calado_opex)
    elif getattr(resultado, "resultado_calado", None) and resultado.resultado_calado.ok:
        calado_resultados.append(resultado.resultado_calado)
    if getattr(resultado, "resultado_calado_capex", None) and resultado.resultado_calado_capex.ok:
        calado_resultados.append(resultado.resultado_calado_capex)

    offset = len(resumenes)
    for resultado_cal in calado_resultados:
        meta = resultado_cal.metadatos_ejecucion
        activo = str(meta.get("activo", ""))
        tipo_uo = str(meta.get("tipo_uo", ""))
        impactos = int(meta.get("impactos_asociados", 0))
        for idx, it in enumerate(resultado_cal.iteraciones, start=1):
            resumen = _iteracion_calado_a_resumen(
                resultado_cal,
                it,
                activo=activo,
                tipo_uo=tipo_uo,
                impactos_asociados=impactos,
            )
            resumen.numero = offset + idx
            resumenes.append(resumen)
        offset = len(resumenes)
    return resumenes


def resumen_activo_desde_calculo_activo(resultado) -> ResumenActivo | None:
    return construir_tabla_resumen_activo(iteraciones_desde_calculo_activo(resultado))


def resumen_activo_para_ui(resultado: ResultadoPIAgitacion) -> ResumenActivo | None:
    """Resumen consolidado del activo (todos los modos de fallo)."""
    return _adaptar_resultado(resultado).resumen_activo


def pi_agitacion(
    info_clima: dict,
    config_puerto: pd.DataFrame | None = None,
    *,
    params: ParametrosEntrada | None = None,
    df_relacion: pd.DataFrame | None = None,
    por_hoja_umbrales: dict[str, pd.DataFrame] | None = None,
) -> ResultadosImpacto:
    """API legacy — delega en ``core.modelos.impacto.pi_agitacion``."""
    p = params or ParametrosEntrada()
    resultado = calcular(
        datos=info_clima,
        params=p,
        info_clima=info_clima,
        config_puerto=config_puerto,
        df_relacion=df_relacion,
        por_hoja_umbrales=por_hoja_umbrales,
    )
    return _adaptar_resultado(resultado)


def nombres_tipos_uo() -> list[str]:
    from core.data_loader import cargar_tipo_de_uo, _normalizar

    fallback = [
        "Graneles Líquidos",
        "Graneles Sólidos",
        "Carga contenerizada",
        "Ro-ro y resto de mercancía general no contenerizada",
        "Pasajeros",
        "Pesquero",
        "Náutico-deportivo",
        "Puerto-ciudad",
    ]
    try:
        df, _ = cargar_tipo_de_uo()
        col = "Tipo de UO"
        if col not in df.columns:
            col = next((c for c in df.columns if "tipo" in _normalizar(c)), None)
        if col:
            vals = [str(v).strip() for v in df[col].dropna() if str(v).strip()]
            if vals:
                return vals
    except (FileNotFoundError, ValueError, OSError):
        pass
    return fallback


def tabla_tipos_terminal() -> pd.DataFrame:
    tipos = nombres_tipos_uo()
    return pd.DataFrame([
        {"Nº": i, "Tipo de UO": t}
        for i, t in enumerate(tipos, start=1)
    ])
