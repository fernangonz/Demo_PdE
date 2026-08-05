# -*- coding: utf-8 -*-
"""Fichas de modelo: inputs, outputs y ecuacion por motor de impacto.

Cada ficha documenta el contrato fisico/economico del motor para la UI
(resultado por IM) sin inventar formulas: solo lo que usa el codigo.
"""

from __future__ import annotations

from dataclasses import dataclass

from core.modelos.impacto.pi_agitacion.interpretacion import regla_variacion_cierre


@dataclass(frozen=True)
class CampoFicha:
    """Campo de entrada o salida de un modelo."""

    nombre: str
    simbolo: str = ""
    unidad: str = ""
    fuente: str = ""
    descripcion: str = ""


@dataclass(frozen=True)
class FichaModelo:
    """Contrato compacto de un motor (ecuacion + I/O)."""

    nombre: str
    motor_id: str
    familia: str
    tipo_impacto: str
    ecuacion: str
    inputs: tuple[CampoFicha, ...] = ()
    outputs: tuple[CampoFicha, ...] = ()
    regla_interpretacion: str = ""
    ecuacion_umbral: str = ""
    ecuacion_extra: str = ""
    notas: str = ""


_INPUTS_CALADO = (
    CampoFicha(
        nombre="Nivel del mar",
        simbolo="NM",
        unidad="m",
        fuente="Indicadores climaticos",
        descripcion="Valor del indicador NM por escenario",
    ),
    CampoFicha(
        nombre="Marea astronomica",
        simbolo="MA",
        unidad="m",
        fuente="Componentes de NM",
        descripcion="Componente de NM",
    ),
    CampoFicha(
        nombre="Marea meteorologica",
        simbolo="MM",
        unidad="m",
        fuente="Componentes de NM",
        descripcion="Componente de NM",
    ),
    CampoFicha(
        nombre="Sea level rise",
        simbolo="SLR",
        unidad="m",
        fuente="Componentes de NM",
        descripcion="Componente de NM",
    ),
    CampoFicha(
        nombre="Calado actual / referencia",
        simbolo="h_0",
        unidad="m",
        fuente="Indicadores climaticos",
        descripcion="Indicador h0 por escenario",
    ),
    CampoFicha(
        nombre="Espesor de sedimentacion",
        simbolo="h_{sed}",
        unidad="m",
        fuente="Indicadores climaticos",
        descripcion="Indicador h sedimentacion por escenario",
    ),
    CampoFicha(
        nombre="Calado del buque",
        simbolo="D_c",
        unidad="m",
        fuente="Configuracion del puerto",
        descripcion="Usado al evaluar formulaciones de umbral (p. ej. 1.1*Dc+0.75)",
    ),
    CampoFicha(
        nombre="Umbral de dragado",
        simbolo="U",
        unidad="m",
        fuente="Relacion umbrales y curvas de dano vs activos",
        descripcion="Numerico o formulacion con Dc",
    ),
)

_OUTPUTS_CALADO = (
    CampoFicha(
        nombre="Calado disponible",
        simbolo="h",
        unidad="m",
        descripcion="h = NM - h0 - h sedimentacion",
    ),
    CampoFicha(
        nombre="Interpretacion de dragado",
        simbolo="",
        unidad="",
        descripcion="Necesario / no necesario dragar segun umbral vs h",
    ),
)

_ECUACION_CALADO = r"h = NM - h_{0} - h_{\mathrm{sed}}"
_ECUACION_CALADO_NM = r"NM = MA + MM + SLR"
_UMBRAL_CALADO = r"U \le h \Rightarrow \mathrm{dragar};\quad U > h \Rightarrow \mathrm{no\ dragar}"
_REGLA_CALADO = (
    "Si umbral ≤ h → es necesario dragar; si umbral > h → no es necesario dragar."
)

