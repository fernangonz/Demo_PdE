# -*- coding: utf-8 -*-
"""Genera el DIAGRAMA DE FLUJO UNICO (procedimiento maestro) en PDF."""

from __future__ import annotations

import sys
from pathlib import Path

# Permitir importar las primitivas del generador existente
FOLDER = Path(__file__).resolve().parent
if str(FOLDER) not in sys.path:
    sys.path.insert(0, str(FOLDER))

from generar_flujos_pdf import (  # noqa: E402
    CX,
    MARGIN,
    PAGE_W,
    FlowPDF,
    connect_vertical,
    crop_pdf_below_fin,
)

# Página más alta: el maestro es más largo que un flujo individual
PAGE_H_MASTER = 9800.0


def _mid(box) -> float:
    """Centro vertical de una caja (process_box no expone cy)."""
    return (box["top"] + box["bottom"]) / 2.0


def _gap(prev, amount: float = 36.0) -> float:
    return prev["bottom"] - amount


class MasterFlowPDF(FlowPDF):
    def __init__(self, path: Path, title: str):
        self.path = path
        self.title = title
        from reportlab.pdfgen import canvas

        self.c = canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H_MASTER))
        self._page_h = PAGE_H_MASTER
        self._draw_frame()
        self.c.setFont("UIBold", 18)
        from reportlab.lib.colors import black

        self.c.setFillColor(black)
        self.c.drawString(MARGIN + 32, PAGE_H_MASTER - 34, title)

    def _draw_frame(self):
        from generar_flujos_pdf import NAVY_STROKE

        self.c.setStrokeColor(NAVY_STROKE)
        self.c.setLineWidth(2.5)
        self.c.rect(MARGIN, 6, PAGE_W - 2 * MARGIN, self._page_h - 12, stroke=1, fill=0)


