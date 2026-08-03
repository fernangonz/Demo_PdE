# -*- coding: utf-8 -*-
"""Fichas documentales desde Word en ``Fichas/*.docx`` (un archivo = un modelo).

El nombre del archivo (sin extension) se empareja con el catalogo igual que
antes las hojas de Excel: p.ej. ``PI FALTA DE FRANCOBORDO.docx`` ->
``PI Falta de francobordo`` / ``falta_francobordo_elo``.

Ruta robusta: tablas e imagenes con ``python-docx`` (+ zip OOXML).
Mammoth queda como fallback opcional si esta instalado.
"""
from __future__ import annotations

import sys

import base64
import html as html_lib
import logging
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
CARPETA_FICHAS = RAIZ_PROYECTO / "Fichas"
CARPETA_MEDIA = CARPETA_FICHAS / "_media"

_EXTENSIONES_WORD = (".docx",)
_log = logging.getLogger(__name__)

_CSS_FICHA = (
    ".pde-ficha-word{"
    "font-family:Calibri,'Segoe UI',Arial,sans-serif;"
    "font-size:15px;line-height:1.45;color:#1a1a1a;"
    "}"
    ".pde-ficha-word table{"
    "border-collapse:collapse;width:100%;margin:0.75em 0;"
    "}"
    ".pde-ficha-word th,.pde-ficha-word td{"
    "border:1px solid #333;padding:6px 8px;vertical-align:top;"
    "}"
    ".pde-ficha-word p{margin:0.4em 0;}"
    ".pde-ficha-word img{max-width:100%;height:auto;display:block;margin:8px auto;}"
    ".pde-ficha-word h1,.pde-ficha-word h2,.pde-ficha-word h3{"
    "margin:0.8em 0 0.35em;font-weight:700;"
    "}"
)


@dataclass(frozen=True)
class FichaWordModelo:
    """Contenido de un .docx asociado a un modelo del catalogo."""

    archivo: str
    html: str
    imagenes: tuple[Path, ...]
    catalogo_id: str | None = None
    ruta: Path | None = None


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", t.lower())


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", str(texto or ""))
    t = t.encode("ascii", "ignore").decode("ascii")
    t = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")
    return t or "ficha"


def _aliases_catalogo(entrada) -> set[str]:
    """Nombres normalizados con los que un archivo Word puede emparejarse."""
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


def emparejar_nombre_ficha(nombre: str) -> str | None:
    """Devuelve ``entrada.id`` del catalogo o None.

    ``nombre`` puede ser hoja antigua, stem de archivo o titulo de modelo.
    """
    from core.modelos.catalogo_impactos import CATALOGO_MODOS_IMPACTO

    clave = _normalizar(Path(str(nombre or "")).stem)
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


def _listar_docx() -> list[Path]:
    if not CARPETA_FICHAS.is_dir():
        return []
    rutas: list[Path] = []
    for path in sorted(CARPETA_FICHAS.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        if path.name.startswith("~$"):
            continue
        if path.suffix.lower() in _EXTENSIONES_WORD:
            rutas.append(path)
    return rutas


def _ext_imagen(data: bytes, content_type: str = "", nombre: str = "") -> str:
    ct = (content_type or "").lower()
    ext_nombre = Path(nombre).suffix.lower() if nombre else ""
    if ext_nombre in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".emf", ".wmf"}:
        return ".jpg" if ext_nombre == ".jpeg" else ext_nombre
    if "jpeg" in ct or "jpg" in ct or data[:2] == b"\xff\xd8":
        return ".jpg"
    if "png" in ct or data[:8].startswith(b"\x89PNG"):
        return ".png"
    if "gif" in ct or data[:4] == b"GIF8":
        return ".gif"
    if "webp" in ct:
        return ".webp"
    return ".bin"


