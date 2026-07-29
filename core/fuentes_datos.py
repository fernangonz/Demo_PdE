"""Registro central: archivo Excel ↔ sección de la aplicación.

Modifica **solo este archivo** si renombras un Excel o una sección en el futuro.
El resto del código referencia las fuentes por ``id`` (clave interna estable).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TipoCarpetaDatos = Literal["modelos", "secciones"]


@dataclass(frozen=True)
class FuenteExcel:
    """Metadatos de un Excel usado por una sección."""

    id: str
    seccion: str
    archivo: str
    tipo_carpeta: TipoCarpetaDatos
    alternativas: tuple[str, ...] = ()
    hoja: str | None = None
    hojas_excluir: tuple[str, ...] = ()


# Orden = barra lateral de navegación (secciones con Excel).
FUENTES: tuple[FuenteExcel, ...] = (
    FuenteExcel(
        id="puertos",
        seccion="Puertos",
        archivo="Lista_de_puertos",
        tipo_carpeta="secciones",
        alternativas=("lista_puertos",),
    ),
    FuenteExcel(
        id="tipos_uo",
        seccion="Tipos de UO",
        archivo="Tipo_de_UO",
        tipo_carpeta="secciones",
        alternativas=("tipos_de_uo", "tipo_de_uo"),
    ),
    FuenteExcel(
        id="clima",
        seccion="Indicadores climáticos",
        archivo="Indicadores_climáticos",
        tipo_carpeta="modelos",
        alternativas=(
            "3_Indicadores_climáticos",
            "datos_clima",
            "indicadores_climaticos",
        ),
    ),
    FuenteExcel(
        id="impactos",
        seccion="Impactos a evaluar",
        archivo="Inventario_matriz_impactos_all",
        tipo_carpeta="secciones",
        alternativas=("inventario_matriz_impactos",),
    ),
    FuenteExcel(
        id="relacion_ivc",
        seccion="Relación impactos vs variables climáticas",
        archivo="Relación_umbrales_y_curvas_de_daño_vs_activos",
        tipo_carpeta="modelos",
        alternativas=(
            "2_Relación_umbrales_y_curvas_de_daño_vs_activos",
            "umbrales_curvas_de_daño",
            "umbrales_curvas",
            "relacion_umbrales_y_curvas_de_dano_vs_activos",
        ),
        hoja="ListRelacion impactos-indicador",
    ),
    FuenteExcel(
        id="umbrales",
        seccion="Relación umbrales y curvas de daño vs activos",
        archivo="Relación_umbrales_y_curvas_de_daño_vs_activos",
        tipo_carpeta="modelos",
        alternativas=(
            "2_Relación_umbrales_y_curvas_de_daño_vs_activos",
            "umbrales_curvas_de_daño",
            "umbrales_curvas",
            "relacion_umbrales_y_curvas_de_dano_vs_activos",
        ),
        hojas_excluir=(
            "listrelacion impactos-indicador",
            "contar",
        ),
    ),
    FuenteExcel(
        id="config_puerto",
        seccion="Configuración del puerto",
        archivo="Configuración_del_puerto",
        tipo_carpeta="modelos",
        alternativas=(
            "1_Configuración_del_puerto",
            "configuracion_del_puerto",
            "configuracion_puerto",
        ),
    ),
    FuenteExcel(
        id="relacion_modelos",
        seccion="Relación modelos, activos e indicadores",
        archivo="Relacion_modelos_activos_e_indicadores",
        tipo_carpeta="modelos",
        alternativas=(
            "4_Relacion_modelos_activos_e_indicadores",
            "Relacion modelos activos e indicadores",
            "Relación_modelos_activos_e_indicadores",
            "relacion_modelos_activos_e_indicadores",
            "relacion_modelos_activos_indicadores",
        ),
    ),
)

# Secciones sin Excel propio (resultados / modelos).
SECCIONES_MODELO: tuple[str, ...] = (
    "Modelos de impactos",
    "Modelos económicos",
)

_INDICE: dict[str, FuenteExcel] = {f.id: f for f in FUENTES}
_POR_SECCION: dict[str, FuenteExcel] = {f.seccion: f for f in FUENTES}


def fuente(id_fuente: str) -> FuenteExcel:
    """Devuelve la definición de una fuente por su id interno."""
    try:
        return _INDICE[id_fuente]
    except KeyError as exc:
        raise KeyError(f"Fuente desconocida: {id_fuente!r}") from exc


def fuente_por_seccion(nombre_seccion: str) -> FuenteExcel | None:
    """Devuelve la fuente vinculada a una sección, o None si es sección de modelo."""
    return _POR_SECCION.get(nombre_seccion)


def secciones_navegacion() -> list[str]:
    """Lista ordenada de secciones para la barra lateral."""
    return [f.seccion for f in FUENTES] + list(SECCIONES_MODELO)


def nombre_archivo_display(f: FuenteExcel) -> str:
    """Nombre de archivo para mensajes y popover (con extensión)."""
    return f"{f.archivo}.xlsx"


def candidatos_archivo(f: FuenteExcel) -> list[str]:
    """Nombres (sin extensión) a probar al localizar el Excel, en orden."""
    vistos: set[str] = set()
    salida: list[str] = []
    for nombre in (f.archivo, *f.alternativas):
        clave = nombre.strip().lower()
        if clave and clave not in vistos:
            vistos.add(clave)
            salida.append(nombre)
    return salida
