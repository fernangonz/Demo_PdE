"""Identidad visual Puertos del Estado / IHCantabria para la interfaz Streamlit."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIR_LOGOS = RAIZ_PROYECTO / "07_Logos"

LOGO_PUERTOS = DIR_LOGOS / "PuertosdelEstado_oscuro.png"
LOGO_IHC = DIR_LOGOS / "ihc.png"

BRAND_NAVY = "#050a30"
BRAND_NAVY_SOFT = "#0c1445"
BRAND_WHITE = "#ffffff"


@lru_cache(maxsize=4)
def _img_base64(ruta: Path) -> str:
    return base64.b64encode(ruta.read_bytes()).decode("ascii")


def inyectar_estilos_branding() -> None:
    """CSS global: cabecera, menu superior, pie y ajustes Streamlit.

    Regla de contraste global: cualquier recuadro/caja blanca lleva SIEMPRE
    texto en navy (#050a30). Solo la barra fija superior y el pie son navy con
    texto blanco. El area central de contenido es siempre blanca.
    """
    st.markdown(
        f"""
<style>
/* --------------------------------------------------------------------- */
/* Base: ocultar sidebar vacia y fijar fondo blanco en el area principal */
/* --------------------------------------------------------------------- */
[data-testid="stSidebar"] {{ display: none; }}
[data-testid="stSidebarCollapsedControl"] {{ display: none; }}

.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stMain"] > div,
section.main,
section.main > div {{
    background-color: {BRAND_WHITE} !important;
    color: {BRAND_NAVY};
}}

.block-container {{
    padding-top: 6.5rem;
    max-width: 100%;
    background-color: {BRAND_WHITE} !important;
    color: {BRAND_NAVY};
}}
.block-container p,
.block-container span,
.block-container label,
.block-container li,
.block-container h1,
.block-container h2,
.block-container h3,
.block-container h4,
.block-container h5,
.block-container h6,
.block-container [data-testid="stMarkdownContainer"],
.block-container [data-testid="stMarkdownContainer"] * {{
    color: {BRAND_NAVY};
}}

/* --------------------------------------------------------------------- */
/* Cabecera nativa Streamlit (menu 3 puntos): esquina superior derecha  */
/* --------------------------------------------------------------------- */
header[data-testid="stHeader"] {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    position: fixed !important;
    top: 0.55rem;
    right: 0.85rem;
    left: auto !important;
    width: auto !important;
    height: auto !important;
    min-height: 0 !important;
    overflow: visible !important;
    z-index: 1012;
    pointer-events: none !important;
}}
header[data-testid="stHeader"] > div {{
    position: static !important;
    width: auto !important;
    height: auto !important;
    pointer-events: none !important;
}}
[data-testid="stToolbar"] {{
    position: static !important;
    top: auto !important;
    right: auto !important;
    left: auto !important;
    bottom: auto !important;
    width: auto !important;
    height: auto !important;
    min-width: 0 !important;
    min-height: 0 !important;
    max-width: none !important;
    max-height: none !important;
    pointer-events: none !important;
}}
[data-testid="stToolbar"] > *,
[data-testid="stToolbar"] button,
[data-testid="stToolbar"] a {{ pointer-events: auto !important; }}
header[data-testid="stHeader"] svg {{
    fill: {BRAND_WHITE} !important;
    color: {BRAND_WHITE} !important;
}}

/* --------------------------------------------------------------------- */
/* CABECERA FIJA institucional (logo + menu de secciones)                */
/* Se marca SOLO el HorizontalBlock que contiene el marker (dentro de    */
/* la 1a columna). Asi evitamos pintar de navy todo el stVerticalBlock   */
/* principal de la app (que tambien contiene al marker como descendiente */
/* pero no debe recibir estos estilos).                                  */
/* --------------------------------------------------------------------- */
div[data-testid="stHorizontalBlock"]:has(.pde-brand-bar-marker) {{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    width: 100%;
    z-index: 1005;
    background: {BRAND_NAVY} !important;
    margin: 0 !important;
    padding: 0.75rem 5.5rem 0.75rem 1rem !important;
    min-height: 5rem;
    box-sizing: border-box;
    border-bottom: 1px solid rgba(255, 255, 255, 0.18);
    overflow: visible !important;
    align-items: center !important;
    gap: 0.75rem;
}}
div[data-testid="stHorizontalBlock"]:has(.pde-brand-bar-marker) > [data-testid="column"] {{
    background: transparent !important;
    align-items: center !important;
    display: flex !important;
}}
div[data-testid="stHorizontalBlock"]:has(.pde-brand-bar-marker) > [data-testid="column"] > div {{
    width: 100%;
}}