def _extraer_imagenes_media(ruta_docx: Path, media_dir: Path) -> tuple[Path, ...]:
    """Extrae imagenes embebidas del paquete OOXML a ``Fichas/_media/<slug>/``."""
    media_dir.mkdir(parents=True, exist_ok=True)
    guardadas: list[Path] = []
    try:
        with zipfile.ZipFile(ruta_docx) as zf:
            nombres = [
                n
                for n in zf.namelist()
                if n.startswith("word/media/") and not n.endswith("/")
            ]
            for i, nombre in enumerate(sorted(nombres)):
                data = zf.read(nombre)
                if not data:
                    continue
                ext = Path(nombre).suffix.lower() or _ext_imagen(data, nombre=nombre)
                if ext in {".emf", ".wmf"}:
                    # No mostrables directamente en Streamlit; se omiten.
                    continue
                dest = media_dir / f"img_{i}{ext}"
                if not dest.is_file() or dest.stat().st_size != len(data):
                    dest.write_bytes(data)
                guardadas.append(dest)
    except (OSError, zipfile.BadZipFile) as exc:
        _log.warning("No se pudieron extraer imagenes de %s: %s", ruta_docx.name, exc)
        return ()
    return tuple(guardadas)


def _extraer_imagenes_python_docx(ruta_docx: Path, media_dir: Path) -> tuple[Path, ...]:
    """Extrae imagenes via ``document.part.related_parts`` (python-docx)."""
    try:
        from docx import Document
        from docx.opc.constants import RELATIONSHIP_TYPE as RT
    except ImportError:
        return ()

    media_dir.mkdir(parents=True, exist_ok=True)
    guardadas: list[Path] = []
    try:
        doc = Document(str(ruta_docx))
        parts = getattr(doc.part, "related_parts", {}) or {}
        i = 0
        for rel in doc.part.rels.values():
            try:
                if rel.reltype != RT.IMAGE:
                    continue
                part = rel.target_part
            except Exception:
                continue
            data = part.blob
            if not data:
                continue
            ct = getattr(part, "content_type", "") or ""
            nombre = getattr(part, "partname", None)
            nombre_s = str(nombre) if nombre else ""
            ext = _ext_imagen(data, content_type=ct, nombre=nombre_s)
            if ext in {".emf", ".wmf", ".bin"}:
                continue
            dest = media_dir / f"img_{i}{ext}"
            if not dest.is_file() or dest.stat().st_size != len(data):
                dest.write_bytes(data)
            guardadas.append(dest)
            i += 1
        # related_parts dict path (algunas builds)
        if not guardadas and parts:
            for part in parts.values():
                ct = getattr(part, "content_type", "") or ""
                if not str(ct).startswith("image/"):
                    continue
                data = getattr(part, "blob", None)
                if not data:
                    continue
                nombre_s = str(getattr(part, "partname", "") or "")
                ext = _ext_imagen(data, content_type=ct, nombre=nombre_s)
                if ext in {".emf", ".wmf", ".bin"}:
                    continue
                dest = media_dir / f"img_{i}{ext}"
                if not dest.is_file() or dest.stat().st_size != len(data):
                    dest.write_bytes(data)
                guardadas.append(dest)
                i += 1
    except Exception as exc:
        _log.warning("python-docx imagenes fallo en %s: %s", ruta_docx.name, exc)
        return ()
    return tuple(guardadas)