FICHA_PI_CALADO_ELO = FichaModelo(
    nombre="PI FALTA DE CALADO",
    motor_id="PI_CALADO_ELO",
    familia="PI",
    tipo_impacto="ELO",
    ecuacion=_ECUACION_CALADO,
    ecuacion_extra=_ECUACION_CALADO_NM,
    ecuacion_umbral=_UMBRAL_CALADO,
    inputs=_INPUTS_CALADO,
    outputs=_OUTPUTS_CALADO,
    regla_interpretacion=_REGLA_CALADO,
    notas=(
        "Misma ecuacion fisica que OPEX/CAPEX; rol economico ELO -> PI. "
        "Prerrequisito de procedimiento: diagrama «PI FALTA DE CALADO» "
        "en Flujo de modelos/ (no es un modelo aparte; no reutilizar OPEX)."
    ),
)

FICHA_PI_CALADO_ELS = FichaModelo(
    nombre="OPEX FALTA DE CALADO",
    motor_id="PI_CALADO_ELS",
    familia="OPEX",
    tipo_impacto="ELS",
    ecuacion=_ECUACION_CALADO,
    ecuacion_extra=_ECUACION_CALADO_NM,
    ecuacion_umbral=_UMBRAL_CALADO,
    inputs=_INPUTS_CALADO,
    outputs=_OUTPUTS_CALADO,
    regla_interpretacion=_REGLA_CALADO,
    notas="Misma ecuacion fisica; rol economico ELS -> OPEX.",
)

FICHA_PI_CALADO_ELU = FichaModelo(
    nombre="CAPEX FALTA DE CALADO",
    motor_id="PI_CALADO_ELU",
    familia="CAPEX",
    tipo_impacto="ELU",
    ecuacion=_ECUACION_CALADO,
    ecuacion_extra=_ECUACION_CALADO_NM,
    ecuacion_umbral=_UMBRAL_CALADO,
    inputs=_INPUTS_CALADO,
    outputs=_OUTPUTS_CALADO,
    regla_interpretacion=_REGLA_CALADO,
    notas="Misma ecuacion fisica; rol economico ELU -> CAPEX.",
)

FICHA_PI_AGITACION = FichaModelo(
    nombre="PI SUPERACIÓN DE UMBRAL",
    motor_id="PI_AGITACION",
    familia="PI",
    tipo_impacto="ELO",
    ecuacion=r"\Delta = I_{\mathrm{esc}} - I_{\mathrm{hist}}",
    ecuacion_umbral=(
        r"\Delta > 0 \Rightarrow \mathrm{Empeora};\quad "
        r"\Delta < 0 \Rightarrow \mathrm{Mejora};\quad "
        r"\Delta = 0 \Rightarrow \mathrm{Sin\ cambios}"
    ),
    inputs=(
        CampoFicha(
            nombre="Umbral operativo",
            simbolo="U",
            unidad="(segun variable)",
            fuente="Relacion umbrales y curvas de dano vs activos",
            descripcion="Hs, viento, corriente o visibilidad segun modo",
        ),
        CampoFicha(
            nombre="Indicador climatico",
            simbolo="I",
            unidad="h/ano o d/ano",
            fuente="Indicadores climaticos",
            descripcion="Horas/dias de superacion del umbral (p. ej. Hs > U)",
        ),
        CampoFicha(
            nombre="Percentil / regla de seleccion",
            simbolo="",
            unidad="",
            fuente="Relacion_modelos_activos_e_indicadores o diagrama",
            descripcion="Paso 5b: Excel predefinido o umbral + P99 + filtros Tipo UO",
        ),
    ),
    outputs=(
        CampoFicha(
            nombre="Cambio respecto al hist\u00f3rico",
            simbolo=r"\Delta",
            unidad="h/ano o d/ano",
            descripcion="I_escenario - I_hist\u00f3rico",
        ),
        CampoFicha(
            nombre="Interpretaci\u00f3n",
            simbolo="",
            unidad="",
            descripcion="Empeora / Mejora / Sin cambios",
        ),
    ),
    # Motor compartido (oleaje→horas; viento/corriente/visibilidad→días):
    # la UI reescribe con regla_variacion_cierre(unidad) al mostrar el IM.
    regla_interpretacion=regla_variacion_cierre(None),
    notas="Motor compartido por Agitacion, Exceso de Oleaje y otras variables ELO.",
)

