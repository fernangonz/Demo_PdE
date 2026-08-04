# -*- coding: utf-8 -*-
"""Ventanas auxiliares para PDFs (modal + pestaña nueva)."""

from __future__ import annotations

import html as _html
import re
import shutil
import unicodedata
from pathlib import Path

import streamlit as st

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
CARPETA_STATIC = RAIZ_PROYECTO / "static"

KEY_MODAL_MAXIMIZADO = "pde_pdf_modal_max"

_RE_SLUG_NO_ASCII = re.compile(r"[^A-Za-z0-9._-]+")


def slug_ascii(nombre: str) -> str:
    """Slug ASCII apto para nombre de fichero servido por Streamlit."""
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    base = base.strip().replace(" ", "_")
    base = _RE_SLUG_NO_ASCII.sub("_", base)
    base = base.strip("._-") or "documento"
    return base.lower()


def preparar_pdf_publico(ruta_pdf, *, subcarpeta):
    """Copia ``ruta_pdf`` a ``static/<subcarpeta>/<slug>.pdf`` si es necesario.

    Devuelve la ruta local del PDF publicado, o ``None`` si no existe.
    Solo recopia si cambia tamaño o mtime del origen.
    """
    if ruta_pdf is None:
        return None
    origen = Path(ruta_pdf)
    if not origen.is_file():
        return None

    destino_dir = CARPETA_STATIC / subcarpeta
    destino_dir.mkdir(parents=True, exist_ok=True)

    destino = destino_dir / f"{slug_ascii(origen.stem)}.pdf"

    try:
        origen_stat = origen.stat()
        if destino.is_file():
            destino_stat = destino.stat()
            mismo_tam = destino_stat.st_size == origen_stat.st_size
            mismo_mtime = int(destino_stat.st_mtime) >= int(origen_stat.st_mtime)
            if mismo_tam and mismo_mtime:
                return destino
        shutil.copyfile(origen, destino)
    except OSError:
        return None
    return destino


def url_pdf_publico(ruta_publicada):
    """URL absoluta-al-origen para el PDF publicado (``/app/static/...``).

    Streamlit expone ``static/`` bajo ``/app/static/...`` cuando
    ``[server] enableStaticServing = true``. Devolvemos la forma absoluta
    (leading ``/``) para que el navegador no la resuelva contra el path
    actual, que puede contener query strings de Streamlit.
    """
    if ruta_publicada is None:
        return None
    ruta = Path(ruta_publicada)
    try:
        rel = ruta.resolve().relative_to(CARPETA_STATIC.resolve())
    except (OSError, ValueError):
        return None
    partes = "/".join(rel.parts)
    return f"/app/static/{partes}"


