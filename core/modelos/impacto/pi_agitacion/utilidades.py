"""Utilidades internas del modelo PI_AGITACION (no exportar fuera del paquete)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from core.data_loader import _a_numero, _normalizar
from core.modelos.impacto.pi_agitacion.interpretacion import interpretar_cambio
from core.config_indicadores import ReglaIndicador
from core.modelos.impacto.pi_agitacion.schemas import IndicadorEvaluado

_ALIASES_HISTORICO = ("historico", "historic")


@dataclass
class ColumnaEscenario:
    etiqueta: str
    escenario: str
    anio: int
    columna: str = ""
    es_historico: bool = False


def es_historico(escenario: str | None) -> bool:
    if not escenario:
        return False
    return _normalizar(escenario) in _ALIASES_HISTORICO


def normalizar_escenario(escenario: str | None) -> str | None:
    if not escenario:
        return None
    if es_historico(escenario):
        return "Histórico"
    return re.sub(r"\s+", "", str(escenario)).upper()


def nombre_activo_resumen(activo: str) -> str:
    """Nombre del activo tal como figura en Configuración del puerto (sin recortes ni alias)."""
    return str(activo).strip()


# Variantes de nombre del mismo CP en distintos Excel (no mezclar activos distintos).
_ALIASES_ACTIVO_CP: dict[str, str] = {
    "darsenas zona de permanencia": "darsenas zona permanencia",
    "darsenas zona permanencia": "darsenas zona permanencia",
}


def clave_activo_puerto(activo: object) -> str:
    """Clave canónica del activo para cruzar Excel sin confundir CP distintos."""
    n = _normalizar(activo)
    n = re.sub(r"[()/\\-]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return _ALIASES_ACTIVO_CP.get(n, n)


def match_activo(a: object, b: object) -> bool:
    """True si dos activos son el mismo CP (coincidencia exacta o alias conocido)."""
    if a is None or b is None:
        return False
    na, nb = _normalizar(a), _normalizar(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    return clave_activo_puerto(a) == clave_activo_puerto(b)


def columna_por_patron(columnas: list[str], *patrones: str) -> str | None:
    norm = {_normalizar(c): c for c in columnas}
    for patron in patrones:
        p = _normalizar(patron)
        for n, original in norm.items():
            if p == n or p in n:
                return original
    return None


def match_texto(a: object, b: object) -> bool:
    na, nb = _normalizar(a), _normalizar(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def fila_configuracion(
    config: pd.DataFrame | None,
    *,
    tipo_uo: str | None = None,
    activo: str | None = None,
) -> pd.Series | None:
    if config is None or config.empty:
        return None
    cols = list(config.columns)
    col_tipo = columna_por_patron(cols, "tipo de uo", "tipo")
    col_activo = columna_por_patron(
        cols, "activo fisico u operacional", "activo", "activo fisico"
    )
    for _, row in config.iterrows():
        if col_tipo and tipo_uo and not match_texto(row.get(col_tipo), tipo_uo):
            continue
        if activo and col_activo:
            celda = str(row.get(col_activo, "")).strip()
            if not match_activo(celda, activo):
                continue
        return row
    return config.iloc[0] if not config.empty else None


def impactos_por_activo(df_rel: pd.DataFrame, activo: str) -> pd.DataFrame:
    col = "Activo físico u Operacional"
    if col not in df_rel.columns:
        return df_rel.iloc[0:0]
    mask = df_rel[col].map(lambda x: match_activo(x, activo))
    return df_rel[mask].copy()


def fila_relacion(
    df_rel: pd.DataFrame,
    *,
    activo: str,
    modo_fallo: str,
    variable: str,
) -> pd.Series | None:
    sub = impactos_por_activo(df_rel, activo)
    for _, row in sub.iterrows():
        if match_texto(row.get("Modos de fallo / Modos de parada"), modo_fallo):
            if match_texto(row.get("Variable"), variable):
                return row
    return None


def parsear_umbral_m(valor: object) -> float | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)", texto)
    return float(m.group(1)) if m else None


def es_formula_excel(valor: object) -> bool:
    return isinstance(valor, str) and valor.strip().startswith("=")


def columna_umbral_general(columnas: list[str]) -> str | None:
    """Columna «Umbral General» con o sin unidad: «Umbral General (m)», etc."""
    for col in columnas:
        if "umbral general" in _normalizar(col):
            return col
    return None


def columna_tipo_uo(columnas: list[str], tipo_uo: str) -> str | None:
    """Columna de umbral específica del Tipo de UO (p. ej. «Graneles Líquidos»)."""
    if not tipo_uo:
        return None
    tuo_n = _normalizar(tipo_uo)
    for col in columnas:
        if _normalizar(col) == tuo_n:
            return col
    for col in columnas:
        col_n = _normalizar(col)
        if tuo_n in col_n or col_n in tuo_n:
            return col
    return None


def _celda_umbral_tiene_valor(valor: object) -> bool:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return False
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto or texto.lower() in ("nan", "none", "-"):
            return False
    return True


def _fila_coincide_lista_master(
    row: pd.Series,
    *,
    activo: str,
    modo_fallo: str,
    variable: str,
    tipo_impacto: str | None,
    tipo_activo_servicio: str | None,
    columnas: list[str],
) -> bool:
    if not match_activo(row.get("Activo físico u Operacional"), activo):
        return False
    if not match_modo_fallo_superacion(
        row.get("Modos de fallo / Modos de parada"),
        modo_fallo,
        variable,
        tipo_impacto=tipo_impacto,
    ):
        return False
    if not match_texto(row.get("Variable"), variable):
        return False
    if tipo_impacto and "Tipo de impacto" in columnas:
        if not match_texto(row.get("Tipo de impacto"), tipo_impacto):
            return False
    if tipo_activo_servicio and "Tipo activo/servicio" in columnas:
        if not match_texto(row.get("Tipo activo/servicio"), tipo_activo_servicio):
            return False
    return True


def buscar_fila_lista_master(
    lista: pd.DataFrame,
    *,
    n_relacion: int | None = None,
    activo: str,
    modo_fallo: str,
    variable: str,
    tipo_impacto: str | None = None,
    tipo_activo_servicio: str | None = None,
) -> pd.Series | None:
    """Fila en ``ListRelacion impactos-indicador`` que coincide con el IM evaluado."""
    columnas = list(lista.columns)

    if n_relacion is not None and "Nº" in columnas:
        nums = pd.to_numeric(lista["Nº"], errors="coerce")
        candidatos = lista[nums == n_relacion]
        for _, row in candidatos.iterrows():
            if _fila_coincide_lista_master(
                row,
                activo=activo,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=tipo_impacto,
                tipo_activo_servicio=tipo_activo_servicio,
                columnas=columnas,
            ):
                return row

    for _, row in lista.iterrows():
        if _fila_coincide_lista_master(
            row,
            activo=activo,
            modo_fallo=modo_fallo,
            variable=variable,
            tipo_impacto=tipo_impacto,
            tipo_activo_servicio=tipo_activo_servicio,
            columnas=columnas,
        ):
            return row

    if tipo_activo_servicio:
        for _, row in lista.iterrows():
            if _fila_coincide_lista_master(
                row,
                activo=activo,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=tipo_impacto,
                tipo_activo_servicio=None,
                columnas=columnas,
            ):
                return row
    return None


def seleccionar_raw_umbral_fila(
    fila: pd.Series,
    columnas: list[str],
    *,
    tipo_uo: str,
) -> tuple[object | None, str | None]:
    """Umbral específico del Tipo UO; si vacío, «Umbral General»."""
    col_tuo = columna_tipo_uo(columnas, tipo_uo)
    if col_tuo and _celda_umbral_tiene_valor(fila.get(col_tuo)):
        return fila.get(col_tuo), col_tuo
    col_ug = columna_umbral_general(columnas) or "Umbral General"
    if col_ug in columnas:
        return fila.get(col_ug), col_ug
    return None, None


def formato_umbral_desde_um(
    valor: float,
    variable: str,
    um: str | None = None,
) -> str:
    """Texto del umbral usando la columna UM de la hoja maestra."""
    var_n = _normalizar(variable)
    um_n = _normalizar(um or "")

    if um_n == "km" or (var_n == "visibilidad" and um_n != "m"):
        return f"Visibilidad < {valor:g} km"
    if um_n == "m/s" or var_n in ("viento", "corriente"):
        prefijo = "Viento >" if var_n == "viento" else "V >"
        return f"{prefijo} {valor:g} m/s"
    if var_n in ("nivel del mar", "calado"):
        return f"{valor:g} m"
    if um_n == "mm":
        return f"Precipitación > {valor:g} mm"
    if um_n in ("c", "°c", "oc"):
        return f"Temperatura > {valor:g} °C"
    return f"Hs > {valor:g} m"


def resolver_umbral_lista_master(
    lista: pd.DataFrame,
    *,
    n_relacion: int | None,
    tipo_uo: str,
    activo: str,
    modo_fallo: str,
    variable: str,
    tipo_impacto: str | None = None,
    tipo_activo_servicio: str | None = None,
    inputs_formulacion: dict[str, float] | None = None,
) -> tuple[str, float] | None:
    """Resuelve umbral numérico y texto desde la hoja maestra."""
    fila = buscar_fila_lista_master(
        lista,
        n_relacion=n_relacion,
        activo=activo,
        modo_fallo=modo_fallo,
        variable=variable,
        tipo_impacto=tipo_impacto,
        tipo_activo_servicio=tipo_activo_servicio,
    )
    if fila is None:
        return None

    columnas = list(lista.columns)
    raw, _origen = seleccionar_raw_umbral_fila(fila, columnas, tipo_uo=tipo_uo)
    if not _celda_umbral_tiene_valor(raw):
        return None

    um_celda = fila.get("UM")
    um = str(um_celda).strip() if _celda_umbral_tiene_valor(um_celda) else None

    if es_formula_excel(raw):
        return None

    texto_raw = str(raw).strip()
    if es_formulacion_umbral(raw) or _normalizar(variable) in ("nivel del mar", "calado"):
        val = evaluar_umbral_formulacion(raw, inputs_formulacion)
        if val is None:
            return None
        return texto_raw, val

    val = evaluar_umbral_formulacion(raw, inputs_formulacion)
    if val is None:
        return None
    return formato_umbral_desde_um(val, variable, um), val


def _fila_coincide_umbral(
    row: pd.Series,
    *,
    activo: str,
    modo_fallo: str,
    variable: str,
    tipo_impacto: str | None,
    columnas: list[str],
) -> bool:
    return _fila_coincide_lista_master(
        row,
        activo=activo,
        modo_fallo=modo_fallo,
        variable=variable,
        tipo_impacto=tipo_impacto,
        tipo_activo_servicio=None,
        columnas=columnas,
    )


def umbral_desde_lista_master(
    lista: pd.DataFrame | None,
    *,
    n_relacion: int | None = None,
    activo: str | None = None,
    modo_fallo: str | None = None,
    variable: str | None = None,
    tipo_impacto: str | None = None,
    tipo_uo: str = "",
    tipo_activo_servicio: str | None = None,
    inputs_formulacion: dict[str, float] | None = None,
) -> object | None:
    """Valor bruto del umbral en la hoja maestra (compatibilidad)."""
    if lista is None or lista.empty or not activo or not modo_fallo or not variable:
        return None
    res = resolver_umbral_lista_master(
        lista,
        n_relacion=n_relacion,
        tipo_uo=tipo_uo,
        activo=activo,
        modo_fallo=modo_fallo,
        variable=variable,
        tipo_impacto=tipo_impacto,
        tipo_activo_servicio=tipo_activo_servicio,
        inputs_formulacion=inputs_formulacion,
    )
    if res is None:
        return None
    return res[1]


def resolver_valor_umbral_celda(
    raw: object,
    inputs_formulacion: dict[str, float] | None,
    *,
    lista_master: pd.DataFrame | None = None,
    n_relacion: int | None = None,
    activo: str | None = None,
    modo_fallo: str | None = None,
    variable: str | None = None,
    tipo_impacto: str | None = None,
    tipo_uo: str = "",
    tipo_activo_servicio: str | None = None,
) -> float | None:
    """Numérico, formulación (1.5*Dc+0.75) o fórmula Excel → hoja maestra."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)) or es_formula_excel(raw):
        if lista_master is not None and activo and modo_fallo and variable:
            res = resolver_umbral_lista_master(
                lista_master,
                n_relacion=n_relacion,
                tipo_uo=tipo_uo,
                activo=activo,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=tipo_impacto,
                tipo_activo_servicio=tipo_activo_servicio,
                inputs_formulacion=inputs_formulacion,
            )
            return res[1] if res else None
        return None
    return evaluar_umbral_formulacion(raw, inputs_formulacion)


