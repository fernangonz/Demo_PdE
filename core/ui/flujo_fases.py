"""Barra de progreso del flujo de análisis (Puerto → Resultados).

Estados heurísticos a partir de session_state y datos disponibles.
No inventa resultados: solo refleja configuración y cálculo existentes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

import streamlit as st

from core.branding import BRAND_NAVY, BRAND_NAVY_SOFT, BRAND_WHITE


class EstadoFase(str, Enum):
    COMPLETADO = "completado"
    ADVERTENCIAS = "advertencias"
    PENDIENTE = "pendiente"
    BLOQUEADO = "bloqueado"


@dataclass(frozen=True)
class FaseFlujo:
    id: str
    numero: int
    etiqueta: str
    estado: EstadoFase
    detalle: str = ""


_COLORES = {
    EstadoFase.COMPLETADO: ("#1b7a4a", "#e8f5ee"),
    EstadoFase.ADVERTENCIAS: ("#8a6d1d", "#f7f1de"),
    EstadoFase.PENDIENTE: (BRAND_NAVY, "#e8ebf2"),
    EstadoFase.BLOQUEADO: ("#6b7280", "#f0f1f4"),
}

_ETIQUETAS_ESTADO = {
    EstadoFase.COMPLETADO: "Completado",
    EstadoFase.ADVERTENCIAS: "Con advertencias",
    EstadoFase.PENDIENTE: "Pendiente",
    EstadoFase.BLOQUEADO: "Bloqueado",
}


def puerto_seleccionado() -> str | None:
    """Puerto concreto en sesión, o None si es 'Todos' / vacío."""
    puerto = st.session_state.get("puerto_sel")
    if not puerto or puerto == "Todos los puertos":
        return None
    return str(puerto)


def hay_resultado_calculo() -> bool:
    res = st.session_state.get("resultado_calculo_puerto")
    if res is not None and getattr(res, "ok", False):
        return True
    res_act = st.session_state.get("resultado_calculo_activo")
    return bool(res_act is not None and getattr(res_act, "ok", False))


def derivar_fases(
    *,
    excel_ok: bool,
    config_presente: bool,
    n_activos: int,
    n_impactos: int,
    clima_ok: bool,
    validacion_errores: int = 0,
    validacion_avisos: int = 0,
) -> list[FaseFlujo]:
    """Deriva el estado de las 5 fases del flujo."""
    puerto_ok = puerto_seleccionado() is not None
    calculo_ok = hay_resultado_calculo()

    if puerto_ok:
        f1 = EstadoFase.COMPLETADO
        d1 = puerto_seleccionado() or ""
    else:
        f1 = EstadoFase.PENDIENTE
        d1 = "Selecciona un puerto"

    if not excel_ok:
        f2 = EstadoFase.ADVERTENCIAS if config_presente else EstadoFase.PENDIENTE
        d2 = "Revisa fuentes Excel"
    else:
        f2 = EstadoFase.COMPLETADO
        d2 = "Fuentes disponibles"

    if not puerto_ok:
        f3 = EstadoFase.BLOQUEADO
        d3 = "Requiere puerto"
    elif config_presente and n_activos > 0:
        if validacion_errores:
            f3 = EstadoFase.ADVERTENCIAS
            d3 = f"{n_activos} activos · {validacion_errores} error(es)"
        elif validacion_avisos:
            f3 = EstadoFase.ADVERTENCIAS
            d3 = f"{n_activos} activos · {validacion_avisos} aviso(s)"
        else:
            f3 = EstadoFase.COMPLETADO
            d3 = f"{n_activos} activos · {n_impactos} impactos"
    elif config_presente:
        f3 = EstadoFase.ADVERTENCIAS
        d3 = "Configuración sin activos"
    else:
        f3 = EstadoFase.PENDIENTE
        d3 = "Carga configuración del puerto"

    if not puerto_ok or not config_presente or n_activos == 0:
        f4 = EstadoFase.BLOQUEADO
        d4 = "Completa fases anteriores"
    elif not clima_ok:
        f4 = EstadoFase.ADVERTENCIAS
        d4 = "Clima no disponible"
    elif calculo_ok:
        f4 = EstadoFase.COMPLETADO
        d4 = "Cálculo en sesión"
    else:
        f4 = EstadoFase.PENDIENTE
        d4 = "Pendiente de ejecutar"

    if calculo_ok:
        f5 = EstadoFase.COMPLETADO
        d5 = "Disponibles en Resultados"
    elif f4 == EstadoFase.BLOQUEADO:
        f5 = EstadoFase.BLOQUEADO
        d5 = "Requiere cálculo"
    else:
        f5 = EstadoFase.PENDIENTE
        d5 = "Sin resultados aún"

    return [
        FaseFlujo("puerto", 1, "Puerto", f1, d1),
        FaseFlujo("datos", 2, "Datos", f2, d2),
        FaseFlujo("configuracion", 3, "Configuración", f3, d3),
        FaseFlujo("calculo", 4, "Cálculo", f4, d4),
        FaseFlujo("resultados", 5, "Resultados", f5, d5),
    ]


def siguiente_fase_incompleta(fases: list[FaseFlujo]) -> FaseFlujo | None:
    """Primera fase no completada (pendiente / advertencias / bloqueado)."""
    for fase in fases:
        if fase.estado != EstadoFase.COMPLETADO:
            return fase
    return None


def vista_para_fase(fase_id: str) -> str:
    """Mapea id de fase a clave de vista de navegación."""
    return {
        "puerto": "Puertos",
        "datos": "__fuentes__",
        "configuracion": "Configuración del puerto",
        "calculo": "Cálculo de impactos",
        "resultados": "__resultados__",
    }.get(fase_id, "Puertos")


def mostrar_barra_progreso(
    fases: list[FaseFlujo],
    *,
    ir_a_vista: Callable[[str], None] | None = None,
) -> None:
    """Renderiza la barra de fases del flujo (clicable si se pasa ir_a_vista)."""
    st.markdown(
        f"""
