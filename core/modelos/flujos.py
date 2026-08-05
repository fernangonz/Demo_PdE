"""Diagramas de flujo de modelos (carpeta ``Flujo de modelos/`` en la raiz del proyecto)."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
CARPETA_FLUJOS = RAIZ_PROYECTO / "Flujo de modelos"

# Tres o mas saltos seguidos -> un solo renglon en blanco entre bloques.
_RE_NEWLINES_EXTRA = re.compile(r"\n{3,}")
# Espacio alrededor de flechas sueltas para no hinchar el diagrama.
_RE_FLECHA_SOLA = re.compile(r"\n{2,}([↓⬇])\n{2,}")

_IMAGENES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
_TEXTOS = {".txt", ".md"}
_PDF = {".pdf"}

# Nombres de archivo (sin extension) asociados a cada modelo.
# ELO->PI, ELS->OPEX, ELU->CAPEX: cada familia tiene su propio procedimiento.
# No reutilizar OPEX/CAPEX como diagrama de PI FALTA DE CALADO.
# DIAGRAMA_FLUJO_UNICO: procedimiento maestro del catálogo (no es un motor).
ID_DIAGRAMA_FLUJO_UNICO = "DIAGRAMA_FLUJO_UNICO"

_ALIASES_FLUJO: dict[str, tuple[str, ...]] = {
    ID_DIAGRAMA_FLUJO_UNICO: (
        "DIAGRAMA DE FLUJO UNICO",
        "DIAGRAMA DE FLUJO ÚNICO",
        "FLUJO UNICO",
        "FLUJO ÚNICO",
        "PROCEDIMIENTO MAESTRO",
        ID_DIAGRAMA_FLUJO_UNICO,
    ),
    "CALCULO_ACTIVO": (
        "ESQUEMA CALCULO POR ACTIVO",
        "ESQUEMA CALCULO ACTIVO",
        "CALCULO_ACTIVO",
    ),
    "PI_AGITACION": (
        "PI SUPERACION DE UMBRAL",
        "PI SUPERACIÓN DE UMBRAL",
        "PI AGITACION",
        "PI AGITACIÓN",
        "PI_AGITACION",
    ),
    # Diagrama propio (sin búsqueda de umbral; 1 o 2 indicadores predefinidos Excel 4).
    "PI_PRECIPITACION": (
        "PI EXCESO DE PRECIPITACIÓN",
        "PI EXCESO DE PRECIPITACION",
        "PI_PRECIPITACION",
    ),
    "PI_CALADO_ELO": (
        "PI FALTA DE CALADO",
        "PI_CALADO_ELO",
    ),
    "PI_CALADO_ELS": (
        "OPEX FALTA DE CALADO",
        "PI_CALADO_ELS",
    ),
    "PI_CALADO_ELU": (
        "CAPEX FALTA DE CALADO",
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
    tipo: str  # "pdf" | "imagen" | "texto"


def _modelos_impacto() -> dict:
    from core.modelos.registro import MODELOS_IMPACTO

    return MODELOS_IMPACTO


def _normalizar_nombre(texto: str) -> str:
    import unicodedata

    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return "".join(c for c in t.upper() if c.isalnum())


def _coincide_archivo(archivo: Path, alias: str) -> bool:
    return _normalizar_nombre(archivo.stem) == _normalizar_nombre(alias)


def normalizar_texto_diagrama_para_display(texto: str) -> str:
    """Compacta whitespace de un .txt de flujo solo para visualizacion."""
    lineas = [
        linea.rstrip()
        for linea in texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    ]
    compacto = "\n".join(lineas)
    compacto = _RE_NEWLINES_EXTRA.sub("\n\n", compacto)
    compacto = _RE_FLECHA_SOLA.sub(r"\n\1\n", compacto)
    return compacto.strip() + ("\n" if compacto.strip() else "")


def leer_texto_diagrama(ruta: Path) -> str:
    """Lee un diagrama de texto y lo normaliza para mostrar en UI/HTML."""
    try:
        crudo = ruta.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        crudo = ruta.read_text(encoding="latin-1")
    return normalizar_texto_diagrama_para_display(crudo)


def _aliases_diagrama(modelo_id: str) -> tuple[str, ...]:
    meta = _modelos_impacto().get(modelo_id)
    alias_base = (meta.metadatos.nombre,) if meta else ()
    return _ALIASES_FLUJO.get(modelo_id, ()) + alias_base + (modelo_id,)


def _candidatos_diagrama(
    modelo_id: str,
    *,
    extensiones: set[str],
) -> list[Path]:
    if not CARPETA_FLUJOS.is_dir():
        return []

    alias = _aliases_diagrama(modelo_id)
    candidatos: list[Path] = []
    vistos: set[Path] = set()

    for alias_nombre in alias:
        for ext in sorted(extensiones):
            ruta = CARPETA_FLUJOS / f"{alias_nombre}{ext}"
            if ruta.is_file() and ruta not in vistos:
                # Evitar borradores tipo *_nuevo.pdf
                if ruta.stem.lower().endswith("_nuevo"):
                    continue
                candidatos.append(ruta)
                vistos.add(ruta)

    if not candidatos:
        for archivo in CARPETA_FLUJOS.iterdir():
            if not archivo.is_file():
                continue
            if archivo.suffix.lower() not in extensiones:
                continue
            if archivo.stem.lower().endswith("_nuevo"):
                continue
            if any(_coincide_archivo(archivo, a) for a in alias):
                if archivo not in vistos:
                    candidatos.append(archivo)
                    vistos.add(archivo)

    return candidatos


def _tipo_diagrama(ruta: Path) -> str:
    ext = ruta.suffix.lower()
    if ext in _PDF:
        return "pdf"
    if ext in _IMAGENES:
        return "imagen"
    return "texto"


def buscar_diagrama_pdf(modelo_id: str) -> DiagramaFlujo | None:
    """PDF esquematico del flujo (preferido en UI)."""
    candidatos = _candidatos_diagrama(modelo_id, extensiones=_PDF)
    if not candidatos:
        return None
    elegido = sorted(candidatos, key=lambda p: p.name)[0]
    return DiagramaFlujo(modelo_id=modelo_id, ruta=elegido, tipo="pdf")


def buscar_diagrama_texto(modelo_id: str) -> DiagramaFlujo | None:
    """Version TXT del procedimiento (boton TXT)."""
    candidatos = _candidatos_diagrama(modelo_id, extensiones=_TEXTOS)
    if not candidatos:
        return None
    elegido = sorted(candidatos, key=lambda p: p.name)[0]
    return DiagramaFlujo(modelo_id=modelo_id, ruta=elegido, tipo="texto")


def buscar_diagrama(modelo_id: str) -> DiagramaFlujo | None:
    """Localiza el diagrama principal: PDF > imagen > texto.

    El TXT se mantiene disponible aparte via ``buscar_diagrama_texto``.
    """
    pdf = buscar_diagrama_pdf(modelo_id)
    if pdf is not None:
        return pdf

    candidatos = _candidatos_diagrama(modelo_id, extensiones=_IMAGENES | _TEXTOS)
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
    return DiagramaFlujo(modelo_id=modelo_id, ruta=elegido, tipo=_tipo_diagrama(elegido))


def nombre_esperado_diagrama(modelo_id: str) -> str:
    """Nombre de procedimiento esperado en ``Flujo de modelos/`` (sin extension)."""
    aliases = _ALIASES_FLUJO.get(modelo_id, ())
    if aliases:
        return aliases[0]
    meta = _modelos_impacto().get(modelo_id)
    if meta is not None:
        return meta.metadatos.nombre
    return modelo_id


def mensaje_diagrama_faltante(modelo_id: str) -> str:
    """Mensaje user-facing cuando falta el diagrama de procedimiento del modo."""
    nombre = nombre_esperado_diagrama(modelo_id)
    return (
        "No se puede seguir el procedimiento de cálculo: "
        f"falta el diagrama en Flujo de modelos para «{nombre}»"
    )


def tiene_diagrama(modelo_id: str) -> bool:
    """Hay procedimiento usable (PDF, imagen o TXT) en Flujo de modelos."""
    return (
        buscar_diagrama_pdf(modelo_id) is not None
        or buscar_diagrama_texto(modelo_id) is not None
    )


def _aliases_esquema(modelo_id: str) -> tuple[str, ...]:
    """Nombres de archivo esperados para el esquema asociado a un modelo."""
    mid = (modelo_id or "").strip()
    if not mid:
        return ()
    if mid == "CALCULO_ACTIVO":
        return _ALIASES_FLUJO.get(mid, ())
    meta = _modelos_impacto().get(mid)
    nombre = meta.metadatos.nombre if meta else mid
    return (
        f"ESQUEMA {nombre}",
        f"ESQUEMA_{mid}",
        f"ESQUEMA {mid}",
        *(_ALIASES_FLUJO.get(f"ESQUEMA_{mid}", ())),
    )


def buscar_esquema(modelo_id: str) -> DiagramaFlujo | None:
    """Localiza un esquema (PDF/imagen/TXT) aparte del diagrama de flujo.

    Convención: archivos ``ESQUEMA …`` en ``Flujo de modelos/``.
    ``CALCULO_ACTIVO`` reutiliza sus aliases de esquema por activo.
    """
    if not CARPETA_FLUJOS.is_dir() or not (modelo_id or "").strip():
        return None

    aliases = _aliases_esquema(modelo_id)
    if not aliases:
        return None

    extensiones = _PDF | _IMAGENES | _TEXTOS
    candidatos: list[Path] = []
    vistos: set[Path] = set()
    for alias_nombre in aliases:
        for ext in sorted(extensiones):
            ruta = CARPETA_FLUJOS / f"{alias_nombre}{ext}"
            if ruta.is_file() and ruta not in vistos:
                if ruta.stem.lower().endswith("_nuevo"):
                    continue
                candidatos.append(ruta)
                vistos.add(ruta)

    if not candidatos:
        for archivo in CARPETA_FLUJOS.iterdir():
            if not archivo.is_file():
                continue
            if archivo.suffix.lower() not in extensiones:
                continue
            if archivo.stem.lower().endswith("_nuevo"):
                continue
            if any(_coincide_archivo(archivo, a) for a in aliases):
                if archivo not in vistos:
                    candidatos.append(archivo)
                    vistos.add(archivo)

    if not candidatos:
        return None

    def prioridad(p: Path) -> tuple[int, str]:
        ext = p.suffix.lower()
        if ext in _PDF:
            return (0, p.name)
        if ext in _IMAGENES:
            return (1, p.name)
        return (2, p.name)

    elegido = sorted(candidatos, key=prioridad)[0]
    return DiagramaFlujo(
        modelo_id=modelo_id,
        ruta=elegido,
        tipo=_tipo_diagrama(elegido),
    )


def tiene_esquema(modelo_id: str) -> bool:
    return buscar_esquema(modelo_id) is not None


def motores_sin_diagrama(
    modelo_ids: Iterable[str] | None = None,
) -> list[str]:
    """Ids de motores registrados (o de la lista dada) sin diagrama en Flujo de modelos."""
    ids = list(modelo_ids) if modelo_ids is not None else list(_modelos_impacto().keys())
    return [mid for mid in ids if not tiene_diagrama(mid)]


CODIGO_PROCEDIMIENTO_FLUJO_FALTANTE = "PROCEDIMIENTO_FLUJO_FALTANTE"
CODIGO_INDICADORES_MODELO_FALTANTES = "INDICADORES_MODELO_FALTANTES"


def resolver_motivo_y_codigo_diagrama_indicadores(
    modelo_id: str,
    motivo_indicadores: str,
) -> tuple[str, str]:
    """Motivo y Codigo coherentes cuando faltan diagrama y/o indicadores del modelo.

    - Solo diagrama / metodologia no definida -> ``PROCEDIMIENTO_FLUJO_FALTANTE``
      (sin inventar checklist de indicadores de otra rama).
    - Solo indicadores (diagrama presente) -> ``INDICADORES_MODELO_FALTANTES``
    """
    falta_diagrama = not tiene_diagrama(modelo_id)
    if falta_diagrama:
        # Procedimiento indefinido: no fabricar requisitos de indicadores.
        return mensaje_diagrama_faltante(modelo_id), CODIGO_PROCEDIMIENTO_FLUJO_FALTANTE
    texto_ind = (motivo_indicadores or "").strip()
    return texto_ind, CODIGO_INDICADORES_MODELO_FALTANTES