def _columnas_umbral_fila(
    hoja: pd.DataFrame,
    *,
    tipo_uo: str,
) -> list[str]:
    cols: list[str] = []
    col_tuo = columna_tipo_uo(list(hoja.columns), tipo_uo)
    if col_tuo:
        cols.append(col_tuo)
    col_ug = columna_umbral_general(list(hoja.columns))
    if col_ug and col_ug not in cols:
        cols.append(col_ug)
    for nombre in ("Umbral General", "Umbral general"):
        if nombre in hoja.columns and nombre not in cols:
            cols.append(nombre)
    return cols


def _buscar_fila_umbral(
    hoja: pd.DataFrame,
    *,
    n_relacion: int | None,
    activo: str,
    modo_fallo: str,
    variable: str,
    tipo_impacto: str | None,
    tipo_activo_servicio: str | None = None,
) -> pd.Series | None:
    columnas = list(hoja.columns)
    if n_relacion is not None and "Nº" in columnas:
        nums = pd.to_numeric(hoja["Nº"], errors="coerce")
        match = hoja[nums == n_relacion]
        if not match.empty:
            return match.iloc[0]

    for _, row in hoja.iterrows():
        if _fila_coincide_lista_master(
            row,
            activo=activo,
            modo_fallo=modo_fallo,
            variable=variable,
            tipo_impacto=tipo_impacto,
            tipo_activo_servicio=tipo_activo_servicio,
            columnas=columnas,
        ):
            return row
    return None