<style>
.pde-flujo {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin: 0.35rem 0 1rem 0;
    padding: 0.55rem 0.65rem;
    background: #f4f5f8;
    border: 1px solid #d5dae3;
    border-radius: 6px;
}}
.pde-flujo-paso {{
    flex: 1 1 7.5rem;
    min-width: 7rem;
    padding: 0.45rem 0.55rem;
    border-radius: 4px;
    border-left: 3px solid {BRAND_NAVY};
    background: {BRAND_WHITE};
}}
.pde-flujo-num {{
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: {BRAND_NAVY};
    opacity: 0.75;
}}
.pde-flujo-estado {{
    font-size: 0.72rem;
    font-weight: 600;
}}
.pde-flujo-det {{
    font-size: 0.7rem;
    color: {BRAND_NAVY_SOFT};
    opacity: 0.85;
    margin-top: 0.15rem;
}}
</style>
        """,
        unsafe_allow_html=True,
    )

    chips = []
    for fase in fases:
        color, bg = _COLORES[fase.estado]
        estado_txt = _ETIQUETAS_ESTADO[fase.estado]
        chips.append(
            f'<div class="pde-flujo-paso" style="border-left-color:{color};background:{bg};">'
            f'<div class="pde-flujo-num">{fase.numero} · {fase.etiqueta}</div>'
            f'<div class="pde-flujo-estado" style="color:{color};">{estado_txt}</div>'
            f'<div class="pde-flujo-det">{fase.detalle}</div>'
            f"</div>"
        )
    st.markdown(
        f'<div class="pde-flujo">{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )

    if ir_a_vista is not None:
        cols = st.columns(len(fases))
        for col, fase in zip(cols, fases):
            with col:
                if st.button(
                    f"Ir a {fase.etiqueta}",
                    key=f"flujo_ir_{fase.id}",
                    use_container_width=True,
                    disabled=fase.estado == EstadoFase.BLOQUEADO,
                ):
                    ir_a_vista(vista_para_fase(fase.id))
