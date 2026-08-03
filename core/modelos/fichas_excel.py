# -*- coding: utf-8 -*-
"""Fichas documentales desde Fichas/Ficha.xlsx (una hoja = un modelo).

Cada hoja se empareja con una entrada del catalogo por nombre normalizado
(motor_nombre, aliases de flujo, modo de fallo). El contenido tabular
(con merges Excel -> rowspan/colspan HTML) alimenta el boton FICHA; las
imagenes embebidas alimentan el boton i.
"""

from __future__ import annotations

import html as html_lib
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pandas as pd

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
CARPETA_FICHAS = RAIZ_PROYECTO / "Fichas"
ARCHIVO_FICHAS = CARPETA_FICHAS / "Ficha.xlsx"
CARPETA_MEDIA = CARPETA_FICHAS / "_media"

# Notas editoriales / TODO del Excel: no mostrar en la UI.
_PREFIJOS_NOTA_EDITORIAL = (
    "revisar y corregir",
    "especificar:",
)


@dataclass(frozen=True)
class FichaExcelModelo:
    """Contenido de una hoja de Ficha.xlsx asociada a un modelo."""

    hoja: str
    tabla: pd.DataFrame
    html: str
    imagenes: tuple[Path, ...]
    catalogo_id: str | None = None


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")
    return t or "hoja"


def _es_nota_editorial(texto: object) -> bool:
    """True si el texto es una nota de revision/TODO del Excel."""
    t = re.sub(r"\s+", " ", str(texto or "")).strip().lower()
    if not t:
        return False
    return any(t.startswith(p) for p in _PREFIJOS_NOTA_EDITORIAL)


def _aliases_catalogo(entrada) -> set[str]:
    """Nombres normalizados con los que una hoja puede emparejarse."""
    from core.modelos.catalogo_impactos import titulo_modo_impacto
    from core.modelos.flujos import _ALIASES_FLUJO, nombre_esperado_diagrama

    aliases: set[str] = set()
    for bruto in (
        entrada.id,
        entrada.motor_id,
        entrada.motor_nombre,
        entrada.modo_fallo,
        titulo_modo_impacto(entrada),
        f"{entrada.familia} {entrada.modo_fallo}",
        f"{entrada.tipo_impacto} {entrada.modo_fallo}",
        nombre_esperado_diagrama(entrada.diagrama_modelo_id or entrada.motor_id),
    ):
        n = _normalizar(bruto)
        if n:
            aliases.add(n)
    mid = entrada.diagrama_modelo_id or entrada.motor_id
    for a in _ALIASES_FLUJO.get(mid, ()):
        n = _normalizar(a)
        if n:
            aliases.add(n)
    return aliases


def _emparejar_hoja(nombre_hoja: str) -> str | None:
    """Devuelve entrada.id del catalogo o None."""
    from core.modelos.catalogo_impactos import CATALOGO_MODOS_IMPACTO

    clave = _normalizar(nombre_hoja)
    if not clave:
        return None

    mejor_id: str | None = None
    mejor_score = -1
    for entrada in CATALOGO_MODOS_IMPACTO:
        aliases = _aliases_catalogo(entrada)
        if clave in aliases:
            return entrada.id
        for a in aliases:
            if not a:
                continue
            if a in clave or clave in a:
                score = min(len(a), len(clave))
                if score > mejor_score:
                    mejor_score = score
                    mejor_id = entrada.id
    return mejor_id


def _extraer_imagenes_hoja(ws, carpeta: Path) -> tuple[Path, ...]:
    carpeta.mkdir(parents=True, exist_ok=True)
    rutas: list[Path] = []
    imagenes = list(getattr(ws, "_images", []) or [])
    for i, img in enumerate(imagenes):
        try:
            data = img._data()
        except Exception:
            continue
        if not data:
            continue
        if data[:2] == b"\xff\xd8":
            ext = ".jpg"
        elif data[:8].startswith(b"\x89PNG"):
            ext = ".png"
        elif data[:4] == b"GIF8":
            ext = ".gif"
        else:
            ext = ".bin"
        destino = carpeta / f"img_{i}{ext}"
        destino.write_bytes(data)
        rutas.append(destino)
    return tuple(rutas)


def _mapa_merges(ws) -> dict[tuple[int, int], tuple[int, int, int, int]]:
    """(row, col) origen -> (min_r, min_c, rowspan, colspan)."""
    out: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for rango in ws.merged_cells.ranges:
        min_r, min_c, max_r, max_c = rango.min_row, rango.min_col, rango.max_row, rango.max_col
        out[(min_r, min_c)] = (min_r, min_c, max_r - min_r + 1, max_c - min_c + 1)
    return out