def _inyectar_css_dialogo_maximizado():
    st.markdown(
        """
        <style>
        div[data-testid="stModal"] div[role="dialog"] {
            max-width: 95vw !important;
            width: 95vw !important;
        }
        div[data-testid="stModal"] div[role="dialog"] > div {
            max-width: 100% !important;
        }
        div[data-testid="stModal"] div[role="dialog"] iframe {
            width: 100% !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _pdf_viewer_bytes(data, *, height, key):
    try:
        import streamlit_pdf  # type: ignore[import-not-found]
    except Exception as exc:
        import sys
        return (
            False,
            (
                "El visor PDF necesita el componente **streamlit-pdf**.\n\n"
                "Instálalo en el intérprete de Streamlit:\n"
                f"`{sys.executable} -m pip install \"streamlit-pdf>=1.0.0,<2\"`\n\n"
                f"Detalle: {type(exc).__name__}: {exc}"
            ),
        )
    try:
        streamlit_pdf.pdf_viewer(file=data, height=int(height), key=key or None)
        return True, ""
    except Exception as exc:
        return False, f"streamlit_pdf.pdf_viewer: {type(exc).__name__}: {exc}"


def cerrar_dialogo_pdf(state_key):
    st.session_state.pop(state_key, None)
    st.session_state.pop(KEY_MODAL_MAXIMIZADO, None)


def _toggle_maximizado():
    st.session_state[KEY_MODAL_MAXIMIZADO] = not st.session_state.get(
        KEY_MODAL_MAXIMIZADO, False
    )


def link_button_nueva_pestana(label, url):
    """Enlace tipo botón que SIEMPRE abre en pestaña nueva.

    Preferimos un ``<a target="_blank">`` renderizado como botón (via CSS)
    en lugar de ``st.link_button``: garantiza que el navegador respete
    ``target="_blank"`` incluso con query strings de Streamlit activos.
    """
    safe_url = _html.escape(url, quote=True)
    safe_label = _html.escape(label, quote=True)
    st.markdown(
        f"""
        <a href="{safe_url}" target="_blank" rel="noopener noreferrer"
           class="pde-btn-newtab">{safe_label} ↗</a>
        <style>
        .pde-btn-newtab {{
            display: inline-block;
            width: 100%;
            padding: 0.375rem 0.75rem;
            font-weight: 400;
            font-size: 0.875rem;
            line-height: 1.6;
            color: rgb(49, 51, 63);
            text-align: center;
            text-decoration: none;
            background-color: rgb(255, 255, 255);
            border: 1px solid rgba(49, 51, 63, 0.2);
            border-radius: 0.5rem;
            box-sizing: border-box;
            transition: background-color 0.15s ease, border-color 0.15s ease;
        }}
        .pde-btn-newtab:hover {{
            border-color: rgb(255, 75, 75);
            color: rgb(255, 75, 75);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def abrir_dialogo_pdf(*, titulo, ruta_pdf, state_key, url_pestana_nueva=None, key_suffix=""):
    """Abre el modal PDF si ``state_key`` está activo en ``session_state``."""
    if not st.session_state.get(state_key):
        return

    maximizado = bool(st.session_state.get(KEY_MODAL_MAXIMIZADO, False))
    altura = 900 if maximizado else 700
    key_prefix = key_suffix or state_key

    @st.dialog(titulo, width="large")
    def _dlg():
        if maximizado:
            _inyectar_css_dialogo_maximizado()

        c_max, c_link, c_dl, c_cerrar = st.columns([1, 1.6, 1.3, 1], gap="small")
        with c_max:
            st.button(
                "Restaurar" if maximizado else "Maximizar",
                key=f"{key_prefix}_btn_max",
                use_container_width=True,
                on_click=_toggle_maximizado,
            )
        with c_link:
            if url_pestana_nueva:
                link_button_nueva_pestana(
                    "Abrir en pestaña nueva", url_pestana_nueva
                )
        with c_dl:
            if ruta_pdf is not None and Path(ruta_pdf).is_file():
                try:
                    _bytes_dl = Path(ruta_pdf).read_bytes()
                    st.download_button(
                        "Descargar PDF",
                        data=_bytes_dl,
                        file_name=Path(ruta_pdf).name,
                        mime="application/pdf",
                        key=f"{key_prefix}_btn_dl",
                        use_container_width=True,
                    )
                except OSError:
                    pass
        with c_cerrar:
            if st.button(
                "Cerrar",
                key=f"{key_prefix}_btn_cerrar",
                use_container_width=True,
                type="primary",
            ):
                cerrar_dialogo_pdf(state_key)
                st.rerun()

        if ruta_pdf is None or not Path(ruta_pdf).is_file():
            st.warning(
                "PDF no disponible. Comprueba que el archivo exista en "
                "`Flujo de modelos/` (o carpeta correspondiente)."
            )
            return

        data = Path(ruta_pdf).read_bytes()
        if not data:
            st.error(f"El PDF está vacío: `{Path(ruta_pdf).name}`")
            return

        st.caption(f"Documento: `{Path(ruta_pdf).name}`")
        if url_pestana_nueva:
            st.caption(f"URL directa: `{url_pestana_nueva}`")
        ok, err = _pdf_viewer_bytes(
            data, height=altura, key=f"{key_prefix}_viewer_{int(maximizado)}"
        )
        if not ok:
            st.error(err)

    _dlg()


# --- BEGIN abrir_dialogo_imagen ---
KEY_MODAL_MINIMIZADO = "pde_img_modal_min"


def _toggle_minimizado():
    st.session_state[KEY_MODAL_MINIMIZADO] = not st.session_state.get(
        KEY_MODAL_MINIMIZADO, False
    )


def cerrar_dialogo_imagen(state_key):
    """Cierra el modal de imagen y limpia estados asociados."""
    st.session_state.pop(state_key, None)
    st.session_state.pop(KEY_MODAL_MAXIMIZADO, None)
    st.session_state.pop(KEY_MODAL_MINIMIZADO, None)


def _mime_imagen(ruta):
    ext = Path(ruta).suffix.lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".svg": "image/svg+xml",
    }.get(ext, "application/octet-stream")


def abrir_dialogo_imagen(*, titulo, rutas_imagen, state_key, key_suffix=""):
    """Modal con imagen(es) y botones-icono (arriba-derecha):

    - ⇩ Descargar
    - − Minimizar / ☐ Restaurar (colapsa el contenido)
    - □ Maximizar / ❐ Restaurar (ocupa 95vw)
    - ✕ Cerrar

    ``rutas_imagen`` puede ser una ruta unica o iterable de rutas.
    """
    if not st.session_state.get(state_key):
        return

    if rutas_imagen is None:
        rutas = []
    elif isinstance(rutas_imagen, (str, Path)):
        rutas = [Path(rutas_imagen)]
    else:
        rutas = [Path(r) for r in rutas_imagen]

    maximizada = bool(st.session_state.get(KEY_MODAL_MAXIMIZADO, False))
    minimizada = bool(st.session_state.get(KEY_MODAL_MINIMIZADO, False))
    key_prefix = key_suffix or state_key

    @st.dialog(titulo, width="large")
    def _dlg():
        if maximizada:
            _inyectar_css_dialogo_maximizado()

        _inyectar_css_toolbar_iconos()

        c_spacer, c_dl, c_min, c_max, c_cerrar = st.columns(
            [8, 0.9, 0.9, 0.9, 0.9], gap="small", vertical_alignment="center"
        )

        with c_dl:
            _btn_icono_descarga(
                rutas[0] if rutas else None,
                key=f"{key_prefix}_btn_dl",
                mime_fn=_mime_imagen,
            )
        with c_min:
            st.button(
                "☐" if minimizada else "−",
                key=f"{key_prefix}_btn_min",
                help="Restaurar" if minimizada else "Minimizar",
                use_container_width=True,
                on_click=_toggle_minimizado,
                disabled=maximizada,
            )
        with c_max:
            st.button(
                "❐" if maximizada else "□",
                key=f"{key_prefix}_btn_max",
                help="Restaurar tama\u00f1o" if maximizada else "Maximizar",
                use_container_width=True,
                on_click=_toggle_maximizado,
                disabled=minimizada,
            )
        with c_cerrar:
            if st.button(
                "✕",
                key=f"{key_prefix}_btn_cerrar",
                help="Cerrar",
                type="primary",
                use_container_width=True,
            ):
                cerrar_dialogo_imagen(state_key)
                st.rerun()

        if minimizada:
            st.caption(
                "Ventana minimizada — pulsa ☐ para restaurar."
            )
            return

        if not rutas:
            st.warning("No hay imagen disponible para este modelo.")
            return

        for ruta in rutas:
            if not ruta.is_file():
                st.warning(f"No se encuentra: `{ruta.name}`")
                continue
            st.caption(f"Archivo: `{ruta.name}`")
            try:
                st.image(str(ruta), use_container_width=True)
            except Exception as exc:  # pragma: no cover
                st.error(
                    f"No se pudo renderizar la imagen `{ruta.name}`: "
                    f"{type(exc).__name__}: {exc}"
                )

    _dlg()


def _inyectar_css_toolbar_iconos():
    """CSS: compacta los botones de la fila superior del modal."""
    st.markdown(
        """
        <style>
        div[data-testid="stModal"] [data-testid="stHorizontalBlock"]:first-of-type
        button {
            min-height: 34px;
            padding: 2px 4px;
            font-size: 1.05rem;
            line-height: 1;
        }
        div[data-testid="stModal"] [data-testid="stHorizontalBlock"]:first-of-type
        [data-testid="stDownloadButton"] button {
            min-height: 34px;
            padding: 2px 4px;
            font-size: 1.05rem;
            line-height: 1;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _btn_icono_descarga(ruta, *, key, mime_fn):
    """Boton icono de descarga. Si no hay ruta, muestra placeholder deshabilitado."""
    if ruta is not None and Path(ruta).is_file():
        try:
            data = Path(ruta).read_bytes()
        except OSError:
            data = None
    else:
        data = None
    if data is None:
        st.button(
            "⇩",
            key=key,
            help="Descargar (no disponible)",
            use_container_width=True,
            disabled=True,
        )
        return
    st.download_button(
        "⇩",
        data=data,
        file_name=Path(ruta).name,
        mime=mime_fn(ruta),
        key=key,
        help="Descargar",
        use_container_width=True,
    )

# --- END abrir_dialogo_imagen ---