def _resultado_umbral_fila(
    fila: pd.Series,
    hoja: pd.DataFrame,
    *,
    tipo_uo: str,
    activo: str,
    modo_fallo: str,
    variable: str,
    tipo_impacto: str | None,
    tipo_activo_servicio: str | None,
    n_relacion: int | None,
    inputs_formulacion: dict[str, float] | None,
    lista_master: pd.DataFrame | None,
) -> tuple[str, float | None] | None:
    columnas = list(hoja.columns)
    raw, _origen = seleccionar_raw_umbral_fila(fila, columnas, tipo_uo=tipo_uo)
    um = None
    if lista_master is not None and not lista_master.empty:
        fila_master = buscar_fila_lista_master(
            lista_master,
            n_relacion=n_relacion,
            activo=activo,
            modo_fallo=modo_fallo,
            variable=variable,
            tipo_impacto=tipo_impacto,
            tipo_activo_servicio=tipo_activo_servicio,
        )
        if fila_master is not None:
            um_celda = fila_master.get("UM")
            if _celda_umbral_tiene_valor(um_celda):
                um = str(um_celda).strip()
            if not _celda_umbral_tiene_valor(raw) or es_formula_excel(raw):
                raw_master, _ = seleccionar_raw_umbral_fila(
                    fila_master,
                    list(lista_master.columns),
                    tipo_uo=tipo_uo,
                )
                if _celda_umbral_tiene_valor(raw_master):
                    raw = raw_master

    val = resolver_valor_umbral_celda(
        raw,
        inputs_formulacion,
        lista_master=lista_master,
        n_relacion=n_relacion,
        activo=activo,
        modo_fallo=modo_fallo,
        variable=variable,
        tipo_impacto=tipo_impacto,
        tipo_uo=tipo_uo,
        tipo_activo_servicio=tipo_activo_servicio,
    )
    if val is None:
        return None

    if es_formulacion_umbral(raw) or _normalizar(variable) in ("nivel del mar", "calado"):
        texto = str(raw).strip() if _celda_umbral_tiene_valor(raw) else f"{val:g}"
        return texto, val
    return formato_umbral_desde_um(val, variable, um), val

