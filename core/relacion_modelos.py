"""Reglas de percentil e indicador por modelo, activo, modo de fallo y variable.

Prioridad (paso 5b del diagrama):
1. Si hay fila explícita en ``Relacion_modelos_activos_e_indicadores.xlsx`` → usar esa regla.
2. Si no → seguir el diagrama (umbral + filtros del paso 6–7).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from core.config_indicadores import MODO_PREDEFINIDO, MODO_POR_UMBRAL, ReglaIndicador
from core.config_percentiles import normalizar_percentil
from core.data_loader import _normalizar
from core.modelos.impacto.pi_agitacion.utilidades import match_activo, match_texto

PERCENTIL_DIAGRAMA = "P99"
ORIGEN_EXCEL = "excel"
ORIGEN_DIAGRAMA = "diagrama"


@dataclass(frozen=True)
class IndicadorRelacion:
    """Triplete pestaña / indicador / etiqueta del Excel de relación."""

    pestaña: str
    indicador: str
    etiqueta: str


@dataclass(frozen=True)
class ReglaModeloActivo:
    """Percentil e indicador resueltos para una iteración IM."""

    percentil: str
    regla_indicador: ReglaIndicador
    origen: str = ORIGEN_DIAGRAMA
    fila: int | None = None
    num_indicadores: int = 1
    indicadores: tuple[IndicadorRelacion, ...] = field(default_factory=tuple)

    @property
    def desde_excel(self) -> bool:
        return self.origen == ORIGEN_EXCEL


def _es_comodin(valor: object) -> bool:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return True
    texto = str(valor).strip()
    if not texto or texto.lower() in ("*", "todos", "all", "cualquiera", "-", "nan"):
        return True
    return False


def _celda_coincide(celda: object, valor: str | None, *, activo: bool = False) -> bool:
    if not valor:
        return _es_comodin(celda)
    if _es_comodin(celda):
        return True
    if activo:
        return match_activo(celda, valor)
    return match_texto(celda, valor)


def _modelo_aplica(celda_modelo: object, modelo_id: str, variable: str) -> bool:
    if _es_comodin(celda_modelo):
        return True
    texto = _normalizar(celda_modelo)
    mid = _normalizar(modelo_id)
    var = _normalizar(variable)
    if mid in texto or texto in mid:
        return True
    if "superacion" in texto and "umbral" in texto:
        return True
    if "opex" in texto and "calado" in texto:
        return mid == "pi_calado_els" and var in ("nivel del mar", "calado")
    if "capex" in texto and "calado" in texto:
        return mid == "pi_calado_elu" and var in ("nivel del mar", "calado")
    if "calado" in texto and (
        "perdida" in texto
        or "pi_calado_elo" in mid
        or ("pi" in texto and "opex" not in texto and "capex" not in texto)
    ):
        return mid == "pi_calado_elo" and var in ("nivel del mar", "calado")
    if "calado" in texto and ("pi_calado" in mid or "calado" in mid):
        return True
    if "viento" in texto:
        return var == "viento"
    if "corriente" in texto:
        return var == "corriente"
    if "visibilidad" in texto:
        return var == "visibilidad"
    if "agitacion" in texto or "oleaje" in texto:
        return var == "oleaje"
    if "francobordo" in texto:
        return var in ("nivel del mar", "calado") or "francobordo" in mid
    if "inundacion" in texto:
        return "inundacion" in var or "agitacion" in mid or "superacion" in texto
    if "precipitacion" in texto or var == "precipitacion":
        return mid == "pi_precipitacion" or var == "precipitacion"
    return match_texto(celda_modelo, modelo_id)


def _parsear_modo_seleccion(valor: object, indicador: object) -> str:
    if not _es_comodin(indicador) and str(indicador).strip():
        return MODO_PREDEFINIDO
    if _es_comodin(valor):
        return MODO_POR_UMBRAL
    n = _normalizar(valor)
    n_compact = n.replace(" ", "").replace("_", "").replace("-", "")
    # Soporte explicito para desplegable en Excel:
    # - "predefinido" / "Predefinido" / "pre-definido"
    # - "no predefinido"
    if (
        "nopredefinido" in n_compact
        or n_compact.startswith("nopredef")
        or "no predefinido" in n
    ):
        return MODO_POR_UMBRAL
    if any(
        x in n or x in n_compact
        for x in ("predefinido", "predef", "fijo", "nombre", "excel")
    ):
        return MODO_PREDEFINIDO
    if any(x in n or x in n_compact for x in ("umbral", "porumbral")):
        return MODO_POR_UMBRAL
    return MODO_POR_UMBRAL


def _columnas_tripletas_indicador(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Detecta columnas Pestaña / Indicador / Etiqueta (incl. sufijos .1, .2)."""
    triplets: list[tuple[str, str, str]] = []
    vistos: set[str] = set()

    for col in df.columns:
        n = _normalizar(col)
        if "pestana" not in n and "pesta" not in n:
            continue
        sufijo = ""
        if "." in col:
            sufijo = col.rsplit(".", 1)[-1]
        clave = sufijo or "0"
        if clave in vistos:
            continue
        vistos.add(clave)

        col_pest = col
        col_ind = None
        col_etq = None
        for c in df.columns:
            cn = _normalizar(c)
            if "indicador" in cn and "clim" in cn:
                if sufijo and c.endswith(f".{sufijo}"):
                    col_ind = c
                elif not sufijo and "." not in c:
                    col_ind = c
            elif "etiqueta" in cn:
                if sufijo and c.endswith(f".{sufijo}"):
                    col_etq = c
                elif not sufijo and "." not in c:
                    col_etq = c
        if col_ind and col_etq:
            triplets.append((col_pest, col_ind, col_etq))

    return triplets