def _celdas_cubiertas(ws) -> set[tuple[int, int]]:
    """Celdas que no son el origen de un merge (no deben renderizarse)."""
    cubiertas: set[tuple[int, int]] = set()
    for rango in ws.merged_cells.ranges:
        for r in range(rango.min_row, rango.max_row + 1):
            for c in range(rango.min_col, rango.max_col + 1):
                if r == rango.min_row and c == rango.min_col:
                    continue
                cubiertas.add((r, c))
    return cubiertas


def _texto_celda(valor: object) -> str:
    if valor is None:
        return ""
    return re.sub(r"[\u200b\u200c\u200d\ufeff]", "", str(valor)).strip()


def _fila_es_solo_editorial(ws, row: int, max_col: int) -> bool:
    """True si la fila solo contiene notas editoriales (o vacio)."""
    textos: list[str] = []
    for c in range(1, max_col + 1):
        t = _texto_celda(ws.cell(row, c).value)
        if t:
            textos.append(t)
    if not textos:
        return True
    return all(_es_nota_editorial(t) for t in textos)


def _limites_hoja(ws) -> tuple[int, int, int, int]:
    """min_row, max_row, min_col, max_col con contenido (tras filtrar notas)."""
    if ws.max_row is None or ws.max_column is None:
        return 1, 0, 1, 0
    max_r = int(ws.max_row)
    max_c = int(ws.max_column)
    filas_utiles: list[int] = []
    cols_utiles: set[int] = set()
    for r in range(1, max_r + 1):
        if _fila_es_solo_editorial(ws, r, max_c):
            continue
        tiene = False
        for c in range(1, max_c + 1):
            t = _texto_celda(ws.cell(r, c).value)
            if t and not _es_nota_editorial(t):
                tiene = True
                cols_utiles.add(c)
        if tiene:
            filas_utiles.append(r)
    if not filas_utiles:
        return 1, 0, 1, 0
    # Incluir columnas de merges que atraviesen filas utiles.
    for rango in ws.merged_cells.ranges:
        if rango.max_row < filas_utiles[0] or rango.min_row > filas_utiles[-1]:
            continue
        for c in range(rango.min_col, rango.max_col + 1):
            cols_utiles.add(c)
    return filas_utiles[0], filas_utiles[-1], min(cols_utiles), max(cols_utiles)


def _html_desde_hoja(ws) -> str:
    """Tabla HTML con rowspan/colspan segun merges de Excel."""
    min_r, max_r, min_c, max_c = _limites_hoja(ws)
    if max_r < min_r or max_c < min_c:
        return ""

    merges = _mapa_merges(ws)
    cubiertas = _celdas_cubiertas(ws)
    filas_omitir = {
        r
        for r in range(1, int(ws.max_row or 0) + 1)
        if _fila_es_solo_editorial(ws, r, int(ws.max_column or 0))
    }

    filas_html: list[str] = []
    for r in range(min_r, max_r + 1):
        if r in filas_omitir:
            continue
        celdas: list[str] = []
        for c in range(min_c, max_c + 1):
            if (r, c) in cubiertas:
                continue
            texto = _texto_celda(ws.cell(r, c).value)
            if _es_nota_editorial(texto):
                texto = ""
            attrs = ""
            info = merges.get((r, c))
            if info is not None:
                _mr, _mc, rowspan, colspan = info
                # Acortar rowspan si atraviesa filas omitidas.
                fin = _mr + rowspan - 1
                omitidas = sum(1 for rr in range(_mr, fin + 1) if rr in filas_omitir)
                rowspan_eff = max(1, rowspan - omitidas)
                if rowspan_eff > 1:
                    attrs += f' rowspan="{rowspan_eff}"'
                if colspan > 1:
                    attrs += f' colspan="{colspan}"'
            esc = html_lib.escape(texto).replace("\n", "<br/>")
            celdas.append(f"<td{attrs}>{esc}</td>")
        if celdas:
            filas_html.append(f"<tr>{''.join(celdas)}</tr>")

    if not filas_html:
        return ""

    return f"""
<div class="pde-ficha-excel">
<style>
.pde-ficha-excel table {{
  border-collapse: collapse;
  width: 100%;
  font-size: 0.88rem;
  table-layout: fixed;
}}
.pde-ficha-excel th,
.pde-ficha-excel td {{
  border: 1px solid #1a1a1a;
  padding: 8px 10px;
  text-align: left;
  vertical-align: middle;
  word-wrap: break-word;
}}
.pde-ficha-excel td[rowspan] {{
  font-weight: 600;
  background: #f3f5f7;
  text-align: center;
}}
</style>
<table>
  <tbody>
    {''.join(filas_html)}
  </tbody>
</table>
</div>
""".strip()