FICHA_PI_FRANCOBORDO = FichaModelo(
    nombre="PI FALTA DE FRANCOBORDO",
    motor_id="PI_FRANCOBORDO",
    familia="PI",
    tipo_impacto="ELO",
    ecuacion=r"\Delta = I_{\mathrm{esc}} - I_{\mathrm{hist}}",
    ecuacion_umbral=(
        r"\Delta > 0 \Rightarrow \mathrm{Empeora};\quad "
        r"\Delta < 0 \Rightarrow \mathrm{Mejora};\quad "
        r"\Delta = 0 \Rightarrow \mathrm{Sin\ cambios}"
    ),
    inputs=(
        CampoFicha(
            nombre="Francobordo del activo",
            simbolo="F_b",
            unidad="m",
            fuente="Configuracion del puerto",
            descripcion="Referencia de inundacion en atraque (o umbral Excel si no hay Fb)",
        ),
        CampoFicha(
            nombre="Indicador de inundacion",
            simbolo="I",
            unidad="d/ano",
            fuente="Indicadores climaticos",
            descripcion="Dias/ano con inundacion costera en atraque ≥ Fb (o umbral)",
        ),
        CampoFicha(
            nombre="Percentil / regla de seleccion",
            simbolo="",
            unidad="",
            fuente="Relacion_modelos_activos_e_indicadores o diagrama",
            descripcion="Paso 5b igual que superacion de umbral",
        ),
    ),
    outputs=(
        CampoFicha(
            nombre="Cambio respecto al hist\u00f3rico",
            simbolo=r"\Delta",
            unidad="d/ano",
            descripcion="I_escenario - I_hist\u00f3rico",
        ),
        CampoFicha(
            nombre="Interpretaci\u00f3n",
            simbolo="",
            unidad="",
            descripcion="Empeora / Mejora / Sin cambios",
        ),
    ),
    regla_interpretacion=(
        "Variación > 0 → Empeora; < 0 → Mejora; = 0 → sin cambios "
        "(días de inundación en atraque)."
    ),
)

FICHA_PI_PRECIPITACION = FichaModelo(
    nombre="PI EXCESO DE PRECIPITACIÓN",
    motor_id="PI_PRECIPITACION",
    familia="PI",
    tipo_impacto="ELO",
    ecuacion=r"\Delta_i = I_{i,\mathrm{esc}} - I_{i,\mathrm{hist}}",
    ecuacion_umbral=(
        r"\Delta_i > 0 \Rightarrow \mathrm{no\ mejora};\quad "
        r"\Delta_i < 0 \Rightarrow \mathrm{Mejora};\quad "
        r"\Delta_i = 0 \Rightarrow \mathrm{Sin\ cambios}"
    ),
    inputs=(
        CampoFicha(
            nombre="Indicadores predefinidos (1 o 2)",
            simbolo="I_1[, I_2]",
            unidad="d/ano",
            fuente="Relacion_modelos_activos_e_indicadores (Excel 4)",
            descripcion="Selección indicador = Predefinido; sin búsqueda de umbral",
        ),
        CampoFicha(
            nombre="Percentil",
            simbolo="",
            unidad="",
            fuente="Relacion_modelos_activos_e_indicadores",
            descripcion="Paso 5b: percentil de la fila Excel 4",
        ),
    ),
    outputs=(
        CampoFicha(
            nombre=(
                "Cambio respecto al hist\u00f3rico / Interpretaci\u00f3n "
                "(con umbral mm si hay 2 indicadores)"
            ),
            simbolo=r"\Delta_i",
            unidad="d/ano",
            descripcion=(
                "Futuro \u2212 hist\u00f3rico por indicador; con 1 indicador "
                "cabeceras sin sufijo; con 2, umbral mm (p. ej. 1 mm, 20 mm); "
                "Mejora / no mejora / Sin cambios"
            ),
        ),
    ),
    regla_interpretacion=(
        "Por cada indicador (misma polaridad que PI agitaci\u00f3n): "
        "\u0394 > 0 \u2192 no mejora; \u0394 < 0 \u2192 Mejora; \u0394 = 0 \u2192 Sin cambios."
    ),
    notas="Sin umbral. Excel 4 define 1 o 2 indicadores predefinidos.",
)


