# -*- coding: utf-8 -*-
"""Fichas documentales desde Word en ``Fichas/*.docx`` (un archivo = un modelo).

El nombre del archivo (sin extension) se empareja con el catalogo igual que
antes las hojas de Excel: p.ej. ``PI FALTA DE FRANCOBORDO.docx`` ->
``PI Falta de francobordo`` / ``falta_francobordo_elo``.

El contenido se convierte a HTML con mammoth (tablas, parrafos, imagenes).
"""

from __future__ import annotations

import base64
import html as html_lib
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


def _ext_imagen(data: bytes, content_type: str = "") -> str:
    ct = (content_type or "").lower()
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
                ext = Path(nombre).suffix.lower() or _ext_imagen(data)
                dest = media_dir / f"img_{i}{ext}"
                if not dest.is_file() or dest.stat().st_size != len(data):
                    dest.write_bytes(data)
                guardadas.append(dest)
    except (OSError, zipfile.BadZipFile):
        return ()
    return tuple(guardadas)


def _html_desde_docx(ruta: Path) -> str:
    """Convierte el .docx a HTML (tablas, estilos basicos, imagenes inline)."""
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

    css = (
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
    return f'<div class="pde-ficha-word"><style>{css}</style>{body}</div>'


@lru_cache(maxsize=1)
def _cargar_fichas_word() -> dict[str, FichaWordModelo]:
    """Mapa catalogo_id -> ficha. Sin match: clave ``docx:<stem>``."""
    resultado: dict[str, FichaWordModelo] = {}
    for ruta in _listar_docx():
        stem = ruta.stem
        catalogo_id = emparejar_nombre_ficha(stem)
        media = CARPETA_MEDIA / _slug(stem)
        imagenes = _extraer_imagenes_media(ruta, media)
        try:
            html = _html_desde_docx(ruta)
        except Exception:
            html = (
                '<div class="pde-ficha-word"><p>'
                f"No se pudo convertir {html_lib.escape(ruta.name)}."
                "</p></div>"
            )
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