def _tabla_desde_hoja(ws) -> pd.DataFrame:
    """DataFrame plano (fallback / depuracion); omite notas editoriales."""
    min_r, max_r, min_c, max_c = _limites_hoja(ws)
    if max_r < min_r:
        return pd.DataFrame()
    merges = _mapa_merges(ws)
    cubiertas = _celdas_cubiertas(ws)
    filas_omitir = {
        r
        for r in range(1, int(ws.max_row or 0) + 1)
        if _fila_es_solo_editorial(ws, r, int(ws.max_column or 0))
    }
    filas: list[list[str]] = []
    n_cols = max_c - min_c + 1
    for r in range(min_r, max_r + 1):
        if r in filas_omitir:
            continue
        vals = [""] * n_cols
        for c in range(min_c, max_c + 1):
            if (r, c) in cubiertas:
                continue
            texto = _texto_celda(ws.cell(r, c).value)
            if _es_nota_editorial(texto):
                texto = ""
            idx = c - min_c
            vals[idx] = texto
            info = merges.get((r, c))
            if info is not None and info[3] > 1:
                pass
        if any(vals):
            filas.append(vals)
    if not filas:
        return pd.DataFrame()
    columnas = [f"Columna {j + 1}" for j in range(n_cols)]
    return pd.DataFrame(filas, columns=columnas)


@lru_cache(maxsize=1)
def _cargar_fichas_excel() -> dict[str, FichaExcelModelo]:
    """Mapa catalogo_id -> ficha. Si no hay match, clave hoja:<nombre>."""
    if not ARCHIVO_FICHAS.is_file():
        return {}

    import openpyxl

    # data_only para valores; segunda pasada para imagenes embebidas.
    wb = openpyxl.load_workbook(ARCHIVO_FICHAS, data_only=True)
    tablas: dict[str, tuple[str, pd.DataFrame, str, str | None]] = {}
    for nombre in wb.sheetnames:
        ws = wb[nombre]
        catalogo_id = _emparejar_hoja(nombre)
        tablas[nombre] = (
            nombre,
            _tabla_desde_hoja(ws),
            _html_desde_hoja(ws),
            catalogo_id,
        )
    wb.close()

    wb2 = openpyxl.load_workbook(ARCHIVO_FICHAS, data_only=False)
    resultado: dict[str, FichaExcelModelo] = {}
    for nombre in wb2.sheetnames:
        ws = wb2[nombre]
        _nombre, tabla, html, catalogo_id = tablas.get(
            nombre,
            (nombre, pd.DataFrame(), "", _emparejar_hoja(nombre)),
        )
        media = CARPETA_MEDIA / _slug(nombre)
        imagenes = _extraer_imagenes_hoja(ws, media)
        key = catalogo_id or f"hoja:{nombre}"
        resultado[key] = FichaExcelModelo(
            hoja=nombre,
            tabla=tabla,
            html=html,
            imagenes=imagenes,
            catalogo_id=catalogo_id,
        )
    wb2.close()
    return resultado


def invalidar_cache_fichas() -> None:
    _cargar_fichas_excel.cache_clear()


def ficha_excel_por_catalogo_id(catalogo_id: str) -> FichaExcelModelo | None:
    if not (catalogo_id or "").strip():
        return None
    return _cargar_fichas_excel().get(catalogo_id.strip())


def ficha_excel_por_entrada(entrada) -> FichaExcelModelo | None:
    """Resuelve ficha Excel para una entrada del catalogo."""
    if entrada is None:
        return None
    directa = ficha_excel_por_catalogo_id(entrada.id)
    if directa is not None:
        return directa
    for ficha in _cargar_fichas_excel().values():
        if ficha.catalogo_id == entrada.id:
            return ficha
        if _emparejar_hoja(ficha.hoja) == entrada.id:
            return ficha
    return None


def imagenes_ficha_por_entrada(entrada) -> tuple[Path, ...]:
    ficha = ficha_excel_por_entrada(entrada)
    if ficha is None:
        return ()
    return ficha.imagenes