_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _celda_a_html(texto: str) -> str:
    t = (texto or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not t:
        return "&nbsp;"
    return html_lib.escape(t).replace("\n", "<br/>")


def _tc_texto(tc, tabla) -> str:
    """Texto de una celda OOXML ``w:tc`` via python-docx."""
    from docx.table import _Cell

    return _Cell(tc, tabla).text or ""


def _tc_grid_span(tc) -> int:
    """``w:gridSpan`` (colspan); por defecto 1."""
    tc_pr = tc.find(f"{_W_NS}tcPr")
    if tc_pr is None:
        return 1
    gs = tc_pr.find(f"{_W_NS}gridSpan")
    if gs is None:
        return 1
    try:
        return max(1, int(gs.get(f"{_W_NS}val") or 1))
    except (TypeError, ValueError):
        return 1


def _tc_vmerge(tc) -> str | None:
    """Estado de fusion vertical OOXML.

    - ``None``: celda normal (sin vMerge)
    - ``\"restart\"``: inicio de fusion vertical
    - ``\"continue\"``: continuation (no emitir ``<td>``)

    En OOXML, ``w:vMerge`` sin ``w:val`` equivale a ``continue``.
    """
    tc_pr = tc.find(f"{_W_NS}tcPr")
    if tc_pr is None:
        return None
    vm = tc_pr.find(f"{_W_NS}vMerge")
    if vm is None:
        return None
    val = (vm.get(f"{_W_NS}val") or "").strip().lower()
    if not val or val == "continue":
        return "continue"
    return "restart"


@dataclass(frozen=True)
class _TcInfo:
    tc: object
    col: int
    colspan: int
    vmerge: str | None
    text: str


def _parsear_filas_ooxml(tabla) -> list[list[_TcInfo]]:
    """Lee filas/celdas reales del ``w:tbl`` (respeta vMerge/gridSpan)."""
    filas: list[list[_TcInfo]] = []
    for tr in tabla._tbl.findall(f"{_W_NS}tr"):
        col = 0
        celdas: list[_TcInfo] = []
        for tc in tr.findall(f"{_W_NS}tc"):
            colspan = _tc_grid_span(tc)
            celdas.append(
                _TcInfo(
                    tc=tc,
                    col=col,
                    colspan=colspan,
                    vmerge=_tc_vmerge(tc),
                    text=_tc_texto(tc, tabla),
                )
            )
            col += colspan
        filas.append(celdas)
    return filas


def _calcular_rowspan(filas: list[list[_TcInfo]], ri: int, celda: _TcInfo) -> int:
    """Numero de filas que ocupa un restart (o celda normal = 1)."""
    if celda.vmerge == "continue":
        return 0
    if celda.vmerge != "restart":
        return 1
    span = 1
    col = celda.col
    for rj in range(ri + 1, len(filas)):
        debajo = next((c for c in filas[rj] if c.col == col), None)
        if debajo is None or debajo.vmerge != "continue":
            break
        span += 1
    return span


def _tabla_a_html(tabla) -> str:
    """Convierte una tabla Word a HTML respetando fusiones OOXML.

    - ``w:vMerge`` restart -> ``rowspan`` con el texto una sola vez
    - ``w:vMerge`` continue (o sin val) -> no se emite ``<td>``
    - ``w:gridSpan`` -> ``colspan``
    """
    filas = _parsear_filas_ooxml(tabla)
    filas_html: list[str] = []
    for ri, celdas in enumerate(filas):
        parts: list[str] = []
        tag = "th" if ri == 0 else "td"
        for celda in celdas:
            if celda.vmerge == "continue":
                continue
            rowspan = _calcular_rowspan(filas, ri, celda)
            attrs = ""
            if celda.colspan > 1:
                attrs += f' colspan="{celda.colspan}"'
            if rowspan > 1:
                attrs += f' rowspan="{rowspan}"'
            parts.append(f"<{tag}{attrs}>{_celda_a_html(celda.text)}</{tag}>")
        filas_html.append("<tr>" + "".join(parts) + "</tr>")
    return "<table>" + "".join(filas_html) + "</table>"


def _html_desde_python_docx(ruta: Path) -> str:
    """Tablas (+ parrafos sueltos) a HTML con python-docx."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(str(ruta))
    bloques: list[str] = []

    # Recorrer body en orden: parrafos y tablas intercalados.
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "tbl":
            tabla = Table(child, doc)
            bloques.append(_tabla_a_html(tabla))
        elif tag == "p":
            para = Paragraph(child, doc)
            texto = (para.text or "").strip()
            if texto:
                bloques.append(f"<p>{_celda_a_html(texto)}</p>")

    if not bloques and doc.tables:
        for tabla in doc.tables:
            bloques.append(_tabla_a_html(tabla))

    if not bloques:
        return ""

    body = "\n".join(bloques)
    return f'<div class="pde-ficha-word"><style>{_CSS_FICHA}</style>{body}</div>'


def _html_desde_mammoth(ruta: Path) -> str:
    """Fallback opcional: convierte el .docx a HTML con mammoth."""
    import mammoth

    def _convert_image(image):
        with image.open() as image_bytes:
            raw = image_bytes.read()
        encoded = base64.b64encode(raw).decode("ascii")
        content_type = getattr(image, "content_type", None) or "image/png"
        return {"src": f"data:{content_type};base64,{encoded}"}

    with ruta.open("rb") as f:
        result = mammoth.convert_to_html(
            f,
            convert_image=mammoth.images.img_element(_convert_image),
        )
    body = (result.value or "").strip()
    if not body:
        return ""
    return f'<div class="pde-ficha-word"><style>{_CSS_FICHA}</style>{body}</div>'


def _html_desde_docx(ruta: Path) -> str:
    """Convierte el .docx a HTML. Preferir python-docx; mammoth opcional."""
    errores: list[str] = []

    try:
        html = _html_desde_python_docx(ruta)
        if html:
            return html
        errores.append("python-docx: documento sin tablas/parrafos utiles")
    except ImportError as exc:
        errores.append(f"python-docx no instalado: {exc}")
    except Exception as exc:
        _log.exception("python-docx fallo al convertir %s", ruta.name)
        errores.append(f"python-docx: {type(exc).__name__}: {exc}")

    try:
        html = _html_desde_mammoth(ruta)
        if html:
            return html
        errores.append("mammoth: conversion vacia")
    except ImportError:
        errores.append("mammoth no instalado (fallback omitido)")
    except Exception as exc:
        _log.exception("mammoth fallo al convertir %s", ruta.name)
        errores.append(f"mammoth: {type(exc).__name__}: {exc}")

    detalle = html_lib.escape(" | ".join(errores) if errores else "motivo desconocido")
    py_exe = html_lib.escape(sys.executable)
    _log.error(
        "No se pudo convertir %s [%s]: %s",
        ruta.name,
        sys.executable,
        " | ".join(errores),
    )
    return (
        '<div class="pde-ficha-word"><p>'
        f"No se pudo convertir {html_lib.escape(ruta.name)}. "
        f"<code>{detalle}</code>"
        f" <small>(Python: <code>{py_exe}</code>)</small>"
        "</p></div>"
    )


def _imagenes_desde_docx(ruta: Path, media_dir: Path) -> tuple[Path, ...]:
    """Imagenes para el panel Esquema: python-docx, si no zip OOXML."""
    imgs = _extraer_imagenes_python_docx(ruta, media_dir)
    if imgs:
        return imgs
    return _extraer_imagenes_media(ruta, media_dir)


@lru_cache(maxsize=1)
def _cargar_fichas_word() -> dict[str, FichaWordModelo]:
    """Mapa catalogo_id -> ficha. Sin match: clave ``docx:<stem>``."""
    resultado: dict[str, FichaWordModelo] = {}
    for ruta in _listar_docx():
        stem = ruta.stem
        catalogo_id = emparejar_nombre_ficha(stem)
        media = CARPETA_MEDIA / _slug(stem)
        imagenes = _imagenes_desde_docx(ruta, media)
        html = _html_desde_docx(ruta)
        key = catalogo_id or f"docx:{stem}"
        resultado[key] = FichaWordModelo(
            archivo=ruta.name,
            html=html,
            imagenes=imagenes,
            catalogo_id=catalogo_id,
            ruta=ruta,
        )
    return resultado


def invalidar_cache_fichas() -> None:
    _cargar_fichas_word.cache_clear()


def ficha_word_por_catalogo_id(catalogo_id: str) -> FichaWordModelo | None:
    if not (catalogo_id or "").strip():
        return None
    return _cargar_fichas_word().get(catalogo_id.strip())


def ficha_word_por_entrada(entrada) -> FichaWordModelo | None:
    """Resuelve ficha Word para una entrada del catalogo."""
    if entrada is None:
        return None
    directa = ficha_word_por_catalogo_id(entrada.id)
    if directa is not None:
        return directa
    for ficha in _cargar_fichas_word().values():
        if ficha.catalogo_id == entrada.id:
            return ficha
        if emparejar_nombre_ficha(ficha.archivo) == entrada.id:
            return ficha
    return None


def imagenes_ficha_por_entrada(entrada) -> tuple[Path, ...]:
    ficha = ficha_word_por_entrada(entrada)
    if ficha is None:
        return ()
    return ficha.imagenes


def fichas_disponibles() -> tuple[str, ...]:
    """Nombres de archivos Word detectados en ``Fichas/``."""
    return tuple(p.name for p in _listar_docx())
