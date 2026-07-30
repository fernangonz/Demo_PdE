# -*- coding: utf-8 -*-
"""Genera el DIAGRAMA DE FLUJO UNICO (procedimiento maestro) en PDF."""

from __future__ import annotations

import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
if str(FOLDER) not in sys.path:
    sys.path.insert(0, str(FOLDER))

from generar_flujos_pdf import (  # noqa: E402
    CX,
    MARGIN,
    PAGE_W,
    FlowPDF,
    branch_from_diamond,
    connect_vertical,
    crop_pdf_below_fin,
)

PAGE_H_MASTER = 11200.0


def _mid(box) -> float:
    return (box["top"] + box["bottom"]) / 2.0


def _gap(prev, amount: float = 42.0) -> float:
    return prev["bottom"] - amount


def _label_white(pdf: FlowPDF, x: float, y: float, text: str, size: int = 11) -> None:
    """Texto con fondo blanco para no solapar trazos."""
    from reportlab.lib.colors import Color, white

    pdf.c.setFont("UIBold", size)
    tw = pdf.c.stringWidth(text, "UIBold", size)
    pdf.c.setFillColor(white)
    pdf.c.rect(x - 4, y - 4, tw + 8, size + 6, stroke=0, fill=1)
    pdf.c.setFillColor(Color(0, 0, 0))
    pdf.label(x, y, text, size=size)


def _label_above_hline(pdf: FlowPDF, x: float, y_line: float, text: str) -> None:
    """Etiqueta claramente por encima de una linea horizontal."""
    _label_white(pdf, x, y_line + 26, text, size=12)


def _label_beside_vline(pdf: FlowPDF, x_line: float, y: float, text: str, right: bool = True) -> None:
    """Etiqueta al lado de un rail vertical."""
    pdf.c.setFont("UIBold", 11)
    tw = pdf.c.stringWidth(text, "UIBold", 11)
    x = x_line + 14 if right else x_line - tw - 14
    _label_white(pdf, x, y, text, size=11)


def _label_beside_merge(pdf: FlowPDF, cx: float, join_y: float, text: str = "Continuar") -> None:
    """Continuar a la derecha del T de fusion, ENCIMA de la horizontal (nunca en la flecha)."""
    _label_white(pdf, cx + 40, join_y + 28, text, size=11)


def _merge_down_to_top(pdf: FlowPDF, left_box, right_box, target_cx: float, target_top: float) -> None:
    """Fusion sin SI/NO: ambas cajas bajan a un codo y entran por arriba."""
    join_y = min(left_box["bottom"], right_box["bottom"]) - 40
    if join_y - target_top < 75:
        join_y = target_top + 75
    pdf.polyline(
        [
            (left_box["cx"], left_box["bottom"]),
            (left_box["cx"], join_y),
            (target_cx, join_y),
        ],
        arrow_end=False,
    )
    pdf.polyline(
        [
            (right_box["cx"], right_box["bottom"]),
            (right_box["cx"], join_y),
            (target_cx, join_y),
        ],
        arrow_end=False,
    )
    pdf.arrow_down(target_cx, join_y, target_top + 2)
    _label_beside_merge(pdf, target_cx, join_y, "Continuar")