FICHAS_POR_MOTOR: dict[str, FichaModelo] = {
    f.motor_id: f
    for f in (
        FICHA_PI_CALADO_ELO,
        FICHA_PI_CALADO_ELS,
        FICHA_PI_CALADO_ELU,
        FICHA_PI_AGITACION,
        FICHA_PI_FRANCOBORDO,
        FICHA_PI_PRECIPITACION,
    )
}


def ficha_por_motor(motor_id: str | None) -> FichaModelo | None:
    """Resuelve ficha por motor_id exacto."""
    if not motor_id:
        return None
    return FICHAS_POR_MOTOR.get(str(motor_id).strip())


def nombre_motor_display(
    motor_id: str | None = None,
    *,
    familia: str | None = None,
    tipo_impacto: str | None = None,
    modo_fallo: str | None = None,
    titulo: str | None = None,
    fallback: str = "",
) -> str:
    """Nombre humano del motor para UI (diagnóstico / cabecera IM)."""
    from core.modelos.catalogo_impactos import titulo_modo_display

    ficha = resolver_ficha(
        motor_id=motor_id,
        familia=familia,
        tipo_impacto=tipo_impacto,
        modo_fallo=modo_fallo,
        titulo=titulo,
    )
    if ficha is not None:
        return titulo_modo_display(ficha.nombre)
    return titulo_modo_display((fallback or motor_id or "").strip())


def resolver_ficha(
    *,
    motor_id: str | None = None,
    familia: str | None = None,
    tipo_impacto: str | None = None,
    modo_fallo: str | None = None,
    titulo: str | None = None,
) -> FichaModelo | None:
    """Resuelve ficha desde motor / familia / modo (UI de resultados)."""
    ficha = ficha_por_motor(motor_id)
    if ficha is not None:
        return ficha

    texto = " ".join(
        x for x in (modo_fallo or "", titulo or "", familia or "") if x
    ).lower()
    tipo = (tipo_impacto or "").strip().upper()
    fam = (familia or "").strip().upper()

    if "calado" in texto:
        if tipo == "ELU" or fam == "CAPEX":
            return FICHA_PI_CALADO_ELU
        if tipo == "ELS" or fam == "OPEX":
            return FICHA_PI_CALADO_ELS
        return FICHA_PI_CALADO_ELO

    if "francobordo" in texto:
        return FICHA_PI_FRANCOBORDO

    if "precipit" in texto:
        return FICHA_PI_PRECIPITACION

    if any(
        k in texto
        for k in ("agitaci", "oleaje", "viento", "corriente", "visibilidad", "superaci")
    ):
        return FICHA_PI_AGITACION

    if fam == "CAPEX" and tipo == "ELU":
        return FICHA_PI_CALADO_ELU
    if fam == "OPEX" and tipo == "ELS":
        return FICHA_PI_CALADO_ELS

    return None


__all__ = [
    "CampoFicha",
    "FichaModelo",
    "FICHAS_POR_MOTOR",
    "FICHA_PI_CALADO_ELO",
    "FICHA_PI_CALADO_ELS",
    "FICHA_PI_CALADO_ELU",
    "FICHA_PI_AGITACION",
    "FICHA_PI_FRANCOBORDO",
    "FICHA_PI_PRECIPITACION",
    "ficha_por_motor",
    "nombre_motor_display",
    "resolver_ficha",
]
