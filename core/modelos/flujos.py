"""Diagramas de flujo de modelos (carpeta ``Flujo de modelos/`` en la raíz del proyecto)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.modelos.registro import MODELOS_IMPACTO

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
CARPETA_FLUJOS = RAIZ_PROYECTO / "Flujo de modelos"

_IMAGENES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
_TEXTOS = {".txt", ".md"}

# Nombres de archivo (sin extensión) asociados a cada modelo.
_ALIASES_FLUJO: dict[str, tuple[str, ...]] = {
    "CALCULO_ACTIVO": (
        "ESQUEMA CALCULO POR ACTIVO",
        "ESQUEMA CALCULO ACTIVO",
        "CALCULO_ACTIVO",
    ),
    "PI_AGITACION": (
        "PI SUPERACIÓN DE UMBRAL",
        "PI SUPERACION DE UMBRAL",
        "PI AGITACIÓN",
        "PI AGITACION",
        "PI_AGITACION",
    ),
    "PI_CALADO_ELS": (
        "OPEX FALTA DE CALADO",
        "PI CALADO",
        "PI_CALADO_ELS",
    ),
    "PI_CALADO_ELU": (
        "CAPEX FALTA DE CALADO",
        "PI CALADO ELU",
        "PI_CALADO_ELU",
    ),
    "PI_FRANCOBORDO": (
        "PI FALTA DE FRANCOBORDO",
        "PI FALTA FRANCOBORDO",
        "PI_FRANCOBORDO",
    ),
}


@dataclass(frozen=True)
class DiagramaFlujo:
    modelo_id: str
    ruta: Path
    tipo: str  # "imagen" | "texto"


def _normalizar_nombre(texto: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return "".join(c for c in t.upper() if c.isalnum())


def _coincide_archivo(archivo: Path, alias: str) -> bool:
    return _normalizar_nombre(archivo.stem) == _normalizar_nombre(alias)


def buscar_diagrama(modelo_id: str) -> DiagramaFlujo | None:
    """Localiza imagen o texto de flujo para un modelo registrado o esquema."""
    if not CARPETA_FLUJOS.is_dir():
        return None

    meta = MODELOS_IMPACTO.get(modelo_id)
    alias_base = (meta.metadatos.nombre,) if meta else ()
    alias = _ALIASES_FLUJO.get(modelo_id, ()) + alias_base + (modelo_id,)

    candidatos: list[Path] = []
    for alias_nombre in alias:
        for ext in sorted(_IMAGENES | _TEXTOS):
            ruta = CARPETA_FLUJOS / f"{alias_nombre}{ext}"
            if ruta.is_file():
                candidatos.append(ruta)

    if not candidatos:
        for archivo in CARPETA_FLUJOS.iterdir():
            if not archivo.is_file():
                continue
            if any(_coincide_archivo(archivo, a) for a in alias):
                candidatos.append(archivo)

    if not candidatos:
        return None

    def prioridad(p: Path) -> tuple[int, str]:
        ext = p.suffix.lower()
        if ext in _IMAGENES:
            return (0, p.name)
        if ext in _TEXTOS:
            return (1, p.name)
        return (2, p.name)

    elegido = sorted(candidatos, key=prioridad)[0]
    tipo = "imagen" if elegido.suffix.lower() in _IMAGENES else "texto"
    return DiagramaFlujo(modelo_id=modelo_id, ruta=elegido, tipo=tipo)