def build_master(out_path: Path) -> None:
    pdf = MasterFlowPDF(
        out_path,
        "DIAGRAMA DE FLUJO ÚNICO — Procedimiento maestro",
    )
    cx = CX
    w = 1180
    y = PAGE_H_MASTER - 90

    # INICIO
    inicio = pdf.oval(cx, y - 22, 160, 44, "INICIO")
    y = inicio["bottom"] - 40

    # 1
    b1 = pdf.process_box(
        cx, y, w,
        "1. Cargar los archivos de entrada",
        [
            "Entrar en la carpeta data_modelos y cargar:",
            "• 1_Configuración_del_puerto",
            "• 2_Relación_umbrales_y_curvas_de_daño_vs_activos",
            "• 3_Indicadores_climáticos",
            "• 4_Relación_modelos_activos_e_indicadores",
            "• Relación_impactos_variables_climáticas",
        ],
    )
    connect_vertical(pdf, inicio, b1)

    # 2
    b2 = pdf.process_box(
        cx, _gap(b1), w,
        "2. Configuración del cálculo",
        [
            "El percentil y el modo de selección del indicador NO se fijan de forma global.",
            "Se resuelven en el paso 5b, dentro de cada iteración IM.",
            "Cada modo de fallo puede tener: percentil distinto, indicador predefinido,",
            "indicador por umbral, o regla específica de falta de francobordo.",
        ],
    )
    connect_vertical(pdf, b1, b2)

    # 2b
    b2b = pdf.process_box(
        cx, _gap(b2), w,
        "2b. Identificar el modelo que se está ejecutando",
        [
            "##Rama A — PI Superación de Umbral",
            "Variación futura de un indicador climático (por umbral o predefinido).",
            "##Rama B — PI Falta de Francobordo",
            "Indicador de inundación costera en atraque usando Fb o umbral.",
            "##Rama C — OPEX Falta de Calado",
            "Falta de calado en filas OPEX (p. ej. ELO / ELS).",
            "##Rama D — CAPEX Falta de Calado",
            "Falta de calado solo en filas ELU (CAPEX).",
            "La rama determina campos, filtros, selección de indicador y cálculo.",
        ],
    )
    connect_vertical(pdf, b2, b2b)

    # 3
    b3 = pdf.process_box(
        cx, _gap(b2b), w,
        "3. Iteración por Activos (CP)",
        [
            "EXCEL|1_Configuración_del_puerto",
            "Recorrer cada Activo Físico u Operacional. Inicializar CP = 1.",
            "Extraer siempre: Activo + Tipo de UO.",
            "##Campos específicos por rama",
            "A Superación: sin campo numérico adicional.",
            "B Francobordo: extraer Fb (numérico o vacío).",
            "C OPEX Calado: extraer Dc (calado del buque).",
            "D CAPEX Calado: extraer Dc (calado del buque).",
        ],
    )
    connect_vertical(pdf, b2b, b3)

    # 4
    b4 = pdf.process_box(
        cx, _gap(b3), w,
        "4. Buscar impactos asociados al activo",
        [
            "EXCEL|Relación_impactos_variables_climáticas",
            "Buscar: Activo Físico u Operacional = activo de la iteración CP.",
            "##Filtro por rama",
            "A Superación: todas las filas coincidentes del activo.",
            "B Francobordo: filas del activo (incl. Falta de Francobordo).",
            "C OPEX Calado: solo Falta de Calado + impacto OPEX (ELO/ELS).",
            "D CAPEX Calado: solo Falta de Calado + tipo ELU (CAPEX).",
        ],
    )
    connect_vertical(pdf, b3, b4)

    # 5
    b5 = pdf.process_box(
        cx, _gap(b4), w,
        "5. Iteración por Modos de fallo (IM)",
        [
            "Inicializar IM = 1. Recorrer filas del paso 4.",
            "Por cada fila extraer: Modo de fallo / Modo de parada, Variable, Tipo de impacto.",
            "OPEX Calado: tipo p. ej. ELO o ELS.",
            "CAPEX Calado: tipo ELU.",
        ],
    )
    connect_vertical(pdf, b4, b5)

    # 5b
    b5b = pdf.process_box(
        cx, _gap(b5), w,
        "5b. Buscar regla en Relacion_modelos_activos_e_indicadores",
        [
            "EXCEL|4_Relación_modelos_activos_e_indicadores",
            "Revisar No indicadores (informativo; no cambia sola la selección).",
            "Match explícito: Modelo + Activo (si está) + Modo + Variable + Tipo (si está).",
            "Modo y Variable deben ser explícitos (sin comodines).",
        ],
    )
    connect_vertical(pdf, b5, b5b)

    # Diamante: ¿Existe fila?
    y_d = b5b["bottom"] - 70
    d_fila = pdf.diamond(cx, y_d, 320, 110, "¿Existe fila definida en Excel 4?")
    pdf.arrow_down(cx, b5b["bottom"] - 2, d_fila["top"] + 2)

    # Rama SÍ / NO laterales
    left_cx = cx - 480
    right_cx = cx + 480
    branch_top = d_fila["bottom"] - 50

    b_si = pdf.process_box(
        left_cx, branch_top, 520,
        "SÍ — Usar configuración del Excel",
        [
            "Usar percentil y selección del indicador del Excel.",
            "Selección posible: Predefinido / Por umbral /",
            "No predefinido (francobordo).",
        ],
        font_size=11,
    )
    b_no = pdf.process_box(
        right_cx, branch_top, 520,
        "NO — Lógica clásica del diagrama",
        [
            "Percentil por defecto: P99.",
            "A/C/D: selección por umbral ? paso 6.",
            "B Francobordo: no predefinido; aplicar Fb/umbral.",
        ],
        font_size=11,
    )
    # Conexiones desde diamante
    pdf.polyline([
        (d_fila["left"], d_fila["cy"]),
        (left_cx, d_fila["cy"]),
        (left_cx, b_si["top"] + 2),
    ])
    pdf.label(left_cx + 20, d_fila["cy"] + 12, "SÍ")
    pdf.polyline([
        (d_fila["right"], d_fila["cy"]),
        (right_cx, d_fila["cy"]),
        (right_cx, b_no["top"] + 2),
    ])
    pdf.label(right_cx - 40, d_fila["cy"] + 12, "NO")

    # Diamante predefinido (centro, bajo las dos ramas)
    merge_y = min(b_si["bottom"], b_no["bottom"]) - 70
    d_pred = pdf.diamond(cx, merge_y, 340, 120, "¿Indicador predefinido?")
    # Bajar desde ambas cajas al diamante
    pdf.polyline([
        (left_cx, b_si["bottom"]),
        (left_cx, d_pred["cy"]),
        (d_pred["left"], d_pred["cy"]),
    ])
    pdf.polyline([
        (right_cx, b_no["bottom"]),
        (right_cx, d_pred["cy"]),
        (d_pred["right"], d_pred["cy"]),
    ])

    # SÍ predefinido ? saltar 6
    b_skip6 = pdf.process_box(
        left_cx, d_pred["bottom"] - 50, 520,
        "SÍ — Omitir paso 6 ? ir a paso 7",
        [
            "Usar indicador fijado en Excel 4.",
            "No buscar umbral numérico.",
            "Francobordo: no usar Fb ni umbral alternativo.",
        ],
        font_size=11,
    )
    pdf.polyline([
        (d_pred["left"], d_pred["cy"]),
        (left_cx, d_pred["cy"]),
        (left_cx, b_skip6["top"] + 2),
    ])
    pdf.label(left_cx + 20, d_pred["cy"] + 12, "SÍ")

    # NO predefinido ? Fb check / paso 6
    b_no_pred = pdf.process_box(
        right_cx, d_pred["bottom"] - 50, 520,
        "NO — Continuar según modelo",
        [
            "A/C/D ? paso 6 (buscar umbral).",
            "B Francobordo: ¿Fb numérico?",
            "  · SÍ ? omitir 6; referencia = Fb.",
            "  · NO ? paso 6; referencia = umbral.",
        ],
        font_size=11,
    )
    pdf.polyline([
        (d_pred["right"], d_pred["cy"]),
        (right_cx, d_pred["cy"]),
        (right_cx, b_no_pred["top"] + 2),
    ])
    pdf.label(right_cx - 40, d_pred["cy"] + 12, "NO")

    # 6 Umbral
    y6 = min(b_skip6["bottom"], b_no_pred["bottom"]) - 50
    b6 = pdf.process_box(
        cx, y6, w,
        "6. Buscar el umbral correspondiente (si aplica)",
        [
            "Se omite si: indicador predefinido, o (francobordo) Fb tiene valor numérico.",
            "EXCEL|2_Relación_umbrales_y_curvas_de_daño_vs_activos",
            "Filtros: Activo + Modo de fallo.",
            "Umbral: columna Tipo UO si tiene valor; si no ? Umbral General.",
            "Si es formulación (p. ej. con Dc): calcular y guardar umbral numérico.",
        ],
    )
    # Conectar rama NO-predefinido a 6; skip6 baja a bypass hacia 7
    pdf.polyline([
        (right_cx, b_no_pred["bottom"]),
        (right_cx, (b6["top"] + b_no_pred["bottom"]) / 2),
        (cx, (b6["top"] + b_no_pred["bottom"]) / 2),
        (cx, b6["top"] + 2),
    ])
    pdf.polyline([
        (left_cx, b_skip6["bottom"]),
        (left_cx, b6["bottom"] - 20),
        (cx - 40, b6["bottom"] - 20),
    ])
    pdf.label(left_cx + 8, b6["bottom"] - 8, "omitir 6")

    # 7 Indicador
    b7 = pdf.process_box(
        cx, _gap(b6, 55), w,
        "7. Buscar el indicador climático",
        [
            "EXCEL|3_Indicadores_climáticos",
            "Filtros: Variable climática (IM) + Percentil (5b o P99).",
            "##Opción 1 — Predefinido (cualquiera de las 4 ramas)",
            "Usar indicador de Excel 4. No umbral / no Fb.",
            "##Opción 2 — Por umbral (A, C, D)",
            "Candidato = indicador que contenga el umbral del paso 6.",
            "##Opción 3 — Francobordo (B, no predefinido)",
            "Referencia = Fb (si hay) o umbral (si Fb vacío).",
            "Buscar «inundación costera en un atraque».",
            "Elegir el menor valor de los candidatos con valor ? referencia.",
        ],
    )
    connect_vertical(pdf, b6, b7)
    # flecha desde bypass omitir 6
    pdf.arrow_down(cx - 40, b6["bottom"] - 20, b7["top"] + 2)

    # 7.2 varios
    b72 = pdf.process_box(
        cx, _gap(b7), w,
        "7.2 / 7.3. Desempate y extracción de valores",
        [
            "Si hay varios candidatos ? 2º filtro: contiene Tipo de UO.",
            "Si aún hay varios ? criterio espacial: Lon/Lat más cercana al centroide del activo.",
            "Extraer: valor Histórico + todos los escenarios futuros (SSP2-4.5, SSP5-8.5, …).",
        ],
    )
    connect_vertical(pdf, b7, b72)

    # 8 ramas de cálculo — 4 cajas en 2x2
    y8 = b72["bottom"] - 40
    pdf.label_center(cx, y8 + 10, "8–10. Cálculo e interpretación según rama", size=14)
    y8 -= 30

    box_w = 560
    gap_x = 40
    left = cx - box_w - gap_x / 2
    right = cx + box_w + gap_x / 2

    b8a = pdf.process_box(
        left, y8, box_w,
        "Rama A — PI Superación de Umbral",
        [
            "8A Variación = Indicador_escenario ? Histórico",
            "   (Histórico ? Variación = 0)",
            "9A Tabla: Escenario | Indicador | Variación",
            "10A Interpretar (unidad del indicador):",
            "   >0 Empeora · <0 Mejora · =0 Sin cambios",
        ],
        font_size=11,
    )
    b8b = pdf.process_box(
        right, y8, box_w,
        "Rama B — PI Falta de Francobordo",
        [
            "8B Variación = Indicador_escenario ? Histórico",
            "   (Histórico ? Variación = 0)",
            "9B Tabla: Escenario | Indicador | Variación",
            "10B Interpretar según indicador (horas/días):",
            "   >0 Empeora · <0 Mejora · =0 Sin cambios",
        ],
        font_size=11,
    )
    pdf.arrow_down(cx, b72["bottom"] - 2, y8 + 2)

    y8b = min(b8a["bottom"], b8b["bottom"]) - 36
    b8c = pdf.process_box(
        left, y8b, box_w,
        "Rama C — OPEX Falta de Calado",
        [
            "8C h = NM ? h0 ? hsedim  (por escenario)",
            "9C Tabla: Escenario | NM | h sed | h0 | h",
            "10C Umbral ? h ? Es necesario dragar",
            "    Umbral > h ? No es necesario dragar",
            "Filas de impacto OPEX (ELO/ELS).",
        ],
        font_size=11,
    )
    b8d = pdf.process_box(
        right, y8b, box_w,
        "Rama D — CAPEX Falta de Calado",
        [
            "8D h = NM ? h0 ? hsedim  (por escenario)",
            "9D Tabla: Escenario | NM | h sed | h0 | h",
            "10D Umbral ? h ? Es necesario dragar",
            "    Umbral > h ? No es necesario dragar",
            "Misma fórmula; filas ELU (CAPEX).",
        ],
        font_size=11,
    )

    # Merge a 11
    merge_bottom = min(b8c["bottom"], b8d["bottom"])
    y11 = merge_bottom - 55

    d11 = pdf.diamond(cx, y11 - 55, 360, 120, "11. ¿Quedan modos de fallo (IM) en el activo?")
    pdf.arrow_down(cx, merge_bottom - 2, d11["top"] + 2)

    # SÍ ? volver a 5
    b11_si = pdf.process_box(
        left_cx, d11["bottom"] - 45, 500,
        "SÍ — Continuar iteración IM",
        [
            "IM = IM + 1. Volver al paso 5.",
            "Nuevo modo / variable / tipo.",
            "Resolver otra vez percentil e indicador en 5b.",
            "No reutilizar el del modo anterior.",
        ],
        font_size=11,
    )
    pdf.polyline([
        (d11["left"], d11["cy"]),
        (left_cx, d11["cy"]),
        (left_cx, b11_si["top"] + 2),
    ])
    pdf.label(left_cx + 16, d11["cy"] + 12, "SÍ")
    # bucle hacia arriba a b5
    rail = MARGIN + 40
    b5_mid = _mid(b5)
    b11_mid = _mid(b11_si)
    pdf.polyline([
        (b11_si["left"], b11_mid),
        (rail, b11_mid),
        (rail, b5_mid),
        (b5["left"], b5_mid),
    ])
    pdf.label(rail + 8, (b5["top"] + b11_si["bottom"]) / 2, "? paso 5")

    # NO ? 12
    b12 = pdf.process_box(
        right_cx, d11["bottom"] - 45, 500,
        "NO ? 12. ¿Quedan activos (CP)?",
        [
            "SÍ: CP = CP + 1 ? volver al paso 3.",
            "Extraer activo, Tipo UO, Fb/Dc según modelo.",
            "Continuar desde el paso 4.",
            "NO: FIN.",
        ],
        font_size=11,
    )
    pdf.polyline([
        (d11["right"], d11["cy"]),
        (right_cx, d11["cy"]),
        (right_cx, b12["top"] + 2),
    ])
    pdf.label(right_cx - 36, d11["cy"] + 12, "NO")

    # Diamante 12 bajo b12
    d12 = pdf.diamond(right_cx, b12["bottom"] - 70, 300, 100, "¿Quedan activos CP?")
    pdf.arrow_down(right_cx, b12["bottom"] - 2, d12["top"] + 2)

    # SÍ CP ? bucle a 3
    rail_r = PAGE_W - MARGIN - 40
    b3_mid = _mid(b3)
    pdf.polyline([
        (d12["right"], d12["cy"]),
        (rail_r, d12["cy"]),
        (rail_r, b3_mid),
        (b3["right"], b3_mid),
    ])
    pdf.label(rail_r - 70, d12["cy"] + 12, "SÍ ? paso 3")

    # NO ? FIN
    fin_y = min(b11_si["bottom"], d12["bottom"]) - 80
    fin = pdf.oval(cx, fin_y, 160, 44, "FIN")
    pdf.polyline([
        (d12["left"], d12["cy"]),
        (cx, d12["cy"]),
        (cx, fin["top"] + 2),
    ])
    pdf.label(cx + 12, d12["cy"] + 12, "NO")

    # Nota pie
    pdf.label(
        MARGIN + 40,
        fin["bottom"] - 50,
        "Tronco común CP/IM — ramas A/B/C/D solo donde el modelo diverge — bucles IM?5 y CP?3",
        size=11,
        bold=False,
    )

    # Aviso si el contenido se acerca al borde inferior (solapes / página corta)
    if fin["bottom"] < 80:
        print(
            f"Aviso: FIN muy bajo (bottom={fin['bottom']:.1f}). "
            "Considera subir PAGE_H_MASTER o compactar gaps."
        )

    pdf.save()
    try:
        crop_pdf_below_fin(out_path, padding=60)
    except Exception as exc:  # noqa: BLE001
        print(f"Aviso: no se pudo recortar el PDF ({exc})")