/* --------------------------------------------------------------------- */
/* Franja BLANCA continua dentro de la barra navy: contiene los 7        */
/* popovers/botones del menu. Cualquier stHorizontalBlock ANIDADO dentro */
/* del bloque marcado por .pde-brand-bar-marker es la franja del menu.  */
/* --------------------------------------------------------------------- */
/* La navbar es UNA sola pieza: el unico elemento con fondo blanco,       */
/* borde, radio y sombra. Altura fija y compacta; se centra en la franja  */
/* azul (que ya usa align-items:center).                                  */
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) {{
    background: {BRAND_WHITE} !important;
    border: 1px solid #d9dee8 !important;
    border-radius: 9px !important;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.10);
    padding: 0 !important;
    gap: 0 !important;
    flex-wrap: nowrap !important;
    align-items: stretch !important;
    justify-content: center !important;
    width: fit-content !important;
    max-width: 100% !important;
    height: 52px !important;
    min-height: 52px !important;
    align-self: center !important;
    overflow: hidden !important;
}}
/* Cada seccion = una celda plana que ocupa TODA la altura de la navbar.  */
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) > [data-testid="column"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) > [data-testid="stColumn"] {{
    background: transparent !important;
    padding: 0 !important;
    margin: 0 !important;
    display: flex !important;
    align-items: stretch !important;
    justify-content: center !important;
    flex: 0 0 auto !important;
    width: auto !important;
    min-width: 0 !important;
}}
/* Divisor vertical fino entre secciones (todas menos la primera). */
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) > [data-testid="column"] + [data-testid="column"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) > [data-testid="stColumn"] + [data-testid="stColumn"] {{
    border-left: 1px solid #e1e5ee !important;
}}
/* Cadena de contenedores internos de Streamlit -> altura completa,       */
/* sin gaps, centrado, para que la celda llene la navbar de arriba abajo. */
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) > [data-testid="column"] > div,
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) > [data-testid="stColumn"] > div,
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="stVerticalBlock"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="stLayoutWrapper"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="stElementContainer"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="stPopover"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="stPopover"] > div,
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) .stButton {{
    width: auto !important;
    height: 100% !important;
    gap: 0 !important;
    justify-content: center !important;
    align-items: stretch !important;
}}

.pde-logo-wrap img {{
    height: 58px;
    width: auto;
    min-width: 130px;
    max-width: 260px;
    display: block;
    object-fit: contain;
    filter: drop-shadow(0 0 4px rgba(255, 255, 255, 0.25));
}}

/* Ocultar markers auxiliares (no deben ocupar espacio visual) */
.element-container:has(> [data-testid="stMarkdownContainer"] .pde-brand-bar-marker),
.element-container:has(> [data-testid="stMarkdownContainer"] .pde-nav-slot),
.element-container:has(> [data-testid="stMarkdownContainer"] .pde-nav-active),
[data-testid="stElementContainer"]:has(.pde-brand-bar-marker),
[data-testid="stElementContainer"]:has(.pde-nav-slot),
[data-testid="stElementContainer"]:has(.pde-nav-brand),
[data-testid="stElementContainer"]:has(.pde-nav-active) {{
    display: none !important;
}}

