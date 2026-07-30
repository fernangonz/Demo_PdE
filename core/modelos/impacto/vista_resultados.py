"""Organización de resultados: CP (activo) → IM (modos de fallo)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.impact_models import ResumenIteracion


@dataclass
class GrupoPasosIM:
    """Pasos 5+ de una iteración IM (modo de fallo)."""

    titulo: str
    modo_fallo: str
    pasos: list[Any] = field(default_factory=list)
    estado: str = "ok"
    motivo: str | None = None
    error_code: str | None = None
    familia: str = ""
    motor_id: str = ""
    nombre_motor: str = ""
    tipo_impacto: str = ""


@dataclass
class VistaResultadosActivo:
    """Resultados agrupados por activo (CP) y modos de fallo (IM)."""

    activo: str
    tipo_uo: str
    cp_numero: int
    cp_total: int
    pasos_comunes: list[Any]
    modos: list[GrupoPasosIM]
    iteraciones: list[ResumenIteracion]
    resumen_activo: Any | None = None
    diagnostico: list[dict[str, Any]] = field(default_factory=list)


def pasos_comunes_desde_lista(pasos: list[Any]) -> list[Any]:
    """Pasos 3–4 compartidos por el activo (config + impactos)."""
    return [p for p in pasos if getattr(p, "numero", 99) <= 4]


def _modo_fallo_desde_paso(paso: Any) -> str | None:
    for tabla in getattr(paso, "tablas", []):
        for fila in tabla.filas:
            for key in (
                "Modo de fallo / Modo de parada",
                "Modos de fallo / Modos de parada",
            ):
                if key in fila and fila[key]:
                    return str(fila[key]).strip()
    return None


def agrupar_pasos_por_im(pasos: list[Any]) -> list[GrupoPasosIM]:
    """Agrupa pasos 5+ por iteración IM."""
    grupos: list[GrupoPasosIM] = []
    actual: GrupoPasosIM | None = None

    for paso in pasos:
        numero = getattr(paso, "numero", 0)
        nombre = str(getattr(paso, "nombre", ""))
        if numero <= 4:
            continue
        if numero == 5 and "IM=" in nombre:
            if actual is not None:
                grupos.append(actual)
            modo = _modo_fallo_desde_paso(paso) or nombre
            actual = GrupoPasosIM(
                titulo=nombre,
                modo_fallo=modo,
                pasos=[paso],
            )
        elif actual is not None:
            actual.pasos.append(paso)

    if actual is not None:
        grupos.append(actual)
    return grupos


def _meta_activo(resultado) -> tuple[str, str]:
    meta: dict[str, Any] = {}
    if getattr(resultado, "resultado_agitacion", None) and resultado.resultado_agitacion.ok:
        meta.update(resultado.resultado_agitacion.metadatos_ejecucion)
    if getattr(resultado, "resultado_calado_pi", None):
        cal = resultado.resultado_calado_pi.metadatos_ejecucion
        meta.setdefault("activo", cal.get("activo", ""))
        meta.setdefault("tipo_uo", cal.get("tipo_uo", ""))
    if getattr(resultado, "resultado_calado", None) and resultado.resultado_calado.ok:
        cal = resultado.resultado_calado.metadatos_ejecucion
        meta.setdefault("activo", cal.get("activo", ""))
        meta.setdefault("tipo_uo", cal.get("tipo_uo", ""))
    if getattr(resultado, "resultado_calado_opex", None):
        cal = resultado.resultado_calado_opex.metadatos_ejecucion
        meta.setdefault("activo", cal.get("activo", ""))
        meta.setdefault("tipo_uo", cal.get("tipo_uo", ""))
    if getattr(resultado, "resultado_calado_capex", None):
        cal = resultado.resultado_calado_capex.metadatos_ejecucion
        meta.setdefault("activo", cal.get("activo", ""))
        meta.setdefault("tipo_uo", cal.get("tipo_uo", ""))
    if getattr(resultado, "resultado_francobordo", None) and resultado.resultado_francobordo.ok:
        fb = resultado.resultado_francobordo.metadatos_ejecucion
        meta.setdefault("activo", fb.get("activo", ""))
        meta.setdefault("tipo_uo", fb.get("tipo_uo", ""))
    return str(meta.get("activo", "")), str(meta.get("tipo_uo", ""))


def _grupo_desde_iteracion(it: ResumenIteracion, pasos_fallback: list[Any] | None = None) -> GrupoPasosIM:
    pasos = list(getattr(it, "pasos", None) or [])
    if not pasos and pasos_fallback:
        pasos = list(pasos_fallback)
    return GrupoPasosIM(
        titulo=f"IM — {it.modo_fallo}",
        modo_fallo=it.modo_fallo,
        pasos=pasos,
        estado=getattr(it, "estado", "ok") or "ok",
        motivo=getattr(it, "motivo", None),
        error_code=getattr(it, "error_code", None),
        familia=getattr(it, "familia", "") or "",
        motor_id=getattr(it, "motor_id", "") or "",
        nombre_motor=getattr(it, "nombre_motor", "") or "",
        tipo_impacto=getattr(it, "tipo_impacto", "") or "",
    )


def _grupos_im_por_modo(
    grupos_agitacion: list[GrupoPasosIM],
    grupos_calado: list[GrupoPasosIM],
    grupos_francobordo: list[GrupoPasosIM],
    iteraciones: list[ResumenIteracion],
) -> list[GrupoPasosIM]:
    """Une pasos IM siguiendo el orden de iteraciones; prioriza pasos embebidos."""
    por_modo_agit: dict[str, GrupoPasosIM] = {
        g.modo_fallo: g for g in grupos_agitacion
    }
    por_modo_cal: dict[str, GrupoPasosIM] = {
        g.modo_fallo: g for g in grupos_calado
    }
    por_modo_fb: dict[str, GrupoPasosIM] = {
        g.modo_fallo: g for g in grupos_francobordo
    }
    vistos: set[str] = set()
    ordenados: list[GrupoPasosIM] = []

    for it in iteraciones:
        modo = it.modo_fallo
        if modo in vistos:
            continue
        vistos.add(modo)
        pasos_it = list(getattr(it, "pasos", None) or [])
        if pasos_it or getattr(it, "estado", "ok") != "ok":
            fallback = None
            if modo in por_modo_cal:
                fallback = por_modo_cal[modo].pasos
            elif modo in por_modo_fb:
                fallback = por_modo_fb[modo].pasos
            elif modo in por_modo_agit:
                fallback = por_modo_agit[modo].pasos
            ordenados.append(_grupo_desde_iteracion(it, fallback))
            continue
        if modo in por_modo_cal:
            ordenados.append(por_modo_cal[modo])
        elif modo in por_modo_fb:
            ordenados.append(por_modo_fb[modo])
        elif modo in por_modo_agit:
            ordenados.append(por_modo_agit[modo])

    for g in grupos_agitacion + grupos_francobordo + grupos_calado:
        if g.modo_fallo not in vistos:
            ordenados.append(g)
    return ordenados


def _diagnostico_desde_iteraciones(iteraciones: list[ResumenIteracion]) -> list[dict[str, Any]]:
    from core.modelos.fichas_modelo import nombre_motor_display

    filas: list[dict[str, Any]] = []
    for it in iteraciones:
        motor_id = getattr(it, "motor_id", "") or ""
        familia = getattr(it, "familia", "") or ""
        tipo = getattr(it, "tipo_impacto", "") or ""
        nombre = getattr(it, "nombre_motor", "") or ""
        if not nombre:
            nombre = nombre_motor_display(
                motor_id,
                familia=familia,
                tipo_impacto=tipo,
                modo_fallo=it.modo_fallo,
            )
        filas.append({
            "Modo": it.modo_fallo,
            "Estado": getattr(it, "estado", "ok") or "ok",
            "Familia": familia,
            "Tipo": tipo,
            "Motor": nombre,
            "Motivo": getattr(it, "motivo", None) or "",
            "Código": getattr(it, "error_code", None) or "",
        })
    return filas


def construir_vista_resultados_activo(
    resultado,
    *,
    iteraciones: list[ResumenIteracion],
    resumen_activo=None,
    cp_numero: int = 1,
    cp_total: int = 1,
) -> VistaResultadosActivo | None:
    """Construye vista CP → IM a partir del cálculo del activo."""
    if not iteraciones:
        return None

    activo, tipo_uo = _meta_activo(resultado)
    if not activo:
        activo = iteraciones[0].activo
    if not tipo_uo:
        tipo_uo = iteraciones[0].tipo_uo

    pasos_ag: list[Any] = []
    pasos_fb: list[Any] = []
    pasos_cal_im: list[Any] = []
    pasos_cal_comunes: list[Any] = []
    if getattr(resultado, "resultado_agitacion", None) and resultado.resultado_agitacion.ok:
        rp = resultado.resultado_agitacion.resultados_por_pasos
        if rp is not None:
            pasos_ag = list(rp.pasos)

    if getattr(resultado, "resultado_francobordo", None) and resultado.resultado_francobordo.ok:
        rp_fb = resultado.resultado_francobordo.resultados_por_pasos
        if rp_fb is not None:
            pasos_fb = list(rp_fb.pasos)

    calado_resultados = []
    for attr in ("resultado_calado_pi", "resultado_calado_opex", "resultado_calado_capex"):
        res = getattr(resultado, attr, None)
        if res is None:
            continue
        if res.ok or getattr(res, "ejecuciones", None):
            calado_resultados.append(res)

    for res_cal in calado_resultados:
        rp = res_cal.resultados_por_pasos
        if rp is None:
            continue
        pasos_lista = list(rp.pasos)
        pasos_cal_comunes.extend(pasos_comunes_desde_lista(pasos_lista))
        pasos_cal_im.extend(
            p for p in pasos_lista if getattr(p, "numero", 0) > 4
        )

    pasos_cal = pasos_cal_im
    comunes = pasos_comunes_desde_lista(pasos_ag) + pasos_comunes_desde_lista(pasos_fb) + pasos_cal_comunes
    modos = _grupos_im_por_modo(
        agrupar_pasos_por_im(pasos_ag),
        agrupar_pasos_por_im(pasos_cal),
        agrupar_pasos_por_im(pasos_fb),
        iteraciones,
    )

    return VistaResultadosActivo(
        activo=activo,
        tipo_uo=tipo_uo,
        cp_numero=cp_numero,
        cp_total=cp_total,
        pasos_comunes=comunes,
        modos=modos,
        iteraciones=iteraciones,
        resumen_activo=resumen_activo,
        diagnostico=_diagnostico_desde_iteraciones(iteraciones),
    )


def listar_activos_config(config_df) -> list[str]:
    """Activos únicos en Configuración del puerto (orden del Excel)."""
    from core.modelos.impacto.pi_agitacion.utilidades import columna_por_patron

    if config_df is None or config_df.empty:
        return []
    col = columna_por_patron(
        list(config_df.columns),
        "activo fisico u operacional",
        "activo",
    )
    if not col:
        return []
    vistos: set[str] = set()
    activos: list[str] = []
    for valor in config_df[col].dropna():
        texto = str(valor).strip()
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        activos.append(texto)
    return activos
