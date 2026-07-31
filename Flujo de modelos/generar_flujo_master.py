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


def _label_clear_of_vline(pdf: FlowPDF, cx: float, y_from: float, y_to: float, text: str) -> None:
    """Etiqueta a la derecha de la flecha vertical, lejos del trazo y de la punta."""
    from reportlab.lib.colors import white

    y_lo, y_hi = min(y_from, y_to), max(y_from, y_to)
    y_label = y_lo + (y_hi - y_lo) * 0.55
    x_label = cx + 40
    pdf.c.setFont("UIBold", 11)
    tw = pdf.c.stringWidth(text, "UIBold", 11)
    pdf.c.setFillColor(white)
    pdf.c.rect(x_label - 4, y_label - 4, tw + 8, 16, stroke=0, fill=1)
    pdf.label(x_label, y_label, text, size=11)


def _label_above_hline(pdf: FlowPDF, x: float, y_line: float, text: str) -> None:
    """Etiqueta por encima de una linea horizontal (sin cruzarla)."""
    pdf.label(x, y_line + 18, text, size=12)


def _label_beside_vline(pdf: FlowPDF, x_line: float, y: float, text: str, right: bool = True) -> None:
    """Etiqueta al lado de un rail vertical (sentido del bucle)."""
    from reportlab.lib.colors import white

    pdf.c.setFont("UIBold", 11)
    tw = pdf.c.stringWidth(text, "UIBold", 11)
    x = x_line + 14 if right else x_line - tw - 14
    pdf.c.setFillColor(white)
    pdf.c.rect(x - 3, y - 3, tw + 6, 15, stroke=0, fill=1)
    pdf.label(x, y, text, size=11)


def _merge_down_to_top(pdf: FlowPDF, left_box, right_box, target_cx: float, target_top: float) -> None:
    """Fusion sin SI/NO: ambas cajas bajan a un codo y entran por arriba (flecha abajo)."""
    join_y = min(left_box["bottom"], right_box["bottom"]) - 36
    if join_y - target_top < 70:
        join_y = target_top + 70
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
    _label_clear_of_vline(pdf, target_cx, join_y, target_top, "Continuar â")