/* --------------------------------------------------------------------- */
/* REGLA GLOBAL: cualquier recuadro blanco -> texto NAVY                 */
/* --------------------------------------------------------------------- */
.stButton > button,
[data-testid="stPopover"] > button,
[data-testid="stDownloadButton"] > button,
[data-testid="baseButton-secondary"],
[data-testid="baseButton-primary"],
button[kind="primary"],
button[kind="secondary"] {{
    background-color: {BRAND_WHITE} !important;
    color: {BRAND_NAVY} !important;
    border: 1px solid #d0d5dd !important;
}}
.stButton > button:hover,
[data-testid="stPopover"] > button:hover,
[data-testid="stDownloadButton"] > button:hover,
button[kind="primary"]:hover,
button[kind="secondary"]:hover {{
    background-color: #f8f9fc !important;
    border-color: #b8bfd0 !important;
    color: {BRAND_NAVY} !important;
}}
.stButton > button *,
[data-testid="stPopover"] > button *,
[data-testid="stDownloadButton"] > button * {{
    color: {BRAND_NAVY} !important;
    fill: {BRAND_NAVY} !important;
}}

/* Selectbox / inputs siempre con fondo blanco y texto navy */
[data-testid="stSelectbox"] label,
[data-testid="stTextInput"] label,
[data-testid="stNumberInput"] label,
[data-testid="stDateInput"] label,
[data-testid="stMultiSelect"] label {{
    color: {BRAND_NAVY} !important;
}}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
[data-testid="stMultiSelect"] div[data-baseweb="select"] > div,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stDateInput"] input,
[data-testid="stTextArea"] textarea {{
    background-color: {BRAND_WHITE} !important;
    color: {BRAND_NAVY} !important;
    border-color: #d0d5dd !important;
}}
[data-baseweb="popover"] li,
[data-baseweb="menu"] li,
[data-baseweb="popover"] ul,
[data-baseweb="menu"] ul {{
    background-color: {BRAND_WHITE} !important;
    color: {BRAND_NAVY} !important;
}}

/* --------------------------------------------------------------------- */
/* MENU SUPERIOR (dentro de la franja blanca continua)                   */
/* Botones sin fondo propio: la franja blanca hace de fondo compartido.  */
/* Estado activo indicado por border-bottom navy.                        */
/* --------------------------------------------------------------------- */
/* Cada boton = celda plana: SIN fondo, SIN borde, SIN radio, SIN sombra. */
/* Ocupa el 100% de la altura de la navbar y su texto va en una linea.    */
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) button {{
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    outline: none !important;
    color: {BRAND_NAVY} !important;
    height: 100% !important;
    min-height: 100% !important;
    width: 100% !important;
    min-width: max-content !important;
    margin: 0 !important;
    padding: 0 1.5rem !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 0.4rem !important;
    font-size: 0.8rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    white-space: nowrap !important;
    overflow: visible !important;
    text-overflow: clip !important;
    transition: background-color 0.15s ease;
}}
/* El texto/interno nunca se parte en dos lineas. */
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) button * {{
    white-space: nowrap !important;
    overflow: visible !important;
    text-overflow: clip !important;
    color: {BRAND_NAVY} !important;
    fill: {BRAND_NAVY} !important;
    text-shadow: none !important;
}}
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) button:hover {{
    background-color: #f4f7fb !important;
    color: {BRAND_NAVY} !important;
}}
/* Estado activo: subrayado navy grueso + negrita bajo la etiqueta activa. */
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="column"]:has(.pde-nav-active) button,
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="stColumn"]:has(.pde-nav-active) button {{
    border-bottom: 2px solid {BRAND_NAVY} !important;
    background-color: rgba(5, 10, 48, 0.06) !important;
    font-weight: 800 !important;
}}

/* Marca principal "DATOS BASE": mismo estilo pero mas grande y destacado. */
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="column"]:has(.pde-nav-brand) button,
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="stColumn"]:has(.pde-nav-brand) button {{
    font-size: 0.9rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.01em;
}}
/* El icono de la marca (casa) un poco mayor que el texto. */
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="column"]:has(.pde-nav-brand) button [data-testid="stIconMaterial"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="stColumn"]:has(.pde-nav-brand) button [data-testid="stIconMaterial"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="column"]:has(.pde-nav-brand) button span[class*="material"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) [data-testid="stColumn"]:has(.pde-nav-brand) button span[class*="material"] {{
    font-size: 1.2rem !important;
    vertical-align: middle;
}}
/* Iconos Material del menu: siempre navy sobre la franja blanca. */
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) button [data-testid="stIconMaterial"],
div[data-testid="stHorizontalBlock"]:has(.pde-nav-slot):not(:has(.pde-brand-bar-marker)) button span[class*="material"] {{
    color: {BRAND_NAVY} !important;
    fill: {BRAND_NAVY} !important;
}}