def mapear_columnas_relacion_modelos(df: pd.DataFrame) -> dict[str, str]:
    """Localiza columnas del Excel por patrones de nombre (acentos/orden flexibles)."""
    cols: dict[str, str] = {}
    for c in df.columns:
        n = _normalizar(c)
        n_compact = n.replace(" ", "")
        if "modelo" in n and "modelo" not in cols:
            cols["modelo"] = c
        elif (
            ("activo" in n and "fisico" in n)
            or n == "activo"
            or n_compact in ("activofisico", "activofisicuoperacional", "activooperacional")
        ):
            cols.setdefault("activo", c)
        elif (
            ("modo" in n and ("fallo" in n or "parada" in n))
            or "modos de fallo" in n
            or n_compact in ("modofallo", "modosdefallo", "mododeparada")
        ):
            cols.setdefault("modo_fallo", c)
        elif n == "variable" or n.startswith("variable"):
            cols.setdefault("variable", c)
        elif (
            "tipo de impacto" in n
            or n_compact == "tipodeimpacto"
            or ("impacto" in n and "indicador" not in n)
            or ("estado" in n and "limite" in n)
        ):
            cols.setdefault("estado_limite", c)
        elif "percentil" in n:
            cols.setdefault("percentil", c)
        elif (
            ("seleccion" in n and "indicador" in n)
            or n_compact in ("seleccionindicador", "modoseleccion", "mododeindicador")
        ):
            cols.setdefault("modo_seleccion", c)
        elif ("no" in n and "indicador" in n) or n_compact in ("noindicadores", "nindicadores"):
            cols.setdefault("no_indicadores", c)
        elif "indicador" in n and "clim" in n and "indicador" not in cols:
            cols["indicador"] = c
        elif n == "indicador" or (
            "indicador" in n and "etiqueta" not in n and "seleccion" not in n
        ):
            cols.setdefault("indicador", c)
        elif "etiqueta" in n and "etiqueta" not in cols:
            cols["etiqueta"] = c
    cols["tripletas"] = _columnas_tripletas_indicador(df)  # type: ignore[assignment]
    return cols


def _parsear_num_indicadores(valor: object) -> int:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return 1
    try:
        n = int(float(str(valor).strip()))
        return max(1, n)
    except (TypeError, ValueError):
        return 1


def _indicadores_desde_fila(
    row: pd.Series,
    cols: dict[str, str],
) -> tuple[int, tuple[IndicadorRelacion, ...]]:
    """Lee indicadores de la fila.

    Recorre todas las tripletas rellenas (no se corta por ``No indicadores`` cacheado
    o por fórmulas de Excel no recalculadas). ``No indicadores`` solo trunca si es
    mayor que 1 y menor que las tripletas halladas.
    """
    col_no = cols.get("no_indicadores")
    num_declarado = _parsear_num_indicadores(row.get(col_no) if col_no else None)

    triplets = cols.get("tripletas") or []
    indicadores: list[IndicadorRelacion] = []
    for col_pest, col_ind, col_etq in triplets:
        pest = row.get(col_pest)
        ind = row.get(col_ind)
        etq = row.get(col_etq)
        if _es_comodin(pest) and _es_comodin(ind):
            continue
        indicadores.append(
            IndicadorRelacion(
                pestaña="" if _es_comodin(pest) else str(pest).strip(),
                indicador="" if _es_comodin(ind) else str(ind).strip(),
                etiqueta="" if _es_comodin(etq) else str(etq).strip(),
            )
        )

    if not indicadores:
        col_ind = cols.get("indicador")
        col_etq = cols.get("etiqueta")
        indicador_raw = row.get(col_ind) if col_ind else None
        etiqueta_raw = row.get(col_etq) if col_etq else None
        if not _es_comodin(indicador_raw):
            indicadores.append(
                IndicadorRelacion(
                    pestaña="",
                    indicador=str(indicador_raw).strip(),
                    etiqueta="" if _es_comodin(etiqueta_raw) else str(etiqueta_raw).strip(),
                )
            )

    if indicadores and 1 < num_declarado < len(indicadores):
        indicadores = indicadores[:num_declarado]
    num = len(indicadores) if indicadores else num_declarado
    return num, tuple(indicadores)