def evaluar_umbral_formulacion(
    valor: object,
    inputs: dict[str, float] | None = None,
) -> float | None:
    """Evalúa umbral numérico o formulación (p. ej. ``1.5*Dc+0.75``)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    if not texto or texto.lower() in ("nan", "none", "-"):
        return None

    numerico = parsear_umbral_m(texto)
    if numerico is not None and "*" not in texto and "+" not in texto and "dc" not in texto.lower():
        return numerico

    inputs = inputs or {}
    alias = {
        "dc": inputs.get("calado_buque") or inputs.get("Dc") or inputs.get("dc"),
        "hobjetivo": inputs.get("hobjetivo"),
        "hsedimentacion": inputs.get("hsedimentacion"),
    }
    expr = texto.replace(",", ".")
    for nombre, val in alias.items():
        if val is not None:
            expr = re.sub(rf"\b{re.escape(nombre)}\b", str(float(val)), expr, flags=re.IGNORECASE)
    if re.search(r"[A-Za-z]", expr):
        return numerico
    try:
        return float(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError):
        return numerico


def es_formulacion_umbral(valor: object) -> bool:
    """True si el umbral del Excel es una expresión (p. ej. ``1.5*Dc+0.75``)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return False
    if isinstance(valor, (int, float)):
        return False
    texto = str(valor).strip()
    if not texto or texto.lower() in ("nan", "none", "-"):
        return False
    if any(op in texto for op in ("*", "+", "-", "/")) and re.search(
        r"[A-Za-z]", texto
    ):
        return True
    return "dc" in _normalizar(texto)


def nota_umbral_paso6(
    umbral_txt: str,
    umbral_m: float,
    *,
    calado_buque: float | None = None,
) -> str:
    """Texto explicativo del paso 6 según la formulación leída del Excel."""
    texto = str(umbral_txt).strip()
    if es_formulacion_umbral(texto):
        if calado_buque is not None:
            return (
                f"Umbral calculado con la formulación «{texto}» "
                f"y Dc = {calado_buque:g} m → {umbral_m:g} m"
            )
        return f"Umbral calculado con la formulación «{texto}» → {umbral_m:g} m"
    if texto and texto.replace(",", ".") != f"{umbral_m:g}":
        return f"Umbral del Excel: {texto} ({umbral_m:g} m)"
    return f"Umbral numérico del Excel: {umbral_m:g} m"


