# -*- coding: utf-8 -*-
"""Fichas documentales desde Fichas/Ficha.xlsx (una hoja = un modelo).

Cada hoja se empareja con una entrada del catalogo por nombre normalizado
(motor_nombre, aliases de flujo, modo de fallo). El contenido tabular
alimenta el boton FICHA; las imagenes embebidas alimentan el boton i.
"""

from __future__ import annotations

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


@dataclass(frozen=True)
class FichaExcelModelo:
    """Contenido de una hoja de Ficha.xlsx asociada a un modelo."""

    hoja: str
    tabla: pd.DataFrame
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


def _tabla_desde_hoja(ws) -> pd.DataFrame:
    filas: list[list[str]] = []
    max_cols = 0
    for row in ws.iter_rows(values_only=True):
        vals = [("" if c is None else str(c).strip()) for c in row]
        while vals and vals[-1] == "":
            vals.pop()
        if not any(v for v in vals):
            continue
        max_cols = max(max_cols, len(vals))
        filas.append(vals)
    if not filas:
        return pd.DataFrame()
    for i, vals in enumerate(filas):
        if len(vals) < max_cols:
            filas[i] = vals + [""] * (max_cols - len(vals))
    columnas = [f"Columna {j + 1}" for j in range(max_cols)]
    return pd.DataFrame(filas, columns=columnas)


@lru_cache(maxsize=1)
def _cargar_fichas_excel() -> dict[str, FichaExcelModelo]:
    """Mapa catalogo_id -> ficha. Si no hay match, clave hoja:<nombre>."""
    if not ARCHIVO_FICHAS.is_file():
        return {}

    import openpyxl

    # Tabla con data_only; imagenes en segunda pasada.
    wb = openpyxl.load_workbook(ARCHIVO_FICHAS, data_only=True)
    tablas: dict[str, tuple[str, pd.DataFrame, str | None]] = {}
    for nombre in wb.sheetnames:
        ws = wb[nombre]
        catalogo_id = _emparejar_hoja(nombre)
        tablas[nombre] = (nombre, _tabla_desde_hoja(ws), catalogo_id)
    wb.close()

    wb2 = openpyxl.load_workbook(ARCHIVO_FICHAS, data_only=False)
    resultado: dict[str, FichaExcelModelo] = {}
    for nombre in wb2.sheetnames:
        ws = wb2[nombre]
        _nombre, tabla, catalogo_id = tablas.get(
            nombre, (nombre, pd.DataFrame(), _emparejar_hoja(nombre))
        )
        media = CARPETA_MEDIA / _slug(nombre)
        imagenes = _extraer_imagenes_hoja(ws, media)
        key = catalogo_id or f"hoja:{nombre}"
        resultado[key] = FichaExcelModelo(
            hoja=nombre,
            tabla=tabla,
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