def _fila_definida_en_excel(
    row: pd.Series,
    cols: dict[str, str],
    *,
    modo_fallo: str,
    variable: str,
) -> bool:
    """True si la fila fija modo de fallo y variable (no comodines)."""
    col_modo = cols.get("modo_fallo")
    col_var = cols.get("variable")
    if not col_modo or not col_var:
        return False
    if _es_comodin(row.get(col_modo)) or _es_comodin(row.get(col_var)):
        return False
    return match_texto(row.get(col_modo), modo_fallo) and match_texto(row.get(col_var), variable)


def _puntuar_fila(
    row: pd.Series,
    cols: dict[str, str],
    *,
    modelo_id: str,
    activo: str,
    modo_fallo: str,
    variable: str,
    estado_limite: str | None,
) -> int:
    if not _fila_definida_en_excel(row, cols, modo_fallo=modo_fallo, variable=variable):
        return -1
    if not _modelo_aplica(row.get(cols.get("modelo", "")), modelo_id, variable):
        return -1
    if cols.get("activo") and not _celda_coincide(row.get(cols["activo"]), activo, activo=True):
        return -1
    if cols.get("estado_limite") and estado_limite:
        if not _celda_coincide(row.get(cols["estado_limite"]), estado_limite):
            return -1

    puntos = 4  # modo + variable explícitos
    if cols.get("activo") and not _es_comodin(row.get(cols["activo"])):
        puntos += 8
    if cols.get("estado_limite") and estado_limite and not _es_comodin(row.get(cols["estado_limite"])):
        puntos += 2
    if cols.get("modelo") and not _es_comodin(row.get(cols["modelo"])):
        puntos += 1
    return puntos


def _regla_desde_fila(row: pd.Series, cols: dict[str, str]) -> ReglaModeloActivo:
    col_pct = cols.get("percentil")
    percentil = normalizar_percentil(row.get(col_pct) if col_pct else None)

    num_ind, indicadores = _indicadores_desde_fila(row, cols)
    primero = indicadores[0] if indicadores else None

    col_modo = cols.get("modo_seleccion")
    modo = _parsear_modo_seleccion(
        row.get(col_modo) if col_modo else None,
        primero.indicador if primero else None,
    )
    indicador = primero.indicador if primero else None
    etiqueta = primero.etiqueta if primero else None

    if modo == MODO_PREDEFINIDO and not indicador:
        modo = MODO_POR_UMBRAL

    return ReglaModeloActivo(
        percentil=percentil,
        regla_indicador=ReglaIndicador(
            modo_seleccion=modo,
            indicador=indicador,
            etiqueta=etiqueta,
        ),
        origen=ORIGEN_EXCEL,
        num_indicadores=num_ind,
        indicadores=indicadores,
    )


def regla_segun_diagrama() -> ReglaModeloActivo:
    """Paso 6–7 del diagrama cuando no hay fila en el Excel de relación."""
    return ReglaModeloActivo(
        percentil=PERCENTIL_DIAGRAMA,
        regla_indicador=ReglaIndicador(modo_seleccion=MODO_POR_UMBRAL),
        origen=ORIGEN_DIAGRAMA,
    )


def resumen_relacion_modelos(
    df: pd.DataFrame | None,
    *,
    ruta: str = "",
) -> dict[str, str]:
    return {
        "ruta": ruta,
        "filas": str(len(df)) if df is not None and not df.empty else "0",
        "origen": "excel" if df is not None and not df.empty else "diagrama",
    }