TIPO_IMPACTO_PI_OPERACIONAL = "elo"


def es_tipo_impacto_pi_operacional(tipo_impacto: object) -> bool:
    """Estado límite operacional (ELO) → cadena PI superación de umbral."""
    return _normalizar(tipo_impacto) == TIPO_IMPACTO_PI_OPERACIONAL


def match_modo_fallo_superacion(
    modo_a: object,
    modo_b: object,
    variable: object,
    *,
    tipo_impacto: object | None = None,
) -> bool:
    """True si dos modos de fallo son equivalentes para PI superación (p. ej. Agitación ↔ Exceso de Oleaje)."""
    if match_texto(modo_a, modo_b):
        return True
    if _normalizar(variable) != "oleaje":
        return False
    if tipo_impacto is not None and not es_tipo_impacto_pi_operacional(tipo_impacto):
        return False
    oleaje_pi = {"agitacion", "exceso de oleaje"}
    return _normalizar(modo_a) in oleaje_pi and _normalizar(modo_b) in oleaje_pi


def es_modo_superacion_umbral(
    modo: object,
    variable: object,
    tipo_impacto: object | None = None,
) -> bool:
    """Modos PI superación de umbral (solo ELO; ELS/ELU reservados a OPEX/CAPEX)."""
    if tipo_impacto is not None and not es_tipo_impacto_pi_operacional(tipo_impacto):
        return False

    modo_n = _normalizar(modo)
    var_n = _normalizar(variable)

    if var_n == "visibilidad":
        return "visibilidad" in modo_n
    if var_n == "oleaje" and "agitacion" in modo_n:
        return tipo_impacto is not None and es_tipo_impacto_pi_operacional(tipo_impacto)
    if var_n == "oleaje" and modo_n == "exceso de oleaje":
        return tipo_impacto is None or es_tipo_impacto_pi_operacional(tipo_impacto)
    if "exceso" not in modo_n:
        return False
    return var_n in ("oleaje", "viento", "corriente")


def variable_superacion_umbral_usa_dias(variable: str) -> bool:
    """Indicadores en días/año (viento, corriente y visibilidad); oleaje en horas/año."""
    return _normalizar(variable) in ("viento", "corriente", "visibilidad")


def modos_superacion_umbral(impactos: pd.DataFrame) -> list[pd.Series]:
    """Filas de relación a iterar (paso 5 / IM) para el activo actual."""
    filas: list[pd.Series] = []
    for _, row in impactos.iterrows():
        if es_modo_superacion_umbral(
            row.get("Modos de fallo / Modos de parada"),
            row.get("Variable"),
            row.get("Tipo de impacto"),
        ):
            filas.append(row)
    return filas


def hoja_umbrales_variable(
    por_hoja: dict[str, pd.DataFrame],
    variable: str,
) -> pd.DataFrame | None:
    var_n = _normalizar(variable)
    if var_n == "viento":
        return next(
            (
                df
                for nombre, df in por_hoja.items()
                if "viento" in _normalizar(nombre)
                and "agit" not in _normalizar(nombre)
            ),
            None,
        )
    if var_n == "oleaje":
        return next(
            (
                df
                for nombre, df in por_hoja.items()
                if "agit" in _normalizar(nombre) and "oleaje" in _normalizar(nombre)
            ),
            None,
        )
    if var_n == "corriente":
        return next(
            (
                df
                for nombre, df in por_hoja.items()
                if "corriente" in _normalizar(nombre)
            ),
            None,
        )
    if var_n == "visibilidad":
        return next(
            (
                df
                for nombre, df in por_hoja.items()
                if "visibilidad" in _normalizar(nombre)
            ),
            None,
        )
    if var_n in ("nivel del mar", "calado"):
        return next(
            (
                df
                for nombre, df in por_hoja.items()
                if "calado" in _normalizar(nombre)
            ),
            None,
        )
    return None


def formato_umbral(m: float, *, variable: str = "Oleaje", um: str | None = None) -> str:
    return formato_umbral_desde_um(m, variable, um)


def umbral_sin_valor(variable: str) -> str:
    var_n = _normalizar(variable)
    if var_n == "viento":
        return "Días ventosos (definición local)"
    if var_n == "corriente":
        return "Días con corriente elevada (definición local)"
    if var_n == "visibilidad":
        return "Días con visibilidad reducida (definición local)"
    return "Sin umbral numérico"