def write_master_txt(out_path: Path) -> None:
    """Versión texto del procedimiento maestro (botón TXT)."""
    texto = """DIAGRAMA DE FLUJO ÚNICO
Procedimiento maestro: PI Superación de Umbral | PI Falta de Francobordo | OPEX Falta de Calado | CAPEX Falta de Calado

INICIO
?
1. Cargar archivos (data_modelos): Configuración del puerto, Umbrales, Indicadores climáticos, Relacion_modelos, Relación impactos.
?
2. Configuración del cálculo: percentil y selección de indicador se resuelven en 5b (por IM).
?
2b. Identificar modelo ? Rama A / B / C / D.
?
3. Iteración CP (activos). Extraer Activo + Tipo UO (+ Fb o Dc según rama).
?
4. Buscar impactos del activo (filtro según rama).
?
5. Iteración IM (modos de fallo).
?
5b. Regla en Relacion_modelos_activos_e_indicadores (match explícito).
?
¿Existe fila?  SÍ ? percentil/selección Excel | NO ? P99 + lógica clásica
?
¿Indicador predefinido?  SÍ ? omitir 6 ? 7 | NO ? umbral (salvo Fb numérico en francobordo)
?
6. Umbral (si aplica): Tipo UO o Umbral General; formular si procede.
?
7. Indicador: predefinido | por umbral | francobordo (inundación costera, ? referencia)
   + filtro Tipo UO + criterio espacial si hay varios
?
8–10. Cálculo:
  A/B ? Variación = escenario ? histórico; interpretar Empeora/Mejora/Sin cambios
  C/D ? h = NM ? h0 ? hsedim; umbral ? h ? dragar; umbral > h ? no dragar
?
11. ¿Quedan IM? SÍ ? IM+1 ? paso 5 | NO ? 12
?
12. ¿Quedan CP? SÍ ? CP+1 ? paso 3 | NO ? FIN
"""
    out_path.write_text(texto, encoding="utf-8")


def main() -> None:
    pdf_path = FOLDER / "DIAGRAMA DE FLUJO UNICO.pdf"
    txt_path = FOLDER / "DIAGRAMA DE FLUJO UNICO.txt"
    build_master(pdf_path)
    write_master_txt(txt_path)
    print(f"OK PDF: {pdf_path}")
    print(f"OK TXT: {txt_path}")
    if pdf_path.exists():
        print(f"PDF size: {pdf_path.stat().st_size} bytes")
    if txt_path.exists():
        print(f"TXT size: {txt_path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
