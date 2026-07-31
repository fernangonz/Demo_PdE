"""Catálogo de modelos de impacto por modo de fallo y esquema de cálculo por activo."""

from __future__ import annotations

from dataclasses import dataclass

from core.modelos.inputs_activo import IDS_MODOS_FALTA_CALADO
from core.modelos.impacto.pi_agitacion.utilidades import match_modo_fallo_superacion

MOTOR_PI_SUPERACION = "PI_AGITACION"
MOTOR_PI_FRANCOBORDO = "PI_FRANCOBORDO"
MOTOR_PI_CALADO_ELO = "PI_CALADO_ELO"
MOTOR_PI_CALADO_ELS = "PI_CALADO_ELS"
MOTOR_PI_CALADO_ELU = "PI_CALADO_ELU"
MOTOR_PI_CALADO = MOTOR_PI_CALADO_ELS


@dataclass(frozen=True)
class EntradaCatalogoImpacto:
    """Un modo de fallo y el modelo de impacto que lo evalúa."""

    id: str
    familia: str
    modo_fallo: str
    variable: str
    tipo_impacto: str
    motor_id: str
    motor_nombre: str
    implementado: bool
    requiere_inputs_ui: bool
    descripcion: str
    diagrama_modelo_id: str | None = None
    notas_inputs: str = ""


@dataclass(frozen=True)
class MotorCalculoActivo:
    """Motor unificado que escala el cálculo desde el activo."""

    id: str
    nombre: str
    descripcion: str


MOTOR_ACTIVO = MotorCalculoActivo(
    id="CALCULO_ACTIVO",
    nombre="Cálculo de impactos por activo",
    descripcion=(
        "Un solo cálculo parte del activo configurado, recorre los modos de fallo "
        "implementados y genera resultados por iteración y resumen consolidado del activo."
    ),
)