def umbral_por_activo(activo: str, *, variable: str = "Oleaje") -> float | None:
    if _normalizar(variable) != "oleaje":
        return None
    n = _normalizar(activo)
    if any(x in n for x in ("fondeo", "bocana", "canal", "navegacion", "acceso", "espera exterior")):
        return 2.5
    return None


def buscar_umbral_umbrales(
    por_hoja: dict[str, pd.DataFrame],
    *,
    n_relacion: int | None,
    tipo_uo: str,
    activo: str,
    modo_fallo: str,
    variable: str,
    override: float | None = None,
    inputs_formulacion: dict[str, float] | None = None,
    tipo_impacto: str | None = None,
    tipo_activo_servicio: str | None = None,
    lista_master: pd.DataFrame | None = None,
) -> tuple[str, float | None] | None:
    if override is not None:
        return formato_umbral(override, variable=variable), override

    if lista_master is not None and not lista_master.empty:
        resultado = resolver_umbral_lista_master(
            lista_master,
            n_relacion=n_relacion,
            tipo_uo=tipo_uo,
            activo=activo,
            modo_fallo=modo_fallo,
            variable=variable,
            tipo_impacto=tipo_impacto,
            tipo_activo_servicio=tipo_activo_servicio,
            inputs_formulacion=inputs_formulacion,
        )
        if resultado is not None:
            return resultado

    hoja = hoja_umbrales_variable(por_hoja, variable)
    if hoja is not None and not hoja.empty:
        fila = _buscar_fila_umbral(
            hoja,
            n_relacion=n_relacion,
            activo=activo,
            modo_fallo=modo_fallo,
            variable=variable,
            tipo_impacto=tipo_impacto,
            tipo_activo_servicio=tipo_activo_servicio,
        )
        if fila is not None:
            resultado = _resultado_umbral_fila(
                fila,
                hoja,
                tipo_uo=tipo_uo,
                activo=activo,
                modo_fallo=modo_fallo,
                variable=variable,
                tipo_impacto=tipo_impacto,
                tipo_activo_servicio=tipo_activo_servicio,
                n_relacion=n_relacion,
                inputs_formulacion=inputs_formulacion,
                lista_master=lista_master,
            )
            if resultado is not None:
                return resultado
            if _normalizar(variable) in ("viento", "corriente", "visibilidad"):
                return umbral_sin_valor(variable), None

    if _normalizar(variable) in ("viento", "corriente", "visibilidad"):
        return umbral_sin_valor(variable), None
    return None


def etiqueta_indicador_corta(umbral_m: float | None, *, variable: str = "Oleaje") -> str:
    var_n = _normalizar(variable)
    if var_n == "viento" and umbral_m is None:
        return "Nº días ventosos"
    if var_n == "corriente" and umbral_m is None:
        return "Nº días con corriente elevada"
    if var_n == "corriente":
        return f"Nº días/año con V > {umbral_m:g} m/s"
    if var_n == "visibilidad" and umbral_m is None:
        return "Nº días con visibilidad reducida"
    if var_n == "visibilidad":
        if umbral_m is not None and umbral_m < 100:
            return f"Nº días/año con visibilidad < {umbral_m:g} km"
        if umbral_m is not None and umbral_m >= 1000 and umbral_m % 1000 == 0:
            return f"Nº días/año con visibilidad < {int(umbral_m / 1000)} km"
        return f"Nº días/año con visibilidad < {umbral_m:g} m"
    return f"Nº horas/año con Hs > {umbral_m:g} m"


def es_indicador_horas(texto: str) -> bool:
    n = _normalizar(texto)
    return ("hora" in n or "horas" in n) and ("ano" in n or "año" in texto.lower())


def es_indicador_dias(texto: str) -> bool:
    return "dia" in _normalizar(texto)


def es_indicador_percentil_anual(texto: str) -> bool:
    n = _normalizar(texto)
    return "percentil anual" in n or ("percentil" in n and "anual" in n and "hora" not in n)


def indicador_coincide_umbral(texto: str, umbral_m: float) -> bool:
    n = _normalizar(texto).replace(",", ".")
    umbral_txt = f"{umbral_m:g}"
    return umbral_txt in n or umbral_txt.replace(".", ",") in _normalizar(texto)


def indicador_coincide_nombre(texto: str, nombre: str) -> bool:
    if not nombre:
        return False
    n_texto = _normalizar(texto)
    n_nombre = _normalizar(nombre)
    return n_texto == n_nombre or n_nombre in n_texto or n_texto in n_nombre


def clasificar_indicadores_oleaje(
    df_oleaje: pd.DataFrame,
    umbral_m: float,
    *,
    percentil: str,
) -> tuple[pd.Series | None, list[IndicadorEvaluado]]:
    return clasificar_indicadores_umbral(
        df_oleaje,
        umbral_m,
        percentil=percentil,
        variable="Oleaje",
    )


