"""Ventanas auxiliares para PDFs (modal + pestaña nueva).

Uso previsto: catálogo de MODELOS (diagramas de flujo), fichas Word y
esquemas. Todos los visores pueden invocar el mismo par de utilidades:

- :func:`abrir_dialogo_pdf`: modal ``@st.dialog`` con toolbar
  Maximizar / Cerrar y visor ``streamlit-pdf``.
- :func:`preparar_pdf_publico`: copia el PDF a ``static/<subcarpeta>/`` con
  nombre ASCII para que Streamlit lo sirva en ``/app/static/...`` y
  :func:`url_pdf_publico` devuelva la URL a usar en ``st.link_button``.

El modal se mantiene abierto entre reruns porque el trigger vive en
``st.session_state[state_key]`` (patrón oficial de Streamlit para
``@st.dialog``). El toggle de Maximizar comparte una clave global
``pde_pdf_modal_max`` — solo hay un modal abierto simultáneamente.
"""

from __future__ import annotations

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
    """Slug ASCII-safe apto para nombre de fichero servido por Streamlit."""
    base = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    base = base.strip().replace(" ", "_")
    base = _RE_SLUG_NO_ASCII.sub("_", base)
    base = base.strip("._-") or "documento"
    return base.lower()


def preparar_pdf_publico(ruta_pdf: Path, *, subcarpeta: str) -> Path | None:
    """Copia ``ruta_pdf`` a ``static/<subcarpeta>/<slug>.pdf`` si es necesario.

    Devuelve la ruta local del PDF publicado, o ``None`` si el fichero no
    existe. La copia solo se rehace si cambia el tamaño o la mtime del
    origen (evita reescribir en cada rerun de Streamlit).
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


def url_pdf_publico(ruta_publicada: Path) -> str | None:
    """URL relativa que sirve Streamlit para ``ruta_publicada`` (o ``None``).

    Streamlit expone ``static/`` bajo ``/app/static/...`` cuando
    ``[server] enableStaticServing = true``. Usamos la forma relativa
    ``./app/static/...`` para que funcione tanto en local como en despliegues
    con base URL distinta.
    """
    if ruta_publicada is None:
        return None
    ruta = Path(ruta_publicada)
    try:
        rel = ruta.resolve().relative_to(CARPETA_STATIC.resolve())
    except (OSError, ValueError):
        return None
    partes = "/".join(rel.parts)
    return f"./app/static/{partes}"


def _inyectar_css_dialogo_maximizado() -> None:
    """CSS que amplía el diálogo a casi toda la ventana (solo si maximizado)."""
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


def _pdf_viewer_bytes(data: bytes, *, height: int, key: str) -> tuple[bool, str]:
    """Renderiza el PDF con ``streamlit-pdf``. Devuelve (ok, mensaje_error)."""
    try:
        import streamlit_pdf  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - depende del entorno
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
    except Exception as exc:  # pragma: no cover - depende del entorno
        return False, f"streamlit_pdf.pdf_viewer: {type(exc).__name__}: {exc}"


def cerrar_dialogo_pdf(state_key: str) -> None:
    """Cierra el modal limpiando el trigger de sesión y refresca."""
    st.session_state.pop(state_key, None)
    st.session_state.pop(KEY_MODAL_MAXIMIZADO, None)


def _toggle_maximizado() -> None:
    st.session_state[KEY_MODAL_MAXIMIZADO] = not st.session_state.get(
        KEY_MODAL_MAXIMIZADO, False
    )


def abrir_dialogo_pdf(
    *,
    titulo: str,
    ruta_pdf: Path | None,
    state_key: str,
    url_pestana_nueva: str | None = None,
    key_suffix: str = "",
) -> None:
    """Abre el modal PDF si ``state_key`` está activo en ``session_state``.

    Debe llamarse en cada rerun (por ejemplo desde el bloque que dibuja el
    catálogo). Cuando el usuario pulsa el botón que setea
    ``st.session_state[state_key] = True``, la próxima ejecución dispara
    este ``@st.dialog``.
    """
    if not st.session_state.get(state_key):
        return

    maximizado = bool(st.session_state.get(KEY_MODAL_MAXIMIZADO, False))
    altura = 900 if maximizado else 700
    key_prefix = key_suffix or state_key

    @st.dialog(titulo, width="large")
    def _dlg() -> None:
        if maximizado:
            _inyectar_css_dialogo_maximizado()

        c_max, c_link, c_cerrar = st.columns([1, 1.4, 1], gap="small")
        with c_max:
            st.button(
                "Restaurar" if maximizado else "Maximizar",
                key=f"{key_prefix}_btn_max",
                use_container_width=True,
                on_click=_toggle_maximizado,
            )
        with c_link:
            if url_pestana_nueva:
                st.link_button(
                    "Abrir en pestaña nueva",
                    url=url_pestana_nueva,
                    use_container_width=True,
                )
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
        ok, err = _pdf_viewer_bytes(
            data, height=altura, key=f"{key_prefix}_viewer_{int(maximizado)}"
        )
        if not ok:
            st.error(err)

    _dlg()