CATALOGO_MODOS_IMPACTO: tuple[EntradaCatalogoImpacto, ...] = (
    EntradaCatalogoImpacto(
        id="agitacion_oleaje",
        familia="PI",
        modo_fallo="Agitación",
        variable="Oleaje",
        tipo_impacto="ELO",
        motor_id=MOTOR_PI_SUPERACION,
        motor_nombre="PI SUPERACIÓN DE UMBRAL",
        implementado=True,
        requiere_inputs_ui=False,
        diagrama_modelo_id=MOTOR_PI_SUPERACION,
        descripcion=(
            "Misma cadena PI superación de umbral que Exceso de Oleaje; "
            "modo «Agitación» en el Excel de relación impactos."
        ),
        notas_inputs="Automático: Excel de relación modelos, umbrales e indicadores.",
    ),
    EntradaCatalogoImpacto(
        id="exceso_oleaje",
        familia="PI",
        modo_fallo="Exceso de Oleaje",
        variable="Oleaje",
        tipo_impacto="ELO",
        motor_id=MOTOR_PI_SUPERACION,
        motor_nombre="PI SUPERACIÓN DE UMBRAL",
        implementado=True,
        requiere_inputs_ui=False,
        diagrama_modelo_id=MOTOR_PI_SUPERACION,
        descripcion=(
            "Iteración IM dentro del cálculo del activo. Percentil e indicador "
            "desde Excel de relación modelos (paso 5b) o diagrama (umbral + P99). "
            "Tipo ELO = interrupción operativa / PI."
        ),
        notas_inputs="Automático: Excel de relación modelos, umbrales e indicadores.",
    ),
    EntradaCatalogoImpacto(
        id="exceso_viento",
        familia="PI",
        modo_fallo="Exceso de Viento",
        variable="Viento",
        tipo_impacto="ELO",
        motor_id=MOTOR_PI_SUPERACION,
        motor_nombre="PI SUPERACIÓN DE UMBRAL",
        implementado=True,
        requiere_inputs_ui=False,
        diagrama_modelo_id=MOTOR_PI_SUPERACION,
        descripcion=(
            "Misma cadena PI superación de umbral; indicador predefinido en Excel "
            "cuando aplica (ELO + viento)."
        ),
        notas_inputs="Automático: Excel de relación modelos e indicadores climáticos.",
    ),
    EntradaCatalogoImpacto(
        id="exceso_corriente",
        familia="PI",
        modo_fallo="Exceso de Corriente",
        variable="Corriente",
        tipo_impacto="ELO",
        motor_id=MOTOR_PI_SUPERACION,
        motor_nombre="PI SUPERACIÓN DE UMBRAL",
        implementado=True,
        requiere_inputs_ui=False,
        diagrama_modelo_id=MOTOR_PI_SUPERACION,
        descripcion=(
            "Misma cadena PI superación de umbral (pasos 5b–8); umbral en hoja Corriente "
            "e indicador predefinido o por umbral (días/año con V > umbral)."
        ),
        notas_inputs="Automático: Excel de relación modelos, umbrales e indicadores.",
    ),
    EntradaCatalogoImpacto(
        id="visibilidad_reducida",
        familia="PI",
        modo_fallo="Visibilidad reducida",
        variable="Visibilidad",
        tipo_impacto="ELO",
        motor_id=MOTOR_PI_SUPERACION,
        motor_nombre="PI SUPERACIÓN DE UMBRAL",
        implementado=True,
        requiere_inputs_ui=False,
        diagrama_modelo_id=MOTOR_PI_SUPERACION,
        descripcion=(
            "Misma cadena PI superación de umbral (pasos 5b–8); umbral en hoja Visibilidad "
            "e indicador predefinido o por umbral (días/año con visibilidad reducida)."
        ),
        notas_inputs="Automático: Excel de relación modelos, umbrales e indicadores.",
    ),
    EntradaCatalogoImpacto(
        id="falta_francobordo_elo",
        familia="PI",
        modo_fallo="Falta de francobordo",
        variable="Nivel del mar",
        tipo_impacto="ELO",
        motor_id=MOTOR_PI_FRANCOBORDO,
        motor_nombre="PI FALTA DE FRANCOBORDO",
        implementado=True,
        requiere_inputs_ui=False,
        diagrama_modelo_id=MOTOR_PI_FRANCOBORDO,
        descripcion=(
            "Referencia Fb o umbral; indicador de inundacion costera en un atraque "
            "con valor ≥ referencia; variacion por escenario."
        ),
        notas_inputs=(
            "Fb (m) opcional en Configuracion del puerto; si esta vacio se usa umbral."
        ),
    ),
    EntradaCatalogoImpacto(
        id="falta_calado_elo",
        familia="PI",
        modo_fallo="Falta de Calado",
        variable="Nivel del mar",
        tipo_impacto="ELO",
        motor_id=MOTOR_PI_CALADO_ELO,
        motor_nombre="PI FALTA DE CALADO",
        implementado=False,
        requiere_inputs_ui=False,
        diagrama_modelo_id=MOTOR_PI_CALADO_ELO,
        descripcion=(
            "Metodologia no definida: falta el diagrama "
            "«PI FALTA DE CALADO» en Flujo de modelos. "
            "No calcular ni exigir indicadores hasta definir el procedimiento."
        ),
        notas_inputs=(
            "Pendiente de metodologia. No usar inputs de OPEX/CAPEX como sustituto."
        ),
    ),
    EntradaCatalogoImpacto(
        id="falta_calado_els",
        familia="OPEX",
        modo_fallo="Falta de Calado",
        variable="Nivel del mar",
        tipo_impacto="ELS",
        motor_id=MOTOR_PI_CALADO_ELS,
        motor_nombre="OPEX FALTA DE CALADO",
        implementado=True,
        requiere_inputs_ui=False,
        diagrama_modelo_id=MOTOR_PI_CALADO_ELS,
        descripcion=(
            "h = NM - h0 - h sedimentacion. Solo filas IM con tipo ELS "
            "(limitacion operativa / OPEX)."
        ),
        notas_inputs=(
            "Calado del buque Dc (m) del activo en Configuracion del puerto."
        ),
    ),
    EntradaCatalogoImpacto(
        id="falta_calado_elu",
        familia="CAPEX",
        modo_fallo="Falta de Calado",
        variable="Nivel del mar",
        tipo_impacto="ELU",
        motor_id=MOTOR_PI_CALADO_ELU,
        motor_nombre="CAPEX FALTA DE CALADO",
        implementado=True,
        requiere_inputs_ui=False,
        diagrama_modelo_id=MOTOR_PI_CALADO_ELU,
        descripcion=(
            "h = NM - h0 - h sedimentacion. Solo filas IM con tipo ELU "
            "(fallo / CAPEX)."
        ),
        notas_inputs=(
            "Mismo Calado del buque Dc (m) del activo (Configuracion del puerto)."
        ),
    ),
)


_PREFIXES_MODO_DISPLAY = frozenset({"PI", "OPEX", "CAPEX"})