def clasificar_indicadores_umbral(
    df_clima: pd.DataFrame,
    umbral_m: float | None,
    *,
    percentil: str,
    variable: str,
    regla: ReglaIndicador | None = None,
) -> tuple[pd.Series | None, list[IndicadorEvaluado]]:
    if df_clima.empty or "Indicador" not in df_clima.columns:
        return None, []

    regla = regla or ReglaIndicador()

    if regla.usa_predefinido:
        return _clasificar_indicadores_predefinido(
            df_clima,
            percentil=percentil,
            nombre_indicador=regla.indicador or "",
            etiqueta=regla.etiqueta_mostrar(),
        )

    if umbral_m is None:
        return None, []

    sub = df_clima.copy()
    if "Percentil" in sub.columns and percentil:
        mask_pct = sub["Percentil"].astype(str).str.strip().str.upper() == percentil.upper()
        if mask_pct.any():
            sub = sub[mask_pct]

    estados: list[IndicadorEvaluado] = []
    candidato: pd.Series | None = None
    usa_dias = variable_superacion_umbral_usa_dias(variable)
    etiqueta_corta = etiqueta_indicador_corta(umbral_m, variable=variable)

    for _, row in sub.iterrows():
        ind = str(row.get("Indicador", "")).strip()
        if not ind or ind.lower() == "nan":
            continue
        if not indicador_coincide_umbral(ind, umbral_m):
            continue

        if usa_dias and es_indicador_dias(ind):
            estados.append(IndicadorEvaluado(nombre=etiqueta_corta, seleccionado=False))
            if candidato is None:
                candidato = row
        elif not usa_dias and es_indicador_dias(ind):
            estados.append(IndicadorEvaluado(
                nombre=f"Nº días/año con Hs > {umbral_m:g} m",
                seleccionado=False,
                descartado=True,
            ))
        elif es_indicador_percentil_anual(ind):
            estados.append(IndicadorEvaluado(
                nombre="Percentil anual Hs", seleccionado=False, descartado=True
            ))
        elif not usa_dias and es_indicador_horas(ind):
            estados.append(IndicadorEvaluado(nombre=etiqueta_corta, seleccionado=False))
            if candidato is None:
                candidato = row
        else:
            estados.append(IndicadorEvaluado(
                nombre=ind[:80], seleccionado=False, descartado=True
            ))

    if candidato is not None:
        for e in estados:
            if e.nombre == etiqueta_corta:
                e.seleccionado = True
                e.descartado = False

    if usa_dias:
        etiqueta_dias = etiqueta_corta
    else:
        etiqueta_dias = f"Nº días/año con Hs > {umbral_m:g} m"
    if not any(e.nombre == etiqueta_dias for e in estados):
        estados.append(IndicadorEvaluado(nombre=etiqueta_dias, seleccionado=False, descartado=True))
    if not usa_dias and not any(e.nombre == "Percentil anual Hs" for e in estados):
        estados.append(IndicadorEvaluado(nombre="Percentil anual Hs", seleccionado=False, descartado=True))

    if not any(e.seleccionado for e in estados) and candidato is None:
        for _, row in sub.iterrows():
            ind = str(row.get("Indicador", "")).strip()
            if not indicador_coincide_umbral(ind, umbral_m):
                continue
            if usa_dias and es_indicador_dias(ind):
                candidato = row
                estados.append(IndicadorEvaluado(nombre=etiqueta_corta, seleccionado=True))
                break
            if not usa_dias and es_indicador_horas(ind):
                candidato = row
                estados.append(IndicadorEvaluado(nombre=etiqueta_corta, seleccionado=True))
                break

    return candidato, estados


def _clasificar_indicadores_predefinido(
    df_clima: pd.DataFrame,
    *,
    percentil: str,
    nombre_indicador: str,
    etiqueta: str,
) -> tuple[pd.Series | None, list[IndicadorEvaluado]]:
    """Paso 7 con indicador fijo (p. ej. ELO + Viento)."""
    sub = df_clima.copy()
    if "Percentil" in sub.columns and percentil:
        mask_pct = sub["Percentil"].astype(str).str.strip().str.upper() == percentil.upper()
        if mask_pct.any():
            sub = sub[mask_pct]

    candidato: pd.Series | None = None
    estados: list[IndicadorEvaluado] = []

    for _, row in sub.iterrows():
        ind = str(row.get("Indicador", "")).strip()
        if not ind or ind.lower() == "nan":
            continue
        if indicador_coincide_nombre(ind, nombre_indicador):
            if candidato is None:
                candidato = row
        else:
            estados.append(IndicadorEvaluado(nombre=ind[:80], seleccionado=False, descartado=True))

    if candidato is not None:
        estados.insert(0, IndicadorEvaluado(nombre=etiqueta, seleccionado=True))
    else:
        estados.insert(0, IndicadorEvaluado(nombre=etiqueta, seleccionado=False, descartado=True))

    return candidato, estados