def diagnosticar_busqueda_regla(
    df: pd.DataFrame | None,
    *,
    modelo_id: str,
    activo: str,
    modo_fallo: str,
    variable: str,
    estado_limite: str | None = None,
) -> str:
    """Explica por qué no hay fila Excel 4 usable (celdas concretas)."""
    if df is None or df.empty:
        return "Excel 4 esta vacio o no se cargo."

    cols = mapear_columnas_relacion_modelos(df)
    faltan = [k for k in ("modo_fallo", "variable") if k not in cols]
    if faltan:
        return (
            "Excel 4 no tiene columnas reconocibles para "
            + ", ".join(faltan)
            + f" (cabeceras: {list(df.columns)[:8]}…)."
        )

    col_act = cols.get("activo")
    col_modo = cols["modo_fallo"]
    col_var = cols["variable"]
    col_modelo = cols.get("modelo")
    col_tipo = cols.get("estado_limite")
    col_sel = cols.get("modo_seleccion")

    candidatos_modo_var: list[int] = []
    candidatos_activo: list[int] = []
    for idx, row in df.iterrows():
        try:
            fila_excel = int(idx) + 2  # type: ignore[arg-type]
        except (TypeError, ValueError):
            fila_excel = -1
        modo_ok = match_texto(row.get(col_modo), modo_fallo)
        var_ok = match_texto(row.get(col_var), variable)
        if modo_ok and var_ok:
            candidatos_modo_var.append(fila_excel)
        act_ok = (not col_act) or match_activo(row.get(col_act), activo)
        if act_ok and (modo_ok or var_ok or "precipitacion" in _normalizar(variable)):
            if act_ok and (modo_ok or var_ok):
                candidatos_activo.append(fila_excel)

        if not (modo_ok and var_ok):
            continue
        if col_act and not match_activo(row.get(col_act), activo):
            continue
        if col_modelo and not _modelo_aplica(row.get(col_modelo), modelo_id, variable):
            return (
                f"Fila {fila_excel}: Modelo={row.get(col_modelo)!r} no aplica a "
                f"{modelo_id!r} / variable {variable!r}."
            )
        if col_tipo and estado_limite and not _celda_coincide(row.get(col_tipo), estado_limite):
            return (
                f"Fila {fila_excel}: Tipo de impacto={row.get(col_tipo)!r} "
                f"no coincide con {estado_limite!r}."
            )
        if _es_comodin(row.get(col_modo)) or _es_comodin(row.get(col_var)):
            return (
                f"Fila {fila_excel}: Modos/Variable son comodin; se exige fila explicita."
            )
        sel = row.get(col_sel) if col_sel else None
        return (
            f"Fila {fila_excel} coincide en Activo/Modo/Variable pero no se acepto "
            f"(Seleccion indicador={sel!r})."
        )

    if candidatos_modo_var:
        return (
            f"Hay fila(s) {candidatos_modo_var} con Modo={modo_fallo!r} y "
            f"Variable={variable!r}, pero Activo no es {activo!r} "
            f"(ni Tipo/Modelo compatibles)."
        )
    if candidatos_activo:
        return (
            f"Hay fila(s) {candidatos_activo[:5]} para activo {activo!r}, pero no con "
            f"Modo={modo_fallo!r} y Variable={variable!r} explicitos."
        )
    return (
        f"No hay fila en Excel 4 con Activo={activo!r}, "
        f"Modos={modo_fallo!r}, Variable={variable!r}"
        + (f", Tipo={estado_limite!r}" if estado_limite else "")
        + "."
    )


def buscar_regla_modelo(
    df: pd.DataFrame | None,
    *,
    modelo_id: str,
    activo: str,
    modo_fallo: str,
    variable: str,
    estado_limite: str | None = None,
) -> ReglaModeloActivo:
    """Busca regla en Excel; si no hay fila definida, devuelve regla del diagrama."""
    if df is None or df.empty:
        return regla_segun_diagrama()

    cols = mapear_columnas_relacion_modelos(df)
    if "variable" not in cols or "modo_fallo" not in cols:
        return regla_segun_diagrama()

    mejor_idx = None
    mejor_puntos = -1

    for idx, row in df.iterrows():
        puntos = _puntuar_fila(
            row,
            cols,
            modelo_id=modelo_id,
            activo=activo,
            modo_fallo=modo_fallo,
            variable=variable,
            estado_limite=estado_limite,
        )
        if puntos > mejor_puntos:
            mejor_puntos = puntos
            mejor_idx = idx

    if mejor_idx is None or mejor_puntos < 0:
        return regla_segun_diagrama()

    regla = _regla_desde_fila(df.loc[mejor_idx], cols)
    fila_excel = None
    try:
        fila_excel = int(mejor_idx) + 2  # type: ignore[arg-type]
    except (TypeError, ValueError):
        fila_excel = None

    return ReglaModeloActivo(
        percentil=regla.percentil,
        regla_indicador=regla.regla_indicador,
        origen=ORIGEN_EXCEL,
        fila=fila_excel,
        num_indicadores=regla.num_indicadores,
        indicadores=regla.indicadores,
    )
