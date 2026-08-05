# -*- coding: utf-8 -*-
"""Plantilla estandar de pagina: titulo, contexto, KPIs, accion, herramientas.

Disenada para mantener jerarquia visual coherente con el branding PDE/IHC.
Los textos de UI con acentos se definen abajo con escapes Unicode.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

import streamlit as st

from core.branding import BRAND_NAVY, BRAND_NAVY_SOFT, BRAND_WHITE

_EM_DASH = "\u2014"


@dataclass(frozen=True)
class ContextoAnalisis:
    puerto: str = _EM_DASH
    escenario: str = _EM_DASH
    horizonte: str = _EM_DASH


@dataclass(frozen=True)
class KpiItem:
    etiqueta: str
    valor: str
    ayuda: str = ""


@dataclass(frozen=True)
class ExportItem:
    etiqueta: str
    data: bytes
    file_name: str
    mime: str
    key: str


def _inyectar_estilos_plantilla() -> None:
    if st.session_state.get("_pde_plantilla_css"):
        return
    st.session_state["_pde_plantilla_css"] = True
    st.markdown(
        f"""
<style>
.pde-ctx {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin: 0.25rem 0 0.85rem 0;
}}
.pde-ctx-chip {{
    display: inline-flex;
    align-items: baseline;
    gap: 0.35rem;
    padding: 0.28rem 0.65rem;
    border: 1px solid #c5ccd8;
    border-radius: 4px;
    background: #f7f8fb;
    color: {BRAND_NAVY};
    font-size: 0.82rem;
}}
.pde-ctx-chip strong {{
    font-weight: 700;
    color: {BRAND_NAVY};
}}
.pde-ctx-chip span {{
    opacity: 0.78;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 700;
}}
.pde-page-desc {{
    color: {BRAND_NAVY_SOFT};
    font-size: 0.95rem;
    margin: -0.35rem 0 0.75rem 0;
    max-width: 52rem;
}}
.pde-kpi-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem;
    margin: 0.35rem 0 1rem 0;
}}
.pde-kpi {{
    flex: 1 1 8.5rem;
    min-width: 7.5rem;
    padding: 0.65rem 0.75rem;
    border: 1px solid #d0d5dd;
    border-radius: 6px;
    background: {BRAND_WHITE};
}}
.pde-kpi-val {{
    font-size: 1.45rem;
    font-weight: 700;
    color: {BRAND_NAVY};
    line-height: 1.15;
}}
.pde-kpi-lab {{
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: {BRAND_NAVY};
    opacity: 0.7;
    margin-top: 0.2rem;
}}
.pde-kpi-help {{
    font-size: 0.7rem;
    color: {BRAND_NAVY_SOFT};
    opacity: 0.8;
    margin-top: 0.15rem;
}}
.pde-tools-label {{
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: {BRAND_NAVY};
    opacity: 0.65;
    margin-bottom: 0.25rem;
}}
</style>
        """,
        unsafe_allow_html=True,
    )


def mostrar_franja_contexto(ctx: ContextoAnalisis) -> None:
    """Chips Puerto | Escenario | Horizonte."""
    _inyectar_estilos_plantilla()
    st.markdown(
        f"""
<div class="pde-ctx">
  <div class="pde-ctx-chip"><span>Puerto</span><strong>{ctx.puerto}</strong></div>
  <div class="pde-ctx-chip"><span>Escenario</span><strong>{ctx.escenario}</strong></div>
  <div class="pde-ctx-chip"><span>Horizonte</span><strong>{ctx.horizonte}</strong></div>
</div>
        """,
        unsafe_allow_html=True,
    )


def mostrar_kpis(items: list[KpiItem]) -> None:
    """Fila de 3-4 metricas de decision."""
    if not items:
        return
    _inyectar_estilos_plantilla()
    celdas = []
    for item in items:
        ayuda = (
            f'<div class="pde-kpi-help">{item.ayuda}</div>' if item.ayuda else ""
        )
        celdas.append(
            f'<div class="pde-kpi">'
            f'<div class="pde-kpi-val">{item.valor}</div>'
            f'<div class="pde-kpi-lab">{item.etiqueta}</div>'
            f"{ayuda}</div>"
        )
    joined = "".join(celdas)
    st.markdown(
        f'<div class="pde-kpi-row">{joined}</div>',
        unsafe_allow_html=True,
    )


def mostrar_exportar(exports: list[ExportItem], *, key: str = "export") -> None:
    """Unico control Exportar que agrupa descargas CSV/Excel existentes."""
    if not exports:
        return
    _inyectar_estilos_plantilla()
    st.markdown('<div class="pde-tools-label">Herramientas</div>', unsafe_allow_html=True)
    with st.popover("Exportar", key=f"{key}_popover"):
        for item in exports:
            st.download_button(
                item.etiqueta,
                data=item.data,
                file_name=item.file_name,
                mime=item.mime,
                use_container_width=True,
                key=item.key,
            )


@contextmanager
def plantilla_pagina(
    titulo: str,
    descripcion: str = "",
    *,
    contexto: ContextoAnalisis | None = None,
    kpis: list[KpiItem] | None = None,
    accion_primaria: tuple[str, Callable[[], None]] | None = None,
    exports: list[ExportItem] | None = None,
    key_export: str = "export",
) -> Iterator[None]:
    """Cabecera de pagina estandar; el cuerpo va en el bloque with."""
    _inyectar_estilos_plantilla()

    if accion_primaria:
        c_tit, c_acc = st.columns([3.2, 1], vertical_alignment="bottom")
        with c_tit:
            st.subheader(titulo)
            if descripcion:
                st.markdown(
                    f'<p class="pde-page-desc">{descripcion}</p>',
                    unsafe_allow_html=True,
                )
        with c_acc:
            etiqueta, callback = accion_primaria
            if st.button(
                etiqueta,
                type="primary",
                use_container_width=True,
                key=f"{key_export}_cta",
            ):
                callback()
    else:
        st.subheader(titulo)
        if descripcion:
            st.markdown(
                f'<p class="pde-page-desc">{descripcion}</p>',
                unsafe_allow_html=True,
            )

    if contexto is not None:
        mostrar_franja_contexto(contexto)

    if kpis:
        mostrar_kpis(kpis)

    if exports:
        mostrar_exportar(exports, key=key_export)

    yield