def _clasificar_indicadores_viento(
    df_viento: pd.DataFrame,
    *,
    percentil: str,
) -> tuple[pd.Series | None, list[IndicadorEvaluado]]:
    return _clasificar_indicadores_predefinido(
        df_viento,
        percentil=percentil,
        nombre_indicador="Número de días con vientos extremos",
        etiqueta="Nº días con vientos extremos",
    )


def etiqueta_escenario(escenario: str | None, anio: int | None) -> str:
    if es_historico(escenario):
        return "Histórico"
    esc = normalizar_escenario(escenario) or str(escenario)
    return f"{esc} {anio}" if anio else str(esc)


def _inferir_anio_columna(cc: dict) -> int | None:
    anio = cc.get("anio")
    if anio is not None and not (isinstance(anio, float) and pd.isna(anio)):
        return int(anio)
    texto = str(cc.get("columna") or cc.get("texto") or "")
    m = re.search(r"\((\d{4})\)", texto)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{4})\s*-\s*(\d{4})", texto)
    if m:
        return int(m.group(2))
    return None


def columnas_oleaje(
    info_clima: dict,
    baseline_year: int,
    variable: str = "Oleaje",
) -> tuple[ColumnaEscenario | None, list[ColumnaEscenario]]:
    datos = info_clima["por_variable"].get(variable, {})
    cols_clima = datos.get("columnas_clima", [])
    if not cols_clima:
        return None, []

    ref = None
    futuras: list[ColumnaEscenario] = []
    for cc in cols_clima:
        esc = cc.get("escenario")
        anio = _inferir_anio_columna(cc)
        if esc is None or anio is None:
            continue
        etiqueta = cc.get("texto") or cc.get("columna") or f"{esc} ({anio})"
        nombre_col = cc.get("columna") or str(etiqueta)
        col = ColumnaEscenario(
            etiqueta=str(etiqueta),
            escenario=normalizar_escenario(esc) or str(esc),
            anio=int(anio),
            columna=str(nombre_col),
            es_historico=es_historico(esc) and int(anio) == baseline_year,
        )
        if col.es_historico:
            ref = col
        elif not es_historico(esc):
            futuras.append(col)

    futuras.sort(key=lambda c: (c.anio, c.escenario))
    return ref, futuras


def tabla_resultado_indicador(
    fila_ind: pd.Series,
    col_hist: ColumnaEscenario,
    columnas: list[ColumnaEscenario],
    *,
    variable: str = "Oleaje",
) -> pd.DataFrame:
    hist_raw = _a_numero(fila_ind.get(col_hist.columna))
    hist = int(round(hist_raw)) if hist_raw is not None and not pd.isna(hist_raw) else None
    indicador_nombre = str(fila_ind.get("Indicador", "")).strip()
    if not indicador_nombre or indicador_nombre.lower() == "nan":
        indicador_nombre = None

    interp, texto = interpretar_cambio(
        0,
        es_historico=True,
        variable=variable,
        indicador=indicador_nombre,
    )
    filas: list[dict] = [{
        "Escenario": "Histórico",
        "Indicador": hist,
        "Cambio respecto al histórico": 0,
        "Interpretación": interp,
        "Texto auxiliar": texto,
    }]
    for col in columnas:
        val_raw = _a_numero(fila_ind.get(col.columna))
        if val_raw is not None and not pd.isna(val_raw):
            val = int(round(val_raw))
            cambio = (val - hist) if hist is not None else None
        else:
            val = None
            cambio = None
        interp, texto = interpretar_cambio(
            cambio,
            es_historico=False,
            variable=variable,
            indicador=indicador_nombre,
        )
        filas.append({
            "Escenario": etiqueta_escenario(col.escenario, col.anio),
            "Indicador": val,
            "Cambio respecto al histórico": cambio,
            "Interpretación": interp,
            "Texto auxiliar": texto,
        })
    return pd.DataFrame(filas)


def percentiles_disponibles(info_clima: dict, variable: str = "Oleaje") -> list[str]:
    from core.config_percentiles import percentil_global

    df = info_clima.get("por_variable", {}).get(variable, {}).get("df", pd.DataFrame())
    fallback = percentil_global()
    if df.empty or "Percentil" not in df.columns:
        return [fallback, "P50"]
    vals = sorted({
        str(v).strip().upper()
        for v in df["Percentil"].dropna()
        if str(v).strip()
    })
    return vals or [fallback]