def _merge_four_to_top(pdf: FlowPDF, boxes, target_cx: float, target_top: float) -> None:
    """Fusion no etiquetada de varias cajas hacia el siguiente paso."""
    join_y = min(b["bottom"] for b in boxes) - 40
    if join_y - target_top < 75:
        join_y = target_top + 75
    for b in boxes:
        pdf.polyline(
            [
                (b["cx"], b["bottom"]),
                (b["cx"], join_y),
                (target_cx, join_y),
            ],
            arrow_end=False,
        )
    pdf.arrow_down(target_cx, join_y, target_top + 2)
    _label_beside_merge(pdf, target_cx, join_y, "Continuar")


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
        "DIAGRAMA DE FLUJO ÚNICO  Procedimiento maestro",
    )
    cx = CX
    w = 1180
    y = PAGE_H_MASTER - 90

    inicio = pdf.oval(cx, y - 22, 160, 44, "INICIO")
    y = inicio["bottom"] - 40

    b1 = pdf.process_box(
        cx, y, w,
        "1. Cargar los archivos de entrada",
        [
            "Entrar en la carpeta data_modelos y cargar:",
            " 1_Configuración_del_puerto",
            " 2_Relación_umbrales_y_curvas_de_daño_vs_activos",
            " 3_Indicadores_climáticos",
            " 4_Relación_modelos_activos_e_indicadores",
            " Relación_impactos_variables_climáticas",
        ],
    )
    connect_vertical(pdf, inicio, b1)

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

    b2b = pdf.process_box(
        cx, _gap(b2), w,
        "2b. Identificar el modelo que se está ejecutando",
        [
            "##Rama A  PI Superación de Umbral",
            "Variación futura de un indicador climático (por umbral o predefinido).",
            "##Rama B  PI Falta de Francobordo",
            "Indicador de inundación costera en atraque usando Fb o umbral.",
            "##Rama C  OPEX Falta de Calado",
            "Falta de calado en filas OPEX (p. ej. ELO / ELS).",
            "##Rama D  CAPEX Falta de Calado",
            "Falta de calado solo en filas ELU (CAPEX).",
            "La rama determina campos, filtros, selección de indicador y cálculo.",
        ],
    )
    connect_vertical(pdf, b2, b2b)

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

    left_cx = cx - 500
    right_cx = cx + 500

    y_d = b5b["bottom"] - 80
    d_fila = pdf.diamond(cx, y_d, 340, 120, "¿Existe fila definida en Excel 4?")
    pdf.arrow_down(cx, b5b["bottom"] - 2, d_fila["top"] + 2)

    branch_top = d_fila["bottom"] - 55
    branch_from_diamond(pdf, d_fila, left_cx, right_cx, branch_top, "SÍ", "NO")

    b_si = pdf.process_box(
        left_cx, branch_top, 540,
        "SÍ  Usar configuración del Excel",
        [
            "Usar percentil y selección del indicador del Excel.",
            "Selección posible: Predefinido / Por umbral /",
            "No predefinido (francobordo).",
        ],
        font_size=11,
    )
    b_no = pdf.process_box(
        right_cx, branch_top, 540,
        "NO  Lógica clásica del diagrama",
        [
            "Percentil por defecto: P99.",
            "A/C/D: selección por umbral ? paso 6.",
            "B Francobordo: no predefinido; aplicar Fb/umbral.",
        ],
        font_size=11,
    )

    pred_cy = min(b_si["bottom"], b_no["bottom"]) - 200
    d_pred = pdf.diamond(cx, pred_cy, 360, 130, "¿Indicador predefinido?")
    _merge_down_to_top(pdf, b_si, b_no, cx, d_pred["top"])

    out_top = d_pred["bottom"] - 55
    branch_from_diamond(pdf, d_pred, left_cx, right_cx, out_top, "SÍ", "NO")

    b_skip6 = pdf.process_box(
        left_cx, out_top, 540,
        "SÍ  Omitir paso 6 ? ir a paso 7",
        [
            "Usar indicador fijado en Excel 4.",
            "No buscar umbral numérico.",
            "Francobordo: no usar Fb ni umbral alternativo.",
        ],
        font_size=11,
    )
    b_no_pred = pdf.process_box(
        right_cx, out_top, 540,
        "NO  Continuar según modelo",
        [
            "A/C/D ? paso 6 (buscar umbral).",
            "B Francobordo: ¿Fb numérico?",
            "  · SÍ ? omitir 6; referencia = Fb.",
            "  · NO ? paso 6; referencia = umbral.",
        ],
        font_size=11,
    )

    y6 = min(b_skip6["bottom"], b_no_pred["bottom"]) - 70
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

    mid6 = (b_no_pred["bottom"] + b6["top"]) / 2.0
    pdf.polyline(
        [
            (right_cx, b_no_pred["bottom"]),
            (right_cx, mid6),
            (cx, mid6),
            (cx, b6["top"] + 2),
        ]
    )

    skip_rail = MARGIN + 90
    pdf.polyline(
        [
            (left_cx, b_skip6["bottom"]),
            (left_cx, (b_skip6["bottom"] + b6["top"]) / 2),
            (skip_rail, (b_skip6["bottom"] + b6["top"]) / 2),
            (skip_rail, b6["bottom"] - 30),
        ],
        arrow_end=False,
    )
    _label_beside_vline(pdf, skip_rail, _mid(b6), "omitir 6 ? paso 7", right=True)

    b7 = pdf.process_box(
        cx, _gap(b6, 60), w,
        "7. Buscar el indicador climático",
        [
            "EXCEL|3_Indicadores_climáticos",
            "Filtros: Variable climática (IM) + Percentil (5b o P99).",
            "##Opción 1  Predefinido (cualquiera de las 4 ramas)",
            "Usar indicador de Excel 4. No umbral / no Fb.",
            "##Opción 2  Por umbral (A, C, D)",
            "Candidato = indicador que contenga el umbral del paso 6.",
            "##Opción 3  Francobordo (B, no predefinido)",
            "Referencia = Fb (si hay) o umbral (si Fb vacío).",
            "Buscar «inundación costera en un atraque».",
            "Elegir el menor valor de los candidatos con valor ? referencia.",
        ],
    )
    connect_vertical(pdf, b6, b7)
    b7_mid = _mid(b7)
    # Bypass entra al paso 7 desde la izquierda (flecha ?)
    pdf.polyline(
        [
            (skip_rail, b6["bottom"] - 30),
            (skip_rail, b7_mid),
            (b7["left"], b7_mid),
        ]
    )

    b72 = pdf.process_box(
        cx, _gap(b7), w,
        "7.2 / 7.3. Desempate y extracción de valores",
        [
            "Si hay varios candidatos ? 2º filtro: contiene Tipo de UO.",
            "Si aún hay varios ? criterio espacial: Lon/Lat más cercana al centroide del activo.",
            "Extraer: valor Histórico + todos los escenarios futuros (SSP2-4.5, SSP5-8.5, ).",
        ],
    )
    connect_vertical(pdf, b7, b72)

    b_split = pdf.process_box(
        cx, _gap(b72, 50), w,
        "810. Según modelo identificado en 2b  aplicar SOLO una rama",
        [
            "Elegir la rama del modelo en ejecución (A, B, C o D).",
            "No ejecutar las cuatro en paralelo: solo la que corresponda al modelo.",
        ],
    )
    connect_vertical(pdf, b72, b_split)

    box_w = 480
    gap_x = 28
    total_span = 4 * box_w + 3 * gap_x
    x0 = cx - total_span / 2 + box_w / 2
    cols = [x0 + i * (box_w + gap_x) for i in range(4)]
    y8 = b_split["bottom"] - 70

    pdf.arrow_down(cx, b_split["bottom"] - 2, y8 + 2)
    split_drop = (b_split["bottom"] + y8) / 2.0
    for col, lab in zip(cols, ["? A", "? B", "? C", "? D"]):
        pdf.polyline(
            [
                (cx, split_drop),
                (col, split_drop),
                (col, y8 + 2),
            ]
        )
        pdf.label(col + 8, split_drop + 16, lab, size=12)

    b8a = pdf.process_box(
        cols[0], y8, box_w,
        "Rama A  PI Superación de Umbral",
        [
            "8A Variación = Indicador_escenario ? Histórico",
            "   (Histórico ? Variación = 0)",
            "9A Tabla: Escenario | Indicador | Variación",
            "10A >0 Empeora · <0 Mejora · =0 Sin cambios",
        ],
        font_size=10,
    )
    b8b = pdf.process_box(
        cols[1], y8, box_w,
        "Rama B  PI Falta de Francobordo",
        [
            "8B Variación = Indicador_escenario ? Histórico",
            "   (Histórico ? Variación = 0)",
            "9B Tabla: Escenario | Indicador | Variación",
            "10B >0 Empeora · <0 Mejora · =0 Sin cambios",
        ],
        font_size=10,
    )
    b8c = pdf.process_box(
        cols[2], y8, box_w,
        "Rama C  OPEX Falta de Calado",
        [
            "8C h = NM ? h0 ? hsedim (por escenario)",
            "9C Tabla: Escenario | NM | h sed | h0 | h",
            "10C Umbral ? h ? Es necesario dragar",
            "    Umbral > h ? No es necesario dragar",
        ],
        font_size=10,
    )
    b8d = pdf.process_box(
        cols[3], y8, box_w,
        "Rama D  CAPEX Falta de Calado",
        [
            "8D h = NM ? h0 ? hsedim (por escenario)",
            "9D Tabla: Escenario | NM | h sed | h0 | h",
            "10D Umbral ? h ? Es necesario dragar",
            "    Umbral > h ? No es necesario dragar",
        ],
        font_size=10,
    )

    merge_bottom = min(b8a["bottom"], b8b["bottom"], b8c["bottom"], b8d["bottom"])
    d11_cy = merge_bottom - 210
    d11 = pdf.diamond(cx, d11_cy, 380, 130, "11. ¿Quedan modos de fallo (IM) en el activo?")
    _merge_four_to_top(pdf, [b8a, b8b, b8c, b8d], cx, d11["top"])

    b11_si = pdf.process_box(
        left_cx, d11["bottom"] - 50, 520,
        "SÍ  Continuar iteración IM",
        [
            "IM = IM + 1. Volver al paso 5.",
            "Nuevo modo / variable / tipo.",
            "Resolver otra vez percentil e indicador en 5b.",
            "No reutilizar el del modo anterior.",
        ],
        font_size=11,
    )
    pdf.polyline(
        [
            (d11["left"], d11["cy"]),
            (left_cx, d11["cy"]),
            (left_cx, b11_si["top"] + 2),
        ]
    )
    _label_above_hline(pdf, left_cx + 16, d11["cy"], "SÍ")

    rail = MARGIN + 40
    b5_mid = _mid(b5)
    b11_mid = _mid(b11_si)
    # Bucle IM: izquierda ? arriba ? entra al paso 5 (flecha ?)
    pdf.polyline(
        [
            (b11_si["left"], b11_mid),
            (rail, b11_mid),
            (rail, b5_mid),
            (b5["left"], b5_mid),
        ]
    )
    _label_beside_vline(pdf, rail, (b5_mid + b11_mid) / 2, "→ paso 5", right=True)

    b12 = pdf.process_box(
        right_cx, d11["bottom"] - 50, 520,
        "NO ? 12. ¿Quedan activos (CP)?",
        [
            "SÍ: CP = CP + 1 ? volver al paso 3.",
            "Extraer activo, Tipo UO, Fb/Dc según modelo.",
            "Continuar desde el paso 4.",
            "NO: FIN.",
        ],
        font_size=11,
    )
    pdf.polyline(
        [
            (d11["right"], d11["cy"]),
            (right_cx, d11["cy"]),
            (right_cx, b12["top"] + 2),
        ]
    )
    _label_above_hline(pdf, right_cx - 36, d11["cy"], "NO")

    d12 = pdf.diamond(right_cx, b12["bottom"] - 75, 300, 110, "¿Quedan activos CP?")
    pdf.arrow_down(right_cx, b12["bottom"] - 2, d12["top"] + 2)

    rail_r = PAGE_W - MARGIN - 40
    b3_mid = _mid(b3)
    # Bucle CP: derecha ? arriba ? entra al paso 3 (flecha ? desde la derecha)
    # Segmentos limpios (sin solape en el codo)
    pdf.polyline(
        [
            (d12["right"], d12["cy"]),
            (rail_r, d12["cy"]),
        ],
        arrow_end=False,
    )
    pdf.polyline(
        [
            (rail_r, d12["cy"]),
            (rail_r, b3_mid),
            (b3["right"], b3_mid),
        ]
    )
    # Etiqueta en el tramo vertical (sentido ? claro), no en el codo
    _label_above_hline(pdf, d12["right"] + 18, d12["cy"], "SÍ")
    _label_beside_vline(
        pdf,
        rail_r,
        (d12["cy"] + b3_mid) / 2,
        "→ paso 3",
        right=False,
    )

    fin_y = min(b11_si["bottom"], d12["bottom"]) - 90
    fin = pdf.oval(cx, fin_y, 160, 44, "FIN")
    pdf.polyline(
        [
            (d12["left"], d12["cy"]),
            (cx, d12["cy"]),
            (cx, fin["top"] + 2),
        ]
    )
    _label_above_hline(pdf, d12["left"] - 50, d12["cy"], "NO")

    pdf.label(
        MARGIN + 40,
        fin["bottom"] - 50,
        "Tronco común CP/IM  ramas A/B/C/D solo donde el modelo diverge  bucles IM?5 y CP?3",
        size=11,
        bold=False,
    )

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
    texto = """DIAGRAMA DE FLUJO ÚNICO
Procedimiento maestro: PI Superación de Umbral | PI Falta de Francobordo | OPEX Falta de Calado | CAPEX Falta de Calado

INICIO
?
1. Cargar archivos (data_modelos)
?
2. Configuración del cálculo (percentil/selección ? en 5b por IM)
?
2b. Identificar modelo ? Rama A / B / C / D
?
3. Iteración CP (activos)
?
4. Buscar impactos (filtro según rama)
?
5. Iteración IM (modos de fallo)
?
5b. Regla en Relacion_modelos_activos_e_indicadores
?
¿Existe fila?  SÍ ? config Excel | NO ? P99 + lógica clásica
Continuar
¿Indicador predefinido?
  SÍ ? omitir paso 6 ? paso 7 (bypass lateral ?)
  NO ? paso 6 (salvo Fb numérico en francobordo)
?
7. Indicador: predefinido | por umbral | francobordo (? referencia)
?
810. SOLO una rama A/B/C/D según modelo 2b
Continuar
11. ¿Quedan IM? SÍ ? paso 5 | NO ? 12
?
12. ¿Quedan CP? SÍ ? paso 3 | NO ? FIN
"""
    out_path.write_text(texto, encoding="utf-8")


def main() -> None:
    pdf_path = FOLDER / "DIAGRAMA DE FLUJO UNICO.pdf"
    txt_path = FOLDER / "DIAGRAMA DE FLUJO UNICO.txt"
    build_master(pdf_path)
    write_master_txt(txt_path)
    print(f"OK PDF: {pdf_path}")
    print(f"OK TXT: {txt_path}")


if __name__ == "__main__":
    main()