def titulo_modo_display(texto: str) -> str:
    """Capitalización UI: prefijo PI/OPEX/CAPEX en mayúsculas + resto tipo frase.

    Ej.: «PI FALTA DE CALADO» → «PI Falta de calado»;
    «PI Exceso de Oleaje» → «PI Exceso de oleaje».
    """
    raw = (texto or "").strip()
    if not raw:
        return raw
    partes = raw.split(None, 1)
    prefijo = partes[0].upper()
    if prefijo not in _PREFIXES_MODO_DISPLAY:
        return raw
    if len(partes) == 1:
        return prefijo
    return f"{prefijo} {partes[1].strip().capitalize()}"


def titulo_modo_impacto(entrada: EntradaCatalogoImpacto) -> str:
    """Etiqueta visible: familia + modo de fallo (p. ej. «PI Exceso de oleaje»)."""
    return titulo_modo_display(f"{entrada.familia} {entrada.modo_fallo}")


def es_modo_falta_calado(entrada_id: str) -> bool:
    return entrada_id in IDS_MODOS_FALTA_CALADO


def primera_entrada_calado_implementada() -> EntradaCatalogoImpacto | None:
    """Primera tarjeta de calado del catálogo (Dc desde Configuración del puerto)."""
    for entrada in CATALOGO_MODOS_IMPACTO:
        if es_modo_falta_calado(entrada.id) and entrada.implementado:
            return entrada
    return None


def entrada_catalogo(
    *,
    modo_fallo: str,
    variable: str | None = None,
    tipo_impacto: str | None = None,
    motor_id: str | None = None,
) -> EntradaCatalogoImpacto | None:
    for entrada in CATALOGO_MODOS_IMPACTO:
        if entrada.modo_fallo != modo_fallo:
            continue
        if variable is not None and entrada.variable != variable:
            continue
        if tipo_impacto is not None and entrada.tipo_impacto != tipo_impacto:
            continue
        if motor_id is not None and entrada.motor_id != motor_id:
            continue
        return entrada
    return None


def titulo_desde_modo(
    modo_fallo: str,
    *,
    variable: str | None = None,
    tipo_impacto: str | None = None,
) -> str:
    entrada = None
    if tipo_impacto:
        entrada = entrada_catalogo(
            modo_fallo=modo_fallo,
            variable=variable,
            tipo_impacto=tipo_impacto,
        )
    if entrada is None:
        candidatos = [
            e for e in CATALOGO_MODOS_IMPACTO
            if e.modo_fallo == modo_fallo
        ]
        if variable:
            candidatos = [e for e in candidatos if e.variable == variable]
        if not candidatos and variable:
            candidatos = [
                e
                for e in CATALOGO_MODOS_IMPACTO
                if e.variable == variable
                and match_modo_fallo_superacion(
                    e.modo_fallo,
                    modo_fallo,
                    variable,
                    tipo_impacto=tipo_impacto,
                )
            ]
        if len(candidatos) == 1:
            entrada = candidatos[0]
        elif tipo_impacto and candidatos:
            entrada = next(
                (e for e in candidatos if e.tipo_impacto == tipo_impacto),
                None,
            )
    if entrada is None:
        return modo_fallo
    return titulo_modo_impacto(entrada)


def modos_implementados() -> list[EntradaCatalogoImpacto]:
    return [e for e in CATALOGO_MODOS_IMPACTO if e.implementado]


def mermaid_esquema_calculo_activo(*, activo: str) -> str:
    """Diagrama activo → modos de fallo → resumen."""
    activo_txt = activo.replace('"', "'")
    lineas = [
        "flowchart TD",
        f'  A["Activo<br/>{activo_txt}"] --> B["Impactos del activo"]',
    ]
    for i, entrada in enumerate(CATALOGO_MODOS_IMPACTO):
        nodo = f"M{i}"
        titulo = titulo_modo_impacto(entrada)
        if entrada.implementado:
            borde = ""
            if es_modo_falta_calado(entrada.id):
                inputs = "Dc desde Configuración del puerto"
            elif not entrada.requiere_inputs_ui:
                inputs = "sin inputs UI"
            else:
                inputs = "con inputs UI"
            lineas.append(
                f'  B --> {nodo}["{titulo}<br/>'
                f'{entrada.motor_nombre}<br/>{inputs}"]'
            )
            lineas.append(f"  {nodo} --> R")
        else:
            lineas.append(
                f'  B -.-> {nodo}["{titulo}<br/>'
                f'{entrada.motor_nombre}<br/>pendiente"]'
            )
    lineas.append(
        '  R["Resumen del activo<br/>variaciones por escenario y modo de fallo"]'
    )
    return "\n".join(lineas)