/* Logo (fallback en texto) sobre la barra navy */
div[data-testid="stHorizontalBlock"]:has(.pde-brand-bar-marker) .pde-logo-wrap,
div[data-testid="stHorizontalBlock"]:has(.pde-brand-bar-marker) .pde-logo-wrap * {{
    color: {BRAND_WHITE} !important;
}}

/* --------------------------------------------------------------------- */
/* Panel desplegable del popover (portal fuera de la cabecera)           */
/* Fondo blanco + texto navy                                             */
/* --------------------------------------------------------------------- */
[data-testid="stPopoverBody"] {{
    min-width: 240px;
    z-index: 1015 !important;
    background-color: {BRAND_WHITE} !important;
    color: {BRAND_NAVY} !important;
    border: 1px solid #d0d5dd !important;
}}
[data-testid="stPopoverBody"] *:not(svg):not(path) {{
    color: {BRAND_NAVY} !important;
}}
[data-testid="stPopoverBody"] .stButton > button,
[data-testid="stPopoverBody"] [data-testid="stDownloadButton"] > button {{
    background-color: {BRAND_WHITE} !important;
    color: {BRAND_NAVY} !important;
    border: 1px solid #d0d5dd !important;
    text-align: left;
    justify-content: flex-start;
}}
[data-testid="stPopoverBody"] .stButton > button:hover,
[data-testid="stPopoverBody"] [data-testid="stDownloadButton"] > button:hover {{
    background-color: #f8f9fc !important;
    border-color: #b8bfd0 !important;
    color: {BRAND_NAVY} !important;
}}

/* --------------------------------------------------------------------- */
/* Avisos (info/success) sobre fondo navy suave con texto blanco         */
/* --------------------------------------------------------------------- */
div[data-testid="stAlert"],
.stAlert,
[data-testid="stNotification"] {{
    background-color: {BRAND_NAVY_SOFT} !important;
    border: 1px solid rgba(255, 255, 255, 0.22) !important;
    color: {BRAND_WHITE} !important;
}}
div[data-testid="stAlert"] *,
.stAlert *,
[data-testid="stNotification"] * {{
    color: {BRAND_WHITE} !important;
}}
div[data-testid="stAlert"] a,
.stAlert a,
[data-testid="stNotification"] a {{
    color: {BRAND_WHITE} !important;
    text-decoration: underline;
}}
div[data-testid="stAlert"] code,
.stAlert code,
[data-testid="stNotification"] code {{
    color: {BRAND_WHITE} !important;
    background: rgba(255, 255, 255, 0.12) !important;
}}
div[data-testid="stAlert"] svg,
.stAlert svg {{
    fill: {BRAND_WHITE} !important;
    stroke: {BRAND_WHITE} !important;
    color: {BRAND_WHITE} !important;
}}

div[data-testid="stAlert"][kind="error"],
.stAlert[data-baseweb="notification"][kind="negative"] {{
    background-color: #5c1a1a !important;
    border-color: rgba(255, 255, 255, 0.25) !important;
}}
div[data-testid="stAlert"][kind="error"] *,
.stAlert[data-baseweb="notification"][kind="negative"] * {{
    color: {BRAND_WHITE} !important;
}}
div[data-testid="stAlert"][kind="warning"],
.stAlert[data-baseweb="notification"][kind="warning"] {{
    background-color: {BRAND_NAVY_SOFT} !important;
    border-color: rgba(255, 255, 255, 0.22) !important;
}}