def _merge_four_to_top(pdf: FlowPDF, boxes, target_cx: float, target_top: float) -> None:
    """Fusion no etiquetada de varias cajas hacia el siguiente paso (flecha abajo)."""
    join_y = min(b["bottom"] for b in boxes) - 36
    if join_y - target_top < 70:
        join_y = target_top + 70
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
    _label_clear_of_vline(pdf, target_cx, join_y, target_top, "Continuar â")


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
        "DIAGRAMA DE FLUJO ÃNICO â Procedimiento maestro",
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
            "â¢ 1_ConfiguraciÃ³n_del_puerto",
            "â¢ 2_RelaciÃ³n_umbrales_y_curvas_de_daÃ±o_vs_activos",
            "â¢ 3_Indicadores_climÃ¡ticos",
            "â¢ 4_RelaciÃ³n_modelos_activos_e_indicadores",
            "â¢ RelaciÃ³n_impactos_variables_climÃ¡ticas",
        ],
    )
    connect_vertical(pdf, inicio, b1)

    b2 = pdf.process_box(
        cx, _gap(b1), w,
        "2. ConfiguraciÃ³n del cÃ¡lculo",
        [
            "El percentil y el modo de selecciÃ³n del indicador NO se fijan de forma global.",
            "Se resuelven en el paso 5b, dentro de cada iteraciÃ³n IM.",
            "Cada modo de fallo puede tener: percentil distinto, indicador predefinido,",
            "indicador por umbral, o regla especÃ­fica de falta de francobordo.",
        ],
    )
    connect_vertical(pdf, b1, b2)

    b2b = pdf.process_box(
        cx, _gap(b2), w,
        "2b. Identificar el modelo que se estÃ¡ ejecutando",
        [
            "##Rama A  PI Superación de Umbral",
            "Variación futura de un indicador climático (por umbral o predefinido).",
            "Caso especial ELO Inundación costera: selección por Fb (>= atraque), no por texto de umbral.",
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
        "3. IteraciÃ³n por Activos (CP)",
        [
            "EXCEL|1_ConfiguraciÃ³n_del_puerto",
            "Recorrer cada Activo FÃ­sico u Operacional. Inicializar CP = 1.",
            "Extraer siempre: Activo + Tipo de UO.",
            "##Campos especÃ­ficos por rama",
            "A SuperaciÃ³n: sin campo numÃ©rico adicional.",
            "B Francobordo: extraer Fb (numÃ©rico o vacÃ­o).",
            "C OPEX Calado: extraer Dc (calado del buque).",
            "D CAPEX Calado: extraer Dc (calado del buque).",
        ],
    )
    connect_vertical(pdf, b2b, b3)

    b4 = pdf.process_box(
        cx, _gap(b3), w,
        "4. Buscar impactos asociados al activo",
        [
            "EXCEL|RelaciÃ³n_impactos_variables_climÃ¡ticas",
            "Buscar: Activo FÃ­sico u Operacional = activo de la iteraciÃ³n CP.",
            "##Filtro por rama",
            "A SuperaciÃ³n: todas las filas coincidentes del activo.",
            "B Francobordo: filas del activo (incl. Falta de Francobordo).",
            "C OPEX Calado: solo Falta de Calado + impacto OPEX (ELO/ELS).",
            "D CAPEX Calado: solo Falta de Calado + tipo ELU (CAPEX).",
        ],
    )
    connect_vertical(pdf, b3, b4)

    b5 = pdf.process_box(
        cx, _gap(b4), w,
        "5. IteraciÃ³n por Modos de fallo (IM)",
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
            "EXCEL|4_RelaciÃ³n_modelos_activos_e_indicadores",
            "Revisar No indicadores (informativo; no cambia sola la selecciÃ³n).",
            "Match explÃ­cito: Modelo + Activo (si estÃ¡) + Modo + Variable + Tipo (si estÃ¡).",
            "Modo y Variable deben ser explÃ­citos (sin comodines).",
        ],
    )
    connect_vertical(pdf, b5, b5b)

    left_cx = cx - 500
    right_cx = cx + 500

    y_d = b5b["bottom"] - 80
    d_fila = pdf.diamond(cx, y_d, 340, 120, "Â¿Existe fila definida en Excel 4?")
    pdf.arrow_down(cx, b5b["bottom"] - 2, d_fila["top"] + 2)

    branch_top = d_fila["bottom"] - 55
    branch_from_diamond(pdf, d_fila, left_cx, right_cx, branch_top, "SÃ", "NO")

    b_si = pdf.process_box(
        left_cx, branch_top, 540,
        "SÃ â Usar configuraciÃ³n del Excel",
        [
            "Usar percentil y selecciÃ³n del indicador del Excel.",
            "SelecciÃ³n posible: Predefinido / Por umbral /",
            "No predefinido (francobordo).",
        ],
        font_size=11,
    )
    b_no = pdf.process_box(
        right_cx, branch_top, 540,
        "NO â LÃ³gica clÃ¡sica del diagrama",
        [
            "Percentil por defecto: P99.",
            "A/C/D: selecciÃ³n por umbral ? paso 6.",
            "B Francobordo: no predefinido; aplicar Fb/umbral.",
        ],
        font_size=11,
    )

    pred_cy = min(b_si["bottom"], b_no["bottom"]) - 110
    d_pred = pdf.diamond(cx, pred_cy, 360, 130, "Â¿Indicador predefinido?")
    _merge_down_to_top(pdf, b_si, b_no, cx, d_pred["top"])

    out_top = d_pred["bottom"] - 55
    branch_from_diamond(pdf, d_pred, left_cx, right_cx, out_top, "SÃ", "NO")

    b_skip6 = pdf.process_box(
        left_cx, out_top, 540,
        "SÃ â Omitir paso 6 ? ir a paso 7",
        [
            "Usar indicador fijado en Excel 4.",
            "No buscar umbral numÃ©rico.",
            "Francobordo: no usar Fb ni umbral alternativo.",
        ],
        font_size=11,
    )
    b_no_pred = pdf.process_box(
        right_cx, out_top, 540,
        "NO â Continuar segÃºn modelo",
        [
            "A/C/D ? paso 6 (buscar umbral).",
            "B Francobordo: Â¿Fb numÃ©rico?",
            "  Â· SÃ ? omitir 6; referencia = Fb.",
            "  Â· NO ? paso 6; referencia = umbral.",
        ],
        font_size=11,
    )

    y6 = min(b_skip6["bottom"], b_no_pred["bottom"]) - 70
    b6 = pdf.process_box(
        cx, y6, w,
        "6. Buscar el umbral correspondiente (si aplica)",
        [
            "Se omite si: indicador predefinido, o Fb numerico (francobordo o Inundacion costera).",
            "EXCEL|2_RelaciÃ³n_umbrales_y_curvas_de_daÃ±o_vs_activos",
            "Filtros: Activo + Modo de fallo.",
            "Umbral: columna Tipo UO si tiene valor; si no ? Umbral General.",
            "Si es formulaciÃ³n (p. ej. con Dc): calcular y guardar umbral numÃ©rico.",
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
    _label_beside_vline(pdf, skip_rail, _mid(b6), "omitir 6 â paso 7", right=True)

    b7 = pdf.process_box(
        cx, _gap(b6, 60), w,
        "7. Buscar el indicador climÃ¡tico",
        [
            "EXCEL|3_Indicadores_climÃ¡ticos",
            "Filtros: Variable climÃ¡tica (IM) + Percentil (5b o P99).",
            "##OpciÃ³n 1 â Predefinido (cualquiera de las 4 ramas)",
            "Usar indicador de Excel 4. No umbral / no Fb.",
            "##OpciÃ³n 2 â Por umbral (A, C, D)",
            "Candidato = indicador que contenga el umbral del paso 6.",
            "Excepcion A Inundacion costera (ELO): NO por texto umbral; referencia = Fb (o umbral si Fb vacio) + inundacion costera en atraque (menor valor >= referencia).",
            "##OpciÃ³n 3 â Francobordo (B, no predefinido)",
            "Referencia = Fb (si hay) o umbral (si Fb vacÃ­o).",
            "Buscar Â«inundaciÃ³n costera en un atraqueÂ».",
            "Elegir el menor valor de los candidatos con valor ? referencia.",
        ],
    )
    connect_vertical(pdf, b6, b7)
    b7_mid = _mid(b7)
    pdf.polyline(
        [
            (skip_rail, b6["bottom"] - 30),
            (skip_rail, b7_mid),
            (b7["left"], b7_mid),
        ]
    )

    b72 = pdf.process_box(
        cx, _gap(b7), w,
        "7.2 / 7.3. Desempate y extracciÃ³n de valores",
        [
            "Si hay varios candidatos ? 2Âº filtro: contiene Tipo de UO.",
            "Si aÃºn hay varios ? criterio espacial: Lon/Lat mÃ¡s cercana al centroide del activo.",
            "Extraer: valor HistÃ³rico + todos los escenarios futuros (SSP2-4.5, SSP5-8.5, â¦).",
        ],
    )
    connect_vertical(pdf, b7, b72)

    b_split = pdf.process_box(
        cx, _gap(b72, 50), w,
        "8â10. SegÃºn modelo identificado en 2b â aplicar SOLO una rama",
        [
            "Elegir la rama del modelo en ejecuciÃ³n (A, B, C o D).",
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
        "Rama A â PI SuperaciÃ³n de Umbral",
        [
            "8A VariaciÃ³n = Indicador_escenario ? HistÃ³rico",
            "   (HistÃ³rico ? VariaciÃ³n = 0)",
            "9A Tabla: Escenario | Indicador | VariaciÃ³n",
            "10A >0 Empeora Â· <0 Mejora Â· =0 Sin cambios",
        ],
        font_size=10,
    )
    b8b = pdf.process_box(
        cols[1], y8, box_w,
        "Rama B â PI Falta de Francobordo",
        [
            "8B VariaciÃ³n = Indicador_escenario ? HistÃ³rico",
            "   (HistÃ³rico ? VariaciÃ³n = 0)",
            "9B Tabla: Escenario | Indicador | VariaciÃ³n",
            "10B >0 Empeora Â· <0 Mejora Â· =0 Sin cambios",
        ],
        font_size=10,
    )
    b8c = pdf.process_box(
        cols[2], y8, box_w,
        "Rama C â OPEX Falta de Calado",
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
        "Rama D â CAPEX Falta de Calado",
        [
            "8D h = NM ? h0 ? hsedim (por escenario)",
            "9D Tabla: Escenario | NM | h sed | h0 | h",
            "10D Umbral ? h ? Es necesario dragar",
            "    Umbral > h ? No es necesario dragar",
        ],
        font_size=10,
    )

    merge_bottom = min(b8a["bottom"], b8b["bottom"], b8c["bottom"], b8d["bottom"])
    d11_cy = merge_bottom - 130
    d11 = pdf.diamond(cx, d11_cy, 380, 130, "11. Â¿Quedan modos de fallo (IM) en el activo?")
    _merge_four_to_top(pdf, [b8a, b8b, b8c, b8d], cx, d11["top"])

    b11_si = pdf.process_box(
        left_cx, d11["bottom"] - 50, 520,
        "SÃ â Continuar iteraciÃ³n IM",
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
    _label_above_hline(pdf, left_cx + 16, d11["cy"], "SÃ â")

    rail = MARGIN + 40
    b5_mid = _mid(b5)
    b11_mid = _mid(b11_si)
    pdf.polyline(
        [
            (b11_si["left"], b11_mid),
            (rail, b11_mid),
            (rail, b5_mid),
            (b5["left"], b5_mid),
        ]
    )
    _label_beside_vline(pdf, rail, (b5_mid + b11_mid) / 2, "â volver a paso 5", right=True)

    b12 = pdf.process_box(
        right_cx, d11["bottom"] - 50, 520,
        "NO ? 12. Â¿Quedan activos (CP)?",
        [
            "SÃ: CP = CP + 1 ? volver al paso 3.",
            "Extraer activo, Tipo UO, Fb/Dc segÃºn modelo.",
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
    _label_above_hline(pdf, right_cx - 48, d11["cy"], "NO â")

    d12 = pdf.diamond(right_cx, b12["bottom"] - 75, 300, 110, "Â¿Quedan activos CP?")
    pdf.arrow_down(right_cx, b12["bottom"] - 2, d12["top"] + 2)

    rail_r = PAGE_W - MARGIN - 40
    b3_mid = _mid(b3)
    # Bucle CP: derecha -> arriba -> entra al paso 3
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
    # Etiqueta en el tramo vertical (sentido arriba), no en el codo
    _label_beside_vline(
        pdf,
        rail_r,
        (d12["cy"] + b3_mid) / 2,
        "SÃ â paso 3",
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
    _label_above_hline(pdf, cx + 20, d12["cy"], "NO â FIN")

    pdf.label(
        MARGIN + 40,
        fin["bottom"] - 50,
        "Tronco comÃºn CP/IM â ramas A/B/C/D solo donde el modelo diverge â bucles IM?5 y CP?3",
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
    texto = """DIAGRAMA DE FLUJO ÃNICO
Procedimiento maestro: PI SuperaciÃ³n de Umbral | PI Falta de Francobordo | OPEX Falta de Calado | CAPEX Falta de Calado

INICIO
?
1. Cargar archivos (data_modelos)
?
2. ConfiguraciÃ³n del cÃ¡lculo (percentil/selecciÃ³n ? en 5b por IM)
?
2b. Identificar modelo ? Rama A / B / C / D
?
3. IteraciÃ³n CP (activos)
?
4. Buscar impactos (filtro segÃºn rama)
?
5. IteraciÃ³n IM (modos de fallo)
?
5b. Regla en Relacion_modelos_activos_e_indicadores
?
Â¿Existe fila?  SÃ ? config Excel | NO ? P99 + lÃ³gica clÃ¡sica
? Continuar
Â¿Indicador predefinido?
  SÃ ? omitir paso 6 ? paso 7 (bypass lateral)
  NO ? paso 6 (salvo Fb numÃ©rico en francobordo)
?
7. Indicador: predefinido | por umbral | francobordo (? referencia)
?
8â10. SOLO una rama A/B/C/D segÃºn modelo 2b
? Continuar
11. Â¿Quedan IM? SÃ ? ? paso 5 | NO ? 12
?
12. Â¿Quedan CP? SÃ ? subir a paso 3 | NO ? FIN
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