/* --------------------------------------------------------------------- */
/* Pie institucional (IHCantabria) - mismo navy que la cabecera          */
/* --------------------------------------------------------------------- */
.pde-footer {{
    background: {BRAND_NAVY} !important;
    margin: 2.5rem -1rem -1rem -1rem;
    padding: 1rem 1.25rem;
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 0.75rem;
    border-top: 1px solid rgba(255, 255, 255, 0.15);
    color: {BRAND_WHITE} !important;
}}
.pde-footer span,
.pde-footer strong,
.pde-footer p,
.pde-footer a {{ color: {BRAND_WHITE} !important; }}
.pde-footer img {{
    height: 40px;
    width: auto;
    display: block;
    background: {BRAND_NAVY};
    filter: drop-shadow(0 0 4px rgba(255, 255, 255, 0.3));
}}

/* Mapa Folium en Inicio > Puertos */
div[data-testid="stIFrame"] iframe {{
    min-height: 560px;
}}

/* Streamlit 1.58: [data-testid=stDataFrameResizable] aplica
   border:1px + border-radius en estilo inline, pero sin overflow:hidden,
   así la rejilla Glide (.dvn-scroller) pinta una línea gris recta ~1px
   bajo la esquina redondeada (ficha Outputs). */
[data-testid="stDataFrame"] {{
    overflow: hidden !important;
}}
[data-testid="stDataFrameResizable"] {{
    overflow: hidden !important;
}}
[data-testid="stDataFrameResizable"] .stDataFrameGlideDataEditor,
[data-testid="stDataFrameResizable"] .dvn-scroller {{
    border-radius: inherit !important;
}}

/* --------------------------------------------------------------------- */
/* Lista de modelos (MODELOS): tarjetas navy, sin acentos «IA púrpura»   */
/* --------------------------------------------------------------------- */
div[data-testid="stVerticalBlockBorderWrapper"]:has(.pde-modelo-card-marker) {{
    border: 1px solid #c5ccd8 !important;
    border-radius: 8px !important;
    background: {BRAND_WHITE} !important;
    box-shadow: none !important;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(.pde-modelo-card-marker) button[kind="primary"],
div[data-testid="stVerticalBlockBorderWrapper"]:has(.pde-modelo-card-marker) button[data-testid="baseButton-primary"] {{
    background-color: rgba(5, 10, 48, 0.08) !important;
    border: 1px solid {BRAND_NAVY} !important;
    color: {BRAND_NAVY} !important;
    font-weight: 700 !important;
}}
</style>
        """,
        unsafe_allow_html=True,
    )


def _logo_html() -> str:
    if LOGO_PUERTOS.is_file():
        b64 = _img_base64(LOGO_PUERTOS)
        return (
            f'<div class="pde-logo-wrap">'
            f'<img src="data:image/png;base64,{b64}" alt="Puertos del Estado" />'
            f"</div>"
        )
    return (
        f'<div class="pde-logo-wrap">'
        f'<strong style="color:{BRAND_WHITE}; font-size:1.05rem;">Puertos del Estado</strong>'
        f"</div>"
    )


def abrir_cabecera_branding() -> tuple:
    """Marca el bloque de cabecera y devuelve columnas (logo | menu).

    El marker se coloca DENTRO de la primera columna: asi `:has()` sobre el
    stHorizontalBlock (fila de columnas) solo matchea la cabecera y no el
    bloque principal de la app, evitando que el fondo se vuelva azul.
    """
    cols = st.columns([0.9, 3.1], vertical_alignment="center")
    with cols[0]:
        st.markdown('<span class="pde-brand-bar-marker"></span>', unsafe_allow_html=True)
    return cols


def mostrar_logo_puertos() -> None:
    """Logo Puertos del Estado sobre cabecera azul."""
    st.markdown(_logo_html(), unsafe_allow_html=True)


def mostrar_pie_branding() -> None:
    """Pie con credito IHCantabria."""
    if LOGO_IHC.is_file():
        b64 = _img_base64(LOGO_IHC)
        img = (
            f'<img src="data:image/png;base64,{b64}" alt="IHCantabria" '
            f'style="height:40px;width:auto;background:{BRAND_NAVY};" />'
        )
    else:
        img = f"<strong style='color:{BRAND_WHITE}'>IHCantabria</strong>"
    st.markdown(
        f'<div class="pde-footer"><span style="color:{BRAND_WHITE}; font-size:0.78rem;">Desarrollado por</span>{img}</div>',
        unsafe_allow_html=True,
    )
