# -*- coding: utf-8 -*-
"""Genera PDFs de diagramas de flujo con el mismo estilo visual que
PI SUPERACIÓN DE UMBRAL.pdf (cajas azul marino, rombos beige, flechas, bucles)."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib.colors import Color, black, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Estilo (extraído del PDF de ejemplo)
# ---------------------------------------------------------------------------
NAVY = Color(0.0, 0.125, 0.376)
NAVY_STROKE = Color(0.016, 0.141, 0.2)
GREEN = Color(0.306, 0.655, 0.18)
GREEN_STROKE = Color(0.11, 0.267, 0.051)
DIAMOND_FILL = Color(1.0, 0.957, 0.839)
DIAMOND_STROKE = Color(0.71, 0.518, 0.145)
BODY_TEXT = Color(0.125, 0.145, 0.169)

PAGE_W = 2846.04
PAGE_H = 4200.0
MARGIN = 341.0
CX = PAGE_W / 2  # ~1423

pdfmetrics.registerFont(TTFont("Body", r"C:\Windows\Fonts\calibri.ttf"))
pdfmetrics.registerFont(TTFont("BodyBold", r"C:\Windows\Fonts\calibrib.ttf"))
pdfmetrics.registerFont(TTFont("UI", r"C:\Windows\Fonts\segoeui.ttf"))
pdfmetrics.registerFont(TTFont("UIBold", r"C:\Windows\Fonts\seguisb.ttf"))
pdfmetrics.registerFont(TTFont("Mono", r"C:\Windows\Fonts\consola.ttf"))


# ---------------------------------------------------------------------------
# Primitivas de dibujo
# ---------------------------------------------------------------------------
class FlowPDF:
    def __init__(self, path: Path, title: str):
        self.path = path
        self.title = title
        self.c = canvas.Canvas(str(path), pagesize=(PAGE_W, PAGE_H))
        self._draw_frame()
        self.c.setFont("UIBold", 18)
        self.c.setFillColor(black)
        self.c.drawString(MARGIN + 32, PAGE_H - 34, title)

    def _draw_frame(self):
        self.c.setStrokeColor(NAVY_STROKE)
        self.c.setLineWidth(2.5)
        self.c.rect(MARGIN, 6, PAGE_W - 2 * MARGIN, PAGE_H - 12, stroke=1, fill=0)

    def save(self):
        self.c.save()

    def oval(self, cx, cy, w, h, text, fill=GREEN, stroke=GREEN_STROKE):
        x, y = cx - w / 2, cy - h / 2
        self.c.setFillColor(fill)
        self.c.setStrokeColor(stroke)
        self.c.setLineWidth(1.5)
        self.c.roundRect(x, y, w, h, h / 2, stroke=1, fill=1)
        self.c.setFillColor(white)
        self.c.setFont("UIBold", 16)
        self.c.drawCentredString(cx, cy - 5, text)
        return {"cx": cx, "top": cy + h / 2, "bottom": cy - h / 2, "left": x, "right": x + w}

    def process_box(self, cx, top, w, header, lines, header_h=29, line_h=15, pad=10, font_size=12):
        """Caja con cabecera azul + cuerpo blanco. `top` es el borde superior (coord PDF)."""
        body_lines = []
        for line in lines:
            body_lines.extend(self._wrap(line, w - 2 * pad - 8, font_size))
        body_h = max(40, pad + len(body_lines) * line_h + pad)
        total_h = header_h + body_h
        x = cx - w / 2
        y_top = top
        y_bottom = top - total_h

        # header
        self.c.setFillColor(NAVY)
        self.c.setStrokeColor(NAVY_STROKE)
        self.c.setLineWidth(1.2)
        self.c.rect(x, y_top - header_h, w, header_h, stroke=1, fill=1)
        self.c.setFillColor(white)
        self.c.setFont("UIBold", 14 if len(header) < 55 else 12)
        self.c.drawCentredString(cx, y_top - header_h + 8, header)

        # body
        self.c.setFillColor(white)
        self.c.setStrokeColor(NAVY_STROKE)
        self.c.rect(x, y_bottom, w, body_h, stroke=1, fill=1)

        self.c.setFillColor(BODY_TEXT)
        ty = y_top - header_h - pad - 11
        for line in body_lines:
            font, text = "Body", line
            size = font_size
            if line.startswith("##"):
                font, text, size = "BodyBold", line[2:], font_size + 1
            elif line.startswith("EXCEL|"):
                self._excel_icon(x + pad, ty - 2)
                font, text, size = "Body", line[6:], font_size
                self.c.setFont(font, size)
                self.c.setFillColor(BODY_TEXT)
                self.c.drawString(x + pad + 18, ty, text)
                ty -= line_h
                continue
            self.c.setFont(font, size)
            self.c.setFillColor(BODY_TEXT)
            self.c.drawString(x + pad, ty, text)
            ty -= line_h

        return {
            "cx": cx,
            "top": y_top,
            "bottom": y_bottom,
            "left": x,
            "right": x + w,
            "header_bottom": y_top - header_h,
            "w": w,
            "h": total_h,
        }

    def table_box(self, cx, top, w, header, rows, header_h=29, line_h=14, pad=10, font_size=10):
        """Caja con tabla monoespaciada (contenido alineado como en el .txt)."""
        # Filtrar filas separadoras markdown
        clean = []
        for row in rows:
            cells = [str(c).strip() for c in row]
            if cells and all(set(c) <= set("-: ") and any(ch == "-" for ch in c) for c in cells if c):
                continue
            clean.append(cells)
        if not clean:
            clean = [["(sin datos)"]]
        ncols = max(len(r) for r in clean)
        padded = [r + [""] * (ncols - len(r)) for r in clean]
        widths = [max(len(padded[i][j]) for i in range(len(padded))) for j in range(ncols)]
        mono_lines = ["  ".join(cell.ljust(widths[j]) for j, cell in enumerate(row)) for row in padded]

        body_h = max(40, pad + len(mono_lines) * line_h + pad)
        total_h = header_h + body_h
        x = cx - w / 2
        y_top = top
        y_bottom = top - total_h

        self.c.setFillColor(NAVY)
        self.c.setStrokeColor(NAVY_STROKE)
        self.c.setLineWidth(1.2)
        self.c.rect(x, y_top - header_h, w, header_h, stroke=1, fill=1)
        self.c.setFillColor(white)
        self.c.setFont("UIBold", 14 if len(header) < 55 else 12)
        self.c.drawCentredString(cx, y_top - header_h + 8, header)

        self.c.setFillColor(white)
        self.c.setStrokeColor(NAVY_STROKE)
        self.c.rect(x, y_bottom, w, body_h, stroke=1, fill=1)

        self.c.setFillColor(BODY_TEXT)
        self.c.setFont("Mono", font_size)
        ty = y_top - header_h - pad - 10
        for line in mono_lines:
            self.c.drawString(x + pad, ty, line)
            ty -= line_h

        return {
            "cx": cx,
            "top": y_top,
            "bottom": y_bottom,
            "left": x,
            "right": x + w,
            "header_bottom": y_top - header_h,
            "w": w,
            "h": total_h,
        }

    def diamond(self, cx, cy, w, h, text, font_size=13):
        pts = [
            (cx, cy + h / 2),
            (cx + w / 2, cy),
            (cx, cy - h / 2),
            (cx - w / 2, cy),
        ]
        path = self.c.beginPath()
        path.moveTo(*pts[0])
        for p in pts[1:]:
            path.lineTo(*p)
        path.close()
        self.c.setFillColor(DIAMOND_FILL)
        self.c.setStrokeColor(DIAMOND_STROKE)
        self.c.setLineWidth(1.5)
        self.c.drawPath(path, stroke=1, fill=1)

        self.c.setFillColor(black)
        self.c.setFont("UIBold", font_size)
        lines = self._wrap(text, w * 0.62, font_size)
        start = cy + (len(lines) - 1) * 7
        for i, line in enumerate(lines):
            self.c.drawCentredString(cx, start - i * 14, line)
        return {
            "cx": cx,
            "top": cy + h / 2,
            "bottom": cy - h / 2,
            "left": cx - w / 2,
            "right": cx + w / 2,
            "cy": cy,
        }

    def arrow_down(self, x, y_from, y_to, head=12):
        self.c.setStrokeColor(NAVY)
        self.c.setFillColor(NAVY)
        self.c.setLineWidth(2.2)
        self.c.line(x, y_from, x, y_to + head)
        self._arrowhead_down(x, y_to)

    def arrow_right(self, x_from, x_to, y, head=12):
        self.c.setStrokeColor(NAVY)
        self.c.setFillColor(NAVY)
        self.c.setLineWidth(2.2)
        self.c.line(x_from, y, x_to - head, y)
        self._arrowhead_right(x_to, y, size=head)

    def arrow_left(self, x_from, x_to, y, head=12):
        self.c.setStrokeColor(NAVY)
        self.c.setFillColor(NAVY)
        self.c.setLineWidth(2.2)
        self.c.line(x_from, y, x_to + head, y)
        self._arrowhead_left(x_to, y)

    def polyline(self, points, arrow_end=True):
        """points: list of (x,y). Dibuja segmentos y flecha al final."""
        self.c.setStrokeColor(NAVY)
        self.c.setFillColor(NAVY)
        self.c.setLineWidth(2.4)
        for i in range(len(points) - 1):
            x0, y0 = points[i]
            x1, y1 = points[i + 1]
            if i == len(points) - 2 and arrow_end:
                # acortar último segmento para la punta
                if abs(x1 - x0) < 0.5:  # vertical
                    if y1 < y0:
                        self.c.line(x0, y0, x1, y1 + 12)
                        self._arrowhead_down(x1, y1)
                    else:
                        self.c.line(x0, y0, x1, y1 - 12)
                        self._arrowhead_up(x1, y1)
                elif abs(y1 - y0) < 0.5:  # horizontal
                    if x1 > x0:
                        self.c.line(x0, y0, x1 - 12, y1)
                        self._arrowhead_right(x1, y1)
                    else:
                        self.c.line(x0, y0, x1 + 12, y1)
                        self._arrowhead_left(x1, y1)
                else:
                    self.c.line(x0, y0, x1, y1)
            else:
                self.c.line(x0, y0, x1, y1)

    def label(self, x, y, text, size=12, bold=True):
        self.c.setFillColor(black)
        self.c.setFont("UIBold" if bold else "UI", size)
        self.c.drawString(x, y, text)

    def label_center(self, x, y, text, size=12):
        self.c.setFillColor(black)
        self.c.setFont("UIBold", size)
        self.c.drawCentredString(x, y, text)

    def _arrowhead_down(self, x, y):
        p = self.c.beginPath()
        p.moveTo(x, y)
        p.lineTo(x - 7, y + 14)
        p.lineTo(x + 7, y + 14)
        p.close()
        self.c.drawPath(p, stroke=0, fill=1)

    def _arrowhead_up(self, x, y):
        p = self.c.beginPath()
        p.moveTo(x, y)
        p.lineTo(x - 7, y - 14)
        p.lineTo(x + 7, y - 14)
        p.close()
        self.c.drawPath(p, stroke=0, fill=1)

    def _arrowhead_right(self, x, y, size=14):
        p = self.c.beginPath()
        p.moveTo(x, y)
        p.lineTo(x - size, y + size / 2)
        p.lineTo(x - size, y - size / 2)
        p.close()
        self.c.drawPath(p, stroke=0, fill=1)

    def _arrowhead_left(self, x, y):
        p = self.c.beginPath()
        p.moveTo(x, y)
        p.lineTo(x + 14, y + 7)
        p.lineTo(x + 14, y - 7)
        p.close()
        self.c.drawPath(p, stroke=0, fill=1)

    def _excel_icon(self, x, y):
        self.c.setFillColor(GREEN)
        self.c.setStrokeColor(GREEN_STROKE)
        self.c.setLineWidth(0.8)
        self.c.roundRect(x, y, 12, 12, 1.5, stroke=1, fill=1)
        self.c.setFillColor(white)
        self.c.setFont("UIBold", 7)
        self.c.drawCentredString(x + 6, y + 3, "X")

    def _wrap(self, text: str, max_w: float, font_size: int) -> list[str]:
        if text.startswith("EXCEL|") or text.startswith("##"):
            return [text]
        if not text:
            return [""]
        self.c.setFont("Body", font_size)
        words = text.split(" ")
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if self.c.stringWidth(trial, "Body", font_size) <= max_w:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines or [""]



def branch_from_diamond(pdf, d, left_cx, right_cx, branch_top, lab_l="SI", lab_r="NO"):
    """SI/NO salen por vertices laterales HACIA AFUERA y luego bajan a las cajas."""
    # Forzar codo fuera del rombo (evita flecha invertida si left/right_cx cae en el tip)
    out_l = min(left_cx, d["left"] - 50)
    out_r = max(right_cx, d["right"] + 50)
    pdf.polyline([
        (d["left"], d["cy"]),
        (out_l, d["cy"]),
        (left_cx, d["cy"]),
        (left_cx, branch_top + 2),
    ])
    pdf.label(min(d["left"] - 70, (d["left"] + left_cx) / 2 - 10), d["cy"] + 16, lab_l)
    pdf.polyline([
        (d["right"], d["cy"]),
        (out_r, d["cy"]),
        (right_cx, d["cy"]),
        (right_cx, branch_top + 2),
    ])
    pdf.label(max(d["right"] + 50, (d["right"] + right_cx) / 2 - 10), d["cy"] + 16, lab_r)


def enter_box_header_sides(pdf, box, left_src, right_src, rail=60):
    """Entra al centro de la barra azul por laterales, con codos cortos y alineados."""
    hdr_cy = (box["top"] + box["header_bottom"]) / 2
    # Puente justo encima de la caja (enlace corto, sin U enorme)
    route_y = max(box["top"] + 28, min(left_src["bottom"], right_src["bottom"]) - 20)
    if route_y >= min(left_src["bottom"], right_src["bottom"]):
        route_y = (min(left_src["bottom"], right_src["bottom"]) + box["top"]) / 2

    left_rail = min(left_src["cx"], box["left"] - rail)
    right_rail = max(right_src["cx"], box["right"] + rail)
    outer = max(box["left"] - left_rail, right_rail - box["right"], rail)
    left_rail = box["left"] - outer
    right_rail = box["right"] + outer

    pdf.polyline([
        (left_src["cx"], left_src["bottom"]),
        (left_src["cx"], route_y),
        (left_rail, route_y),
        (left_rail, hdr_cy),
        (box["left"], hdr_cy),
    ])
    pdf.polyline([
        (right_src["cx"], right_src["bottom"]),
        (right_src["cx"], route_y),
        (right_rail, route_y),
        (right_rail, hdr_cy),
        (box["right"], hdr_cy),
    ])


def crop_pdf_below_fin(path: Path, padding: float = 40.0):
    """Recorta el espacio en blanco sobrante debajo de FIN."""
    import fitz

    src = fitz.open(path)
    page = src[0]
    fin_bottom = None
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            text = "".join(span["text"] for span in line["spans"]).strip()
            if text == "FIN":
                # Incluir el ovalo verde alrededor del texto
                fin_bottom = max(fin_bottom or 0, line["bbox"][3] + 22)
    if fin_bottom is None:
        src.close()
        return
    new_h = min(page.rect.height, fin_bottom + padding)
    if new_h >= page.rect.height - 8:
        src.close()
        return
    dst = fitz.open()
    new_page = dst.new_page(width=page.rect.width, height=new_h)
    new_page.show_pdf_page(
        new_page.rect,
        src,
        0,
        clip=fitz.Rect(0, 0, page.rect.width, new_h),
    )
    # Remarcar marco (el borde inferior original queda fuera del recorte)
    new_page.draw_rect(
        fitz.Rect(MARGIN, 4, page.rect.width - MARGIN, new_h - 4),
        color=(0.016, 0.141, 0.2),
        width=2.5,
    )
    src.close()
    tmp = path.with_suffix(".crop.pdf")
    dst.save(tmp, deflate=True)
    dst.close()
    tmp.replace(path)


def connect_si_to_filtro(pdf, d4, b_filtro, label="SÍ"):
    """Flecha horizontal a la derecha desde el rombo al lateral del filtro."""
    # PDF: top > bottom
    y = d4["cy"] if b_filtro["bottom"] <= d4["cy"] <= b_filtro["top"] else (b_filtro["top"] + b_filtro["bottom"]) / 2
    pdf.arrow_right(d4["right"], b_filtro["left"], y, head=14)
    pdf.label((d4["right"] + b_filtro["left"]) / 2 - 8, y + 14, label)


def connect_filtro_to_continuar(pdf, b_filtro, b_cont):
    """Desde el filtro hasta el centro de la barra azul de Continuar (lateral derecho)."""
    hdr_cy = (b_cont["top"] + b_cont["header_bottom"]) / 2
    pdf.polyline([
        (b_filtro["cx"], b_filtro["bottom"]),
        (b_filtro["cx"], hdr_cy),
        (b_cont["right"], hdr_cy),
    ])



def connect_vertical(pdf: FlowPDF, box_a, box_b, gap_label=None):
    pdf.arrow_down(box_a["cx"], box_a["bottom"] - 2, box_b["top"] + 2)
    if gap_label:
        mid = (box_a["bottom"] + box_b["top"]) / 2
        pdf.label(box_a["cx"] + 10, mid - 4, gap_label)


# ---------------------------------------------------------------------------
# Plantilla común (estructura idéntica al PDF de ejemplo)
# ---------------------------------------------------------------------------

def _draw_loops_and_end(pdf, cx, b10, b5, b3, out_path):
    """Bucles IM/CP y FIN — secuencia identica al PDF de ejemplo."""
    y = b10["bottom"] - 50
    d5 = pdf.diamond(
        cx,
        y - 42,
        496,
        84,
        "¿Quedan modos de fallo por analizar para el mismo activo?",
        font_size=12,
    )
    pdf.arrow_down(cx, b10["bottom"] - 2, d5["top"] + 2)

    im_cx = cx - 260
    im_top = d5["bottom"] - 35
    pdf.polyline([(d5["left"], d5["cy"]), (im_cx, d5["cy"]), (im_cx, im_top + 2)])
    pdf.label(im_cx - 28, d5["cy"] + 10, "SÍ")

    b_im = pdf.process_box(
        im_cx,
        im_top,
        402,
        "Continuar la iteración IM",
        [
            "IM = IM + 1",
            "Volver al paso 5",
            "Extraer el siguiente Modo de fallo / Modo de parada",
            "Continuar desde el paso 5b en adelante",
        ],
        font_size=11,
        line_h=14,
    )

    loop_im_x = MARGIN + 80
    pdf.polyline(
        [
            (b_im["left"], (b_im["top"] + b_im["bottom"]) / 2),
            (loop_im_x, (b_im["top"] + b_im["bottom"]) / 2),
            (loop_im_x, (b5["top"] + b5["bottom"]) / 2),
            (b5["left"], (b5["top"] + b5["bottom"]) / 2),
        ]
    )
    pdf.label(loop_im_x + 8, (b5["bottom"] + b_im["top"]) / 2, "<- IM", size=11)

    y = min(b_im["bottom"], d5["bottom"]) - 55
    d6 = pdf.diamond(
        cx,
        y - 42,
        496,
        84,
        "¿Quedan Activos Físicos u Operacionales por analizar?",
        font_size=12,
    )
    pdf.polyline([(d5["cx"], d5["bottom"]), (d5["cx"], d6["top"] + 2)])
    pdf.label(d5["cx"] + 12, (d5["bottom"] + d6["top"]) / 2 - 4, "NO")

    # Caja CP alineada al eje del rombo: flecha SÍ horizontal, larga y recta
    cp_w = 400
    cp_gap = 130
    cp_lines = [
        "CP = CP + 1",
        "Volver al paso 3",
        "Extraer el siguiente Activo Físico u Operacional",
        "y su Tipo de UO",
        "Continuar desde el paso 4 en adelante",
    ]
    # Estimar alto permitiendo un wrap de línea
    cp_h_est = 29 + 10 + (len(cp_lines) + 1) * 13 + 10
    cp_cx = d6["right"] + cp_gap + cp_w / 2
    cp_top = d6["cy"] + cp_h_est / 2
    b_cp = pdf.process_box(
        cp_cx,
        cp_top,
        cp_w,
        "Continuar la iteración CP",
        cp_lines,
        font_size=11,
        line_h=13,
    )
    # Flecha al eje del rombo (misma Y), no al centro estimado de la caja
    pdf.arrow_right(d6["right"], b_cp["left"], d6["cy"], head=16)
    pdf.label((d6["right"] + b_cp["left"]) / 2 - 8, d6["cy"] + 14, "SÍ")
    mid_cp = (b_cp["top"] + b_cp["bottom"]) / 2

    loop_cp_x = PAGE_W - MARGIN - 70
    pdf.polyline(
        [
            (b_cp["right"], mid_cp),
            (loop_cp_x, mid_cp),
            (loop_cp_x, (b3["top"] + b3["bottom"]) / 2),
            (b3["right"], (b3["top"] + b3["bottom"]) / 2),
        ]
    )
    pdf.label(loop_cp_x - 42, (b3["bottom"] + b_cp["top"]) / 2, "CP ?", size=11)

    fin = pdf.oval(d6["cx"], min(b_cp["bottom"], d6["bottom"]) - 55, 98, 36, "FIN")
    pdf.polyline([(d6["cx"], d6["bottom"]), (d6["cx"], fin["top"] + 2)])
    pdf.label(d6["cx"] + 12, (d6["bottom"] + fin["top"]) / 2 - 4, "NO")

    pdf.save()
    crop_pdf_below_fin(out_path)
    print("OK", out_path)


def build_calado_like(
    out_path: Path,
    title: str,
    *,
    step3_extra: list[str],
    step4_lines: list[str],
    step5_lines: list[str],
    step5b_modelo: str,
    step5b_tipo: str,
    step6_extra: list[str],
    step7_predef_note: str,
    step7_por_umbral_title: str = "Seleccionar por umbral",
    step7_por_umbral_lines: list[str] | None = None,
    step8_header: str,
    step8_lines: list[str],
    step9_table: list[list[str]],
    step10_lines: list[str],
):
    if step7_por_umbral_lines is None:
        step7_por_umbral_lines = [
            "Indicador que contenga el umbral",
            "obtenido en el paso 6 (o el del",
            "diagrama si no hay Excel en 5b).",
        ]
    pdf = FlowPDF(out_path, title)
    cx = CX
    main_w = 520
    y = PAGE_H - 55

    # INICIO
    inicio = pdf.oval(cx, y - 18, 98, 36, "INICIO")
    y = inicio["bottom"] - 28

    # 1
    b1 = pdf.process_box(
        cx,
        y,
        302,
        "1. Carga archivos de entrada",
        [
            "##data_modelos",
            "EXCEL|1_Configuración_del_puerto",
            "EXCEL|2_Relación_umbrales_y_curvas_de_daño_vs_activos",
            "EXCEL|3_Indicadores_climáticos",
            "EXCEL|4_Relación_modelos_activos_e_indicadores",
            "EXCEL|Relación_impactos_variables_climáticas",
        ],
        line_h=14,
        font_size=11,
    )
    connect_vertical(pdf, inicio, b1)
    y = b1["bottom"] - 28

    # 2
    b2 = pdf.process_box(
        cx,
        y,
        302,
        "2. Configuración del cálculo",
        [
            "El percentil y el modo de selección del",
            "indicador se resuelven en el paso 5b",
            "(por iteración IM), no de forma global",
            "al inicio.",
        ],
        font_size=12,
        line_h=16,
    )
    connect_vertical(pdf, b1, b2)
    y = b2["bottom"] - 28

    # 3
    b3 = pdf.process_box(
        cx,
        y,
        324,
        "3. Iteración por Activos (CP)",
        [
            "Entrar al Excel:",
            "EXCEL|1_Configuración_del_puerto",
            "Recorrer cada Activo Físico u Operacional.",
            "Para cada activo, extraer:",
            "• Activo Físico u Operacional",
            "• Tipo de UO asociado",
            *step3_extra,
        ],
        font_size=12,
        line_h=15,
    )
    connect_vertical(pdf, b2, b3)
    y = b3["bottom"] - 28

    # 4
    b4 = pdf.process_box(
        cx,
        y,
        346,
        "4. Buscar impactos asociados al activo",
        step4_lines,
        font_size=12,
        line_h=15,
    )
    connect_vertical(pdf, b3, b4)
    y = b4["bottom"] - 28

    # 5
    b5 = pdf.process_box(
        cx,
        y,
        346,
        "5. Iteración por Modos de fallo (IM)",
        step5_lines,
        font_size=12,
        line_h=15,
    )
    connect_vertical(pdf, b4, b5)
    y = b5["bottom"] - 28

    # 5b
    b5b = pdf.process_box(
        cx,
        y,
        521,
        "5.b ¿Existe regla en Relacion_modelos_activos_e_indicadores.xlsx?",
        [
            "Entrar al Excel:",
            "EXCEL|4_Relación_modelos_activos_e_indicadores",
            "Revisar cuántos indicadores tiene asociados",
            "en la columna No indicadores.",
            "Buscar una fila explícita que coincida con:",
            f"1. Modelo ({step5b_modelo})",
            "2. Activo Físico u Operacional (si está definido)",
            "3. Modo de fallo / Modo de parada",
            "4. Variable climática",
            f"5. Tipo de impacto {step5b_tipo}",
            "La fila debe tener modo de fallo y variable",
            "explícitos (no comodines).",
        ],
        font_size=11,
        line_h=14,
        header_h=29,
    )
    connect_vertical(pdf, b5, b5b)
    y = b5b["bottom"] - 40

    # Diamante ¿Fila definida?
    d1 = pdf.diamond(cx, y - 34, 200, 70, "¿Fila definida?")
    pdf.arrow_down(cx, b5b["bottom"] - 2, d1["top"] + 2)

    # Ramas bien separadas (fuera del rombo)
    left_cx = cx - 500
    right_cx = cx + 420
    branch_top = d1["bottom"] - 50
    branch_from_diamond(pdf, d1, left_cx, right_cx, branch_top, "SI", "NO")

    b_si = pdf.process_box(
        left_cx,
        branch_top,
        280,
        "Usar la configuracion del Excel",
        [
            "• Percentil",
            "• Selecci\u00f3n indicador (Por umbral / Predefinido)",
            "• Indicador clim\u00e1tico (si es predefinido)",
        ],
        font_size=11,
        line_h=15,
    )
    b_no = pdf.process_box(
        right_cx,
        branch_top,
        280,
        "Seguir la logica clasica del diagrama",
        [
            "• Percentil por defecto: P99",
            "• Indicador: por umbral",
            "• Filtros adicionales del paso 7",
            "  si hay varios candidatos",
            "##Continuar al paso 6",
        ],
        font_size=11,
        line_h=14,
    )

    # Diamante indicador predefinido (bajo rama SI)
    y_pred = b_si["bottom"] - 50
    d2 = pdf.diamond(left_cx, y_pred - 36, 240, 64, "¿Indicador predefinido en el Excel?", font_size=11)
    pdf.arrow_down(left_cx, b_si["bottom"] - 2, d2["top"] + 2)

    # Sub-ramas FUERA del tip del rombo (half=120 => offset > 120 + mitad caja)
    sub_top = d2["bottom"] - 45
    sub_left = left_cx - 250
    sub_right = left_cx + 250
    branch_from_diamond(pdf, d2, sub_left, sub_right, sub_top, "SI", "NO")

    b_omit = pdf.process_box(
        sub_left,
        sub_top,
        190,
        "Omitir el paso 6",
        [
            "Ir directamente al paso 7.",
            "No se busca umbral numerico.",
            "Se usa el indicador climatico",
            "predefinido en el Excel.",
        ],
        font_size=11,
        line_h=13,
        header_h=26,
    )
    b_umbral = pdf.process_box(
        sub_right,
        sub_top,
        190,
        "Continuar por umbral",
        [
            "Continuar al paso 6 (umbral).",
            "Despues, ir al paso 7 con el",
            "percentil definido en el Excel.",
        ],
        font_size=11,
        line_h=13,
        header_h=26,
    )

    # Paso 6 justo debajo (enlace corto a laterales)
    y6 = min(b_no["bottom"], b_omit["bottom"], b_umbral["bottom"]) - 90
    b6 = pdf.process_box(
        cx,
        y6,
        553,
        "6. Buscar el umbral correspondiente",
        [
            "(Omitir si en el paso 5b el Excel fijo un indicador predefinido)",
            "Entrar al Excel:",
            "EXCEL|2_Relacion_umbrales_y_curvas_de_dano_vs_activos",
            "Aplicar los filtros:",
            "1. Activo Fisico u Operacional",
            "2. Modo de fallo / Modo de parada",
            "Seleccionar el umbral:",
            "• Si existe columna del Tipo de UO con valor -> usarla",
            "• Si esta vacia / no existe -> usar Umbral General",
            *step6_extra,
            "Extraer: Activo, Modo de fallo, Variable climatica, Umbral",
        ],
        font_size=11,
        line_h=14,
    )

    # Entrada al paso 6: centro de la barra azul por los laterales
    enter_box_header_sides(pdf, b6, left_src=b_umbral, right_src=b_no)

    skip_x = MARGIN + 120
    y = b6["bottom"] - 35

    b7 = pdf.process_box(
        cx,
        y,
        467,
        "7. Buscar el indicador climatico",
        [
            "Entrar al Excel:",
            "EXCEL|3_Indicadores_climaticos",
            "Aplicar los filtros:",
            "1. Variable climatica",
            "2. Percentil (del Excel en 5b, o P99)",
        ],
        font_size=12,
        line_h=15,
    )
    connect_vertical(pdf, b6, b7)

    # Skip omitir -> paso 7 por la izquierda
    pdf.polyline([
        (b_omit["left"], (b_omit["top"] + b_omit["bottom"]) / 2),
        (skip_x, (b_omit["top"] + b_omit["bottom"]) / 2),
        (skip_x, (b7["top"] + b7["bottom"]) / 2),
        (b7["left"], (b7["top"] + b7["bottom"]) / 2),
    ])
    pdf.label(skip_x + 8, (b_omit["bottom"] + b7["top"]) / 2, "-> paso 7", size=10)

    y = b7["bottom"] - 50
    d3 = pdf.diamond(cx, y - 36, 300, 70, "¿Como se selecciona el indicador?", font_size=12)
    pdf.arrow_down(cx, b7["bottom"] - 2, d3["top"] + 2)

    pred_cx = cx - 360
    umb_cx = cx + 300
    sel_top = d3["bottom"] - 45
    branch_from_diamond(pdf, d3, pred_cx, umb_cx, sel_top, "Predefinido", "Por umbral")

    b_pred = pdf.process_box(
        pred_cx,
        sel_top,
        280,
        "Usar indicador predefinido",
        [
            "Usar el indicador definido en",
            "4_Relacion_modelos_activos_e_indicadores",
            step7_predef_note,
        ],
        font_size=11,
        line_h=13,
        header_h=26,
    )
    b_por = pdf.process_box(
        umb_cx,
        sel_top,
        300,
        step7_por_umbral_title,
        step7_por_umbral_lines,
        font_size=11,
        line_h=13,
        header_h=26,
    )

    y = min(b_pred["bottom"], b_por["bottom"]) - 50
    d4 = pdf.diamond(cx, y - 36, 340, 72, "¿Existe mas de un indicador?", font_size=12)
    mid_y = (min(b_pred["bottom"], b_por["bottom"]) + d4["top"]) / 2
    pdf.polyline([(b_pred["cx"], b_pred["bottom"]), (b_pred["cx"], mid_y), (cx, mid_y), (cx, d4["top"] + 2)])
    # Bajar hasta la línea de fusión y unir horizontalmente hacia el centro
    pdf.polyline([(b_por["cx"], b_por["bottom"]), (b_por["cx"], mid_y), (cx, mid_y)], arrow_end=False)

    # SI -> filtro a la DERECHA (flecha horizontal); NO -> Continuar debajo
    filtro_w = 240
    filtro_cx = cx + 420
    # Alinear verticalmente el filtro al eje del rombo
    filtro_h_est = 26 + 10 + 14 + 10
    filtro_top = d4["cy"] + filtro_h_est / 2
    b_filtro = pdf.process_box(
        filtro_cx,
        filtro_top,
        filtro_w,
        "Aplicar un segundo filtro",
        ["• Indicador que contenga el Tipo de UO"],
        font_size=11,
        line_h=14,
        header_h=26,
    )
    connect_si_to_filtro(pdf, d4, b_filtro, label="SI")

    cont_top = min(d4["bottom"], b_filtro["bottom"]) - 70
    pdf.arrow_down(cx, d4["bottom"] - 2, cont_top + 2)
    pdf.label(cx + 18, d4["bottom"] - 22, "NO")

    b_cont = pdf.process_box(
        cx,
        cont_top,
        420,
        "Continuar y extraer los valores",
        [
            "• Valor del escenario Hist\u00f3rico",
            "• Valores de todos los escenarios futuros",
            "##Criterio espacial:",
            "Si existen varios puntos o indicadores candidatos,",
            "seleccionar el indicador cuya Lon/Lat est\u00e9 m\u00e1s cerca",
            "del centroide del \u00e1rea donde se localiza el activo.",
        ],
        font_size=11,
        line_h=14,
    )
    # filtro vuelve al flujo: flecha al centro de la barra azul de Continuar
    connect_filtro_to_continuar(pdf, b_filtro, b_cont)

    y = b_cont["bottom"] - 28
    b8 = pdf.process_box(cx, y, 467, step8_header, step8_lines, font_size=12, line_h=15)
    connect_vertical(pdf, b_cont, b8)

    y = b8["bottom"] - 28
    b9 = pdf.table_box(cx, y, 560, "9. Generar la tabla de resultados", step9_table, font_size=10, line_h=14)
    connect_vertical(pdf, b8, b9)

    y = b9["bottom"] - 28
    b10 = pdf.process_box(cx, y, 467, "10. Interpretar el resultado", step10_lines, font_size=12, line_h=15)
    connect_vertical(pdf, b9, b10)

    _draw_loops_and_end(pdf, cx, b10, b5, b3, out_path)



def build_francobordo(out_path: Path):
    """PI Falta de Francobordo — misma estructura visual, lógica Fb."""
    pdf = FlowPDF(out_path, "DIAGRAMA DE FLUJO ? PI FALTA DE FRANCOBORDO")
    cx = CX
    y = PAGE_H - 55

    inicio = pdf.oval(cx, y - 18, 98, 36, "INICIO")
    y = inicio["bottom"] - 28

    b1 = pdf.process_box(
        cx, y, 302, "1. Carga archivos de entrada",
        [
            "##data_modelos",
            "EXCEL|1_Configuración_del_puerto",
            "EXCEL|2_Relación_umbrales_y_curvas_de_daño_vs_activos",
            "EXCEL|3_Indicadores_climáticos",
            "EXCEL|4_Relación_modelos_activos_e_indicadores",
            "EXCEL|Relación_impactos_variables_climáticas",
        ],
        line_h=14, font_size=11,
    )
    connect_vertical(pdf, inicio, b1)
    y = b1["bottom"] - 28

    b2 = pdf.process_box(
        cx, y, 302, "2. Configuración del cálculo",
        [
            "El percentil y el modo de selección del",
            "indicador se resuelven en el paso 5b",
            "(por iteración IM), no de forma global",
            "al inicio.",
        ],
        font_size=12, line_h=16,
    )
    connect_vertical(pdf, b1, b2)
    y = b2["bottom"] - 28

    b3 = pdf.process_box(
        cx, y, 324, "3. Iteración por Activos (CP)",
        [
            "Entrar al Excel:",
            "EXCEL|1_Configuración_del_puerto",
            "Recorrer cada Activo Físico u Operacional.",
            "Para cada activo, extraer:",
            "• Activo Físico u Operacional",
            "• Tipo de UO asociado",
            "• FB (francobordo del activo)",
        ],
        font_size=12, line_h=15,
    )
    connect_vertical(pdf, b2, b3)
    y = b3["bottom"] - 28

    b4 = pdf.process_box(
        cx, y, 346, "4. Buscar impactos asociados al activo",
        [
            "Entrar al Excel:",
            "EXCEL|Relación_impactos_variables_climáticas",
            "Buscar:",
            "Activo Físico u Operacional = Activo de la",
            "iteración CP",
            "Extraer:",
            "• Todas las filas coincidentes del activo",
            "  (p. ej. modo Falta de Francobordo)",
        ],
        font_size=12, line_h=15,
    )
    connect_vertical(pdf, b3, b4)
    y = b4["bottom"] - 28

    b5 = pdf.process_box(
        cx, y, 346, "5. Iteración por Modos de fallo (IM)",
        [
            "Sobre la tabla filtrada obtenida en el paso 4.",
            "Recorrer cada fila coincidente.",
            "Para cada fila, extraer:",
            "• Modo de fallo / Modo de parada",
            "• Variable climática",
            "• Tipo de impacto (p. ej. ELO, ELS)",
        ],
        font_size=12, line_h=15,
    )
    connect_vertical(pdf, b4, b5)
    y = b5["bottom"] - 28

    b5b = pdf.process_box(
        cx, y, 521, "5.b ¿Existe regla en Relacion_modelos_activos_e_indicadores.xlsx?",
        [
            "Entrar al Excel:",
            "EXCEL|4_Relación_modelos_activos_e_indicadores",
            "Buscar una fila explícita que coincida con:",
            "1. Modelo (PI falta de francobordo)",
            "2. Activo Físico u Operacional (si está definido)",
            "3. Modo de fallo / Modo de parada",
            "4. Variable climática",
            "5. Tipo de impacto (si está definido en la fila)",
            "Columna Selección indicador:",
            "• predefinido ? indicador fijado en el Excel",
            "• no predefinido ? reglas del paso 7",
            "  (Fb / umbral + inundación costera en atraque)",
            "La fila debe tener modo de fallo y variable",
            "explícitos (no comodines).",
        ],
        font_size=11, line_h=13,
    )
    connect_vertical(pdf, b5, b5b)
    y = b5b["bottom"] - 40

    # Diamante ¿Fila definida?
    d1 = pdf.diamond(cx, y - 34, 200, 70, "¿Fila definida?")
    pdf.arrow_down(cx, b5b["bottom"] - 2, d1["top"] + 2)

    left_cx = cx - 500
    right_cx = cx + 420
    branch_top = d1["bottom"] - 50
    branch_from_diamond(pdf, d1, left_cx, right_cx, branch_top, "SÍ", "NO")

    b_si = pdf.process_box(
        left_cx, branch_top, 280, "Usar la configuración del Excel",
        [
            "• Percentil",
            "• Selección indicador (predefinido / no)",
            "• Indicador climático (si es predefinido)",
        ],
        font_size=11, line_h=15,
    )
    b_no = pdf.process_box(
        right_cx, branch_top, 280, "Seguir la lógica clásica del diagrama",
        [
            "• Percentil por defecto: P99",
            "• Indicador: no predefinido",
            "  (reglas Fb / umbral del paso 7)",
            "• Continuar según valor de Fb",
            "##Continuar a pasos 6 y 7",
        ],
        font_size=11, line_h=14,
    )

    # Diamante indicador predefinido (bajo rama SÍ)
    y_pred = b_si["bottom"] - 50
    d2 = pdf.diamond(left_cx, y_pred - 36, 240, 64, "¿Indicador predefinido en el Excel?", font_size=11)
    pdf.arrow_down(left_cx, b_si["bottom"] - 2, d2["top"] + 2)

    # Sub-ramas fuera del tip del rombo (sin solape Omitir / Continuar según Fb)
    sub_top = d2["bottom"] - 45
    sub_left = left_cx - 250
    sub_right = left_cx + 250
    branch_from_diamond(pdf, d2, sub_left, sub_right, sub_top, "SÍ", "NO")

    b_omit = pdf.process_box(
        sub_left, sub_top, 190, "Omitir el paso 6",
        [
            "Ir directamente al paso 7.",
            "No se busca umbral numérico",
            "ni Fb como referencia.",
            "Se usa el indicador predefinido.",
        ],
        font_size=11, line_h=13, header_h=26,
    )
    b_fb = pdf.process_box(
        sub_right, sub_top, 190, "Continuar según Fb",
        [
            "Continuar según valor de Fb",
            "en Configuración del puerto",
            "(pasos 6 y 7).",
        ],
        font_size=11, line_h=13, header_h=26,
    )

    # Paso 6 claramente DEBAJO de omitir / Fb / lógica clásica
    # Paso 6 justo debajo (enlace corto a laterales)
    y6 = min(b_no["bottom"], b_omit["bottom"], b_fb["bottom"]) - 90
    b6 = pdf.process_box(
        cx, y6, 553, "6. Buscar el umbral correspondiente",
        [
            "(Solo si el indicador NO es predefinido Y la columna Fb",
            "del activo en Configuración del puerto está vacía)",
            "Si Fb tiene valor numérico ? omitir este paso y usar Fb",
            "como referencia en el paso 7.",
            "Entrar al Excel:",
            "EXCEL|2_Relación_umbrales_y_curvas_de_daño_vs_activos",
            "Filtros: 1) Activo  2) Modo de fallo / Modo de parada",
            "• Columna Tipo de UO con valor ? usarla",
            "• Si vacía / no existe ? «Umbral General»",
            "Extraer: Activo, Modo de fallo, Variable, Umbral",
        ],
        font_size=11, line_h=13,
    )
    # Entrada al paso 6: centro de la barra azul por los laterales
    enter_box_header_sides(pdf, b6, left_src=b_fb, right_src=b_no)

    skip_x = MARGIN + 120
    y = b6["bottom"] - 35
    b7 = pdf.process_box(
        cx, y, 520, "7. Buscar el indicador climático",
        [
            "Entrar al Excel:",
            "EXCEL|3_Indicadores_climáticos",
            "Filtros: 1) Variable climática  2) Percentil (5b o P99)",
            "##Determinar la referencia numérica:",
            "A) Si Fb tiene valor en Configuración del puerto:",
            "   Referencia = Fb del activo (no usar umbral del paso 6)",
            "B) Si Fb está vacía:",
            "   Referencia = umbral obtenido en el paso 6",
            "Buscar indicadores que contengan:",
            "• «inundación costera en un atraque»",
            "Elegir el menor valor ? referencia (Fb o umbral).",
        ],
        font_size=11, line_h=13,
    )
    connect_vertical(pdf, b6, b7)
    pdf.polyline([
        (b_omit["left"], (b_omit["top"] + b_omit["bottom"]) / 2),
        (skip_x, (b_omit["top"] + b_omit["bottom"]) / 2),
        (skip_x, (b7["top"] + b7["bottom"]) / 2),
        (b7["left"], (b7["top"] + b7["bottom"]) / 2),
    ])
    pdf.label(skip_x + 8, (b_omit["bottom"] + b7["top"]) / 2, "→ paso 7", size=10)

    y = b7["bottom"] - 50
    d3 = pdf.diamond(cx, y - 36, 300, 70, "¿Cómo se selecciona el indicador?", font_size=12)
    pdf.arrow_down(cx, b7["bottom"] - 2, d3["top"] + 2)

    pred_cx = cx - 360
    umb_cx = cx + 300
    sel_top = d3["bottom"] - 45
    branch_from_diamond(pdf, d3, pred_cx, umb_cx, sel_top, "Predefinido", "No predefinido")

    b_pred = pdf.process_box(
        pred_cx, sel_top, 280, "Usar indicador predefinido",
        [
            "Usar el indicador definido en",
            "4_Relación_modelos_activos_e_indicadores",
        ],
        font_size=11, line_h=13, header_h=26,
    )
    b_por = pdf.process_box(
        umb_cx, sel_top, 300, "Reglas Fb / umbral",
        [
            "Usar referencia (Fb o umbral) y",
            "«inundación costera en un atraque»",
            "según el criterio del paso 7.",
        ],
        font_size=11, line_h=13, header_h=26,
    )

    y = min(b_pred["bottom"], b_por["bottom"]) - 50
    d4 = pdf.diamond(cx, y - 36, 340, 72, "¿Existe más de un indicador?", font_size=12)
    mid_y = (min(b_pred["bottom"], b_por["bottom"]) + d4["top"]) / 2
    pdf.polyline([(b_pred["cx"], b_pred["bottom"]), (b_pred["cx"], mid_y), (cx, mid_y), (cx, d4["top"] + 2)])
    # Bajar hasta la línea de fusión y unir horizontalmente hacia el centro
    pdf.polyline([(b_por["cx"], b_por["bottom"]), (b_por["cx"], mid_y), (cx, mid_y)], arrow_end=False)

    # SÍ -> filtro a la DERECHA (flecha horizontal); NO -> Continuar debajo
    filtro_w = 240
    filtro_cx = cx + 420
    filtro_h_est = 26 + 10 + 14 + 10
    filtro_top = d4["cy"] + filtro_h_est / 2
    b_filtro = pdf.process_box(
        filtro_cx, filtro_top, filtro_w, "Aplicar un segundo filtro",
        ["• Indicador que contenga el Tipo de UO"],
        font_size=11, line_h=14, header_h=26,
    )
    connect_si_to_filtro(pdf, d4, b_filtro, label="SÍ")

    cont_top = min(d4["bottom"], b_filtro["bottom"]) - 70
    pdf.arrow_down(cx, d4["bottom"] - 2, cont_top + 2)
    pdf.label(cx + 18, d4["bottom"] - 22, "NO")
    b_cont = pdf.process_box(
        cx, cont_top, 420, "Continuar y extraer los valores",
        [
            "• Valor del escenario Histórico",
            "• Valores de todos los escenarios futuros",
            "##Criterio espacial:",
            "Si existen varios puntos o indicadores candidatos,",
            "seleccionar el indicador cuya Lon/Lat esté más cerca",
            "del centroide del área donde se localiza el activo.",
        ],
        font_size=11, line_h=14,
    )
    connect_filtro_to_continuar(pdf, b_filtro, b_cont)

    y = b_cont["bottom"] - 28
    b8 = pdf.process_box(
        cx, y, 467, "8. Calcular la variación",
        [
            "Para cada escenario:",
            "Variación = Indicador del escenario ? Indicador Histórico",
            "Donde: Histórico ? Variación = 0",
        ],
        font_size=12, line_h=15,
    )
    connect_vertical(pdf, b_cont, b8)

    y = b8["bottom"] - 28
    b9 = pdf.table_box(
        cx, y, 520, "9. Generar la tabla de resultados",
        [
            ["Escenario", "Indicador", "Variación"],
            ["Histórico", "Valor", "0"],
            ["SSP2-4.5 2040", "Valor", "Futuro - Histórico"],
            ["SSP5-8.5 2040", "Valor", "Futuro - Histórico"],
            ["...", "...", "..."],
        ],
        font_size=10, line_h=14,
    )
    connect_vertical(pdf, b8, b9)

    y = b9["bottom"] - 28
    b10 = pdf.process_box(
        cx, y, 467, "10. Interpretar el resultado",
        [
            "Según el tipo de indicador.",
            "Ejemplo: horas de cierre / días de inundación en atraque",
            "• Variación > 0 ? Empeora",
            "• Variación < 0 ? Mejora",
            "• Variación = 0 ? Sin cambios",
        ],
        font_size=12, line_h=15,
    )
    connect_vertical(pdf, b9, b10)

    _draw_loops_and_end(pdf, cx, b10, b5, b3, out_path)


def build_precipitacion(out_path: Path):
    """PI Exceso de precipitación: misma cadena que superación, sin umbral;
    Excel 4 define 1 o 2 indicadores predefinidos."""
    pdf = FlowPDF(out_path, "DIAGRAMA DE FLUJO ? PI EXCESO DE PRECIPITACIÓN")
    cx = CX
    y = PAGE_H - 55

    inicio = pdf.oval(cx, y - 18, 98, 36, "INICIO")
    y = inicio["bottom"] - 28

    b1 = pdf.process_box(
        cx,
        y,
        302,
        "1. Carga archivos de entrada",
        [
            "##data_modelos",
            "EXCEL|1_Configuración_del_puerto",
            "EXCEL|2_Relación_umbrales_y_curvas_de_daño_vs_activos",
            "EXCEL|3_Indicadores_climáticos",
            "EXCEL|4_Relación_modelos_activos_e_indicadores",
            "EXCEL|Relación_impactos_variables_climáticas",
        ],
        line_h=14,
        font_size=11,
    )
    connect_vertical(pdf, inicio, b1)
    y = b1["bottom"] - 28

    b2 = pdf.process_box(
        cx,
        y,
        340,
        "2. Configuración del cálculo",
        [
            "El percentil se resuelve en el paso 5b",
            "(por iteración IM).",
            "Selección de indicador: siempre Predefinido",
            "(Excel 4); no hay búsqueda por umbral.",
        ],
        font_size=12,
        line_h=16,
    )
    connect_vertical(pdf, b1, b2)
    y = b2["bottom"] - 28

    b3 = pdf.process_box(
        cx,
        y,
        324,
        "3. Iteración por Activos (CP)",
        [
            "Entrar al Excel:",
            "EXCEL|1_Configuración_del_puerto",
            "Recorrer cada Activo Físico u Operacional.",
            "Para cada activo, extraer:",
            "• Activo Físico u Operacional",
            "• Tipo de UO asociado",
        ],
        font_size=12,
        line_h=15,
    )
    connect_vertical(pdf, b2, b3)
    y = b3["bottom"] - 28

    b4 = pdf.process_box(
        cx,
        y,
        360,
        "4. Buscar impactos asociados al activo",
        [
            "Entrar al Excel:",
            "EXCEL|Relación_impactos_variables_climáticas",
            "Buscar:",
            "Activo Físico u Operacional = Activo de la",
            "iteración CP",
            "Extraer:",
            "• Filas con Modo de fallo «Exceso de precipitación»",
            "• Variable climática Precipitación",
            "• Tipo de impacto ELO",
        ],
        font_size=12,
        line_h=15,
    )
    connect_vertical(pdf, b3, b4)
    y = b4["bottom"] - 28

    b5 = pdf.process_box(
        cx,
        y,
        360,
        "5. Iteración por Modos de fallo (IM)",
        [
            "Sobre la tabla filtrada obtenida en el paso 4.",
            "Recorrer cada fila coincidente.",
            "Para cada fila, extraer:",
            "• Modo de fallo / Modo de parada",
            "• Variable climática",
            "• Tipo de impacto ELO",
        ],
        font_size=12,
        line_h=15,
    )
    connect_vertical(pdf, b4, b5)
    y = b5["bottom"] - 28

    b5b = pdf.process_box(
        cx,
        y,
        540,
        "5.b ¿Existe regla en Relacion_modelos_activos_e_indicadores.xlsx?",
        [
            "Entrar al Excel:",
            "EXCEL|4_Relación_modelos_activos_e_indicadores",
            "Buscar una fila explícita que coincida con:",
            "1. Modelo (PI exceso de precipitación)",
            "2. Activo Físico u Operacional (si está definido)",
            "3. Modo de fallo / Modo de parada",
            "4. Variable climática (Precipitación)",
            "5. Tipo de impacto ELO (si está definido)",
            "Exigido: Selección indicador = Predefinido",
            "y No indicadores = 1 o 2 (si hay más, se usan",
            "los 2 primeros; si hay 0 → error).",
            "La fila debe tener modo de fallo y variable",
            "explícitos (no comodines).",
        ],
        font_size=11,
        line_h=14,
        header_h=29,
    )
    connect_vertical(pdf, b5, b5b)
    y = b5b["bottom"] - 40

    d1 = pdf.diamond(cx, y - 34, 220, 70, "¿Fila válida?")
    pdf.arrow_down(cx, b5b["bottom"] - 2, d1["top"] + 2)

    left_cx = cx - 420
    right_cx = cx + 400
    branch_top = d1["bottom"] - 50
    branch_from_diamond(pdf, d1, left_cx, right_cx, branch_top, "SI", "NO")

    b_si = pdf.process_box(
        left_cx,
        branch_top,
        300,
        "Usar la configuración del Excel 4",
        [
            "• Percentil",
            "• Selección indicador = Predefinido",
            "• 1 o 2 indicadores climáticos",
            "  (si 1 → un solo par cambio/interp.;",
            "  si 2 → dos pares; umbrales mm",
            "  según Excel 4, p. ej. 1 mm / 20 mm)",
        ],
        font_size=11,
        line_h=14,
    )
    b_no = pdf.process_box(
        right_cx,
        branch_top,
        300,
        "No se puede calcular",
        [
            "Exceso de precipitación exige fila",
            "explícita en Excel 4 con",
            "Selección = Predefinido y al menos",
            "1 indicador (máx. 2). No hay búsqueda",
            "por umbral ni lógica clásica.",
        ],
        font_size=11,
        line_h=14,
    )

    y6 = b_si["bottom"] - 50
    b6 = pdf.process_box(
        cx,
        y6,
        500,
        "6. Buscar el umbral correspondiente — OMITIDO",
        [
            "No aplica: no existe umbral numérico a buscar",
            "para exceso de precipitación.",
            "Los indicadores vienen predefinidos de Excel 4.",
            "(El Excel 2 de umbrales / curvas no se usa aquí.)",
        ],
        font_size=12,
        line_h=15,
    )
    # SI continúa al paso 6 (centro); NO queda como rama muerta
    mid_y = (b_si["bottom"] + b6["top"]) / 2
    pdf.polyline([
        (b_si["cx"], b_si["bottom"]),
        (b_si["cx"], mid_y),
        (cx, mid_y),
        (cx, b6["top"] + 2),
    ])
    pdf.label(right_cx, b_no["bottom"] - 18, "(fin / error)", size=10)

    y = b6["bottom"] - 28
    b7 = pdf.process_box(
        cx,
        y,
        520,
        "7. Seleccionar el/los indicador(es) predefinido(s)",
        [
            "Entrar al Excel:",
            "EXCEL|3_Indicadores_climáticos",
            "Para cada indicador definido en Excel 4 (1 o 2):",
            "• indicador i (umbrales del indicador en mm según Excel 4,",
            "  p. ej. 1 mm; si hay segundo, p. ej. 20 mm)",
            "Filtrar por Variable climática y Percentil (paso 5b).",
            "Extraer valor Histórico y valores de escenarios futuros",
            "de cada indicador usado (criterio espacial Lon/Lat si aplica).",
        ],
        font_size=11,
        line_h=14,
    )
    connect_vertical(pdf, b6, b7)

    y = b7["bottom"] - 28
    b8 = pdf.process_box(
        cx,
        y,
        500,
        "8. Calcular el cambio respecto al histórico",
        [
            "Para cada escenario futuro y cada indicador:",
            "Cambio = Valor del escenario − Valor Histórico",
            "Donde: Histórico → Cambio = 0 (referencia)",
            "Se obtiene una serie independiente por indicador",
            "(1 par si hay 1 indicador; 2 pares si hay 2).",
        ],
        font_size=12,
        line_h=15,
    )
    connect_vertical(pdf, b7, b8)

    y = b8["bottom"] - 28
    b9 = pdf.table_box(
        cx,
        y,
        620,
        "9. Generar la tabla de resultados",
        [
            ["Escenario", "Cambio (ind.i)", "Interp. (ind.i)", "(+ ind.2 si aplica)", ""],
            ["Histórico", "0", "Referencia", "0 / —", "Referencia / —"],
            ["SSP2-4.5 2040", "Fut-Hist", "Mejora/Empeora/…", "Fut-Hist / —", "…"],
            ["SSP5-8.5 2040", "Fut-Hist", "Mejora/Empeora/…", "Fut-Hist / —", "…"],
            ["...", "...", "...", "...", "..."],
        ],
        font_size=9,
        line_h=13,
    )
    connect_vertical(pdf, b8, b9)

    y = b9["bottom"] - 28
    b10 = pdf.process_box(
        cx,
        y,
        500,
        "10. Interpretar el resultado (por indicador)",
        [
            "Para cada indicador, según el cambio Δ:",
            "• Δ < 0 → Mejora",
            "• Δ > 0 → Empeora",
            "• Δ = 0 → Sin cambios",
            "(Etiquetas de columna pueden usar el umbral en mm",
            "del nombre del indicador, p. ej. 1 mm / 20 mm.)",
            "Si Excel 4 trae 1 indicador → solo un par de columnas.",
        ],
        font_size=12,
        line_h=15,
    )
    connect_vertical(pdf, b9, b10)

    _draw_loops_and_end(pdf, cx, b10, b5, b3, out_path)


def _build_pdf_safe(builder, out_path: Path) -> None:
    """Escribe el PDF; si está bloqueado, usa temp y reemplaza."""
    try:
        builder(out_path)
        return
    except PermissionError:
        tmp = out_path.with_name(out_path.stem + "_tmp.pdf")
        print(f"PDF bloqueado ({out_path.name}). Escribiendo en {tmp.name}…")
        builder(tmp)
        try:
            tmp.replace(out_path)
            print(f"Reemplazado OK: {out_path}")
        except PermissionError:
            print(
                f"No se pudo reemplazar {out_path.name}. "
                "Cierre el visor PDF y renombre/mueva el _tmp.pdf."
            )
            raise


def main():
    folder = Path(r"E:\PDE\DEMO\Flujo de modelos")

    build_calado_like(
        folder / "CAPEX FALTA DE CALADO.pdf",
        "DIAGRAMA DE FLUJO ? CAPEX FALTA DE CALADO",
        step3_extra=["• Calado del buque: Dc"],
        step4_lines=[
            "Entrar al Excel:",
            "EXCEL|Relación_impactos_variables_climáticas",
            "Buscar:",
            "Activo Físico u Operacional = Activo de la",
            "iteración CP",
            "Extraer:",
            "• Filas con Modo de fallo «Falta de Calado»",
            "• Tipo de impacto ELU (CAPEX)",
        ],
        step5_lines=[
            "Sobre la fila ELU del activo (paso 4).",
            "Para cada fila IM, extraer:",
            "• Modo de fallo / Modo de parada",
            "• Variable climática",
            "• Tipo de impacto ELU",
        ],
        step5b_modelo="CAPEX falta de calado",
        step5b_tipo="ELU (si está definido en la fila)",
        step6_extra=[
            "• Si es una formulación que depende de un input, calcularlo",
            "• Umbral seleccionado ya calculado si es formulación",
        ],
        step7_predef_note="(si el Excel fijó un indicador)",
        step8_header="8. Aplicar la formulación h = NM ? h0 ? hsedim",
        step8_lines=[
            "Para cada escenario calcular:",
            "h = NM ? h0 ? hsedim",
            "donde NM, h0 y hsedim proceden de los",
            "indicadores / datos del activo.",
        ],
        step9_table=[
            ["Escenario", "NM", "h sedimentacion", "h0", "h"],
            ["Histórico", "Valor", "Valor", "Valor", "NM-h0-hsedim"],
            ["SSP2-4.5 2040", "Valor", "Valor", "Valor", "NM-h0-hsedim"],
            ["SSP5-8.5 2040", "Valor", "Valor", "Valor", "NM-h0-hsedim"],
            ["...", "...", "...", "...", "..."],
        ],
        step10_lines=[
            "Según el resultado de h frente al umbral:",
            "• umbral ? h ? Es necesario dragar",
            "• umbral > h ? No es necesario dragar",
        ],
    )

    build_calado_like(
        folder / "OPEX FALTA DE CALADO.pdf",
        "DIAGRAMA DE FLUJO ? OPEX FALTA DE CALADO",
        step3_extra=["• Calado del buque: Dc"],
        step4_lines=[
            "Entrar al Excel:",
            "EXCEL|Relación_impactos_variables_climáticas",
            "Buscar:",
            "Activo Físico u Operacional = Activo de la",
            "iteración CP",
            "Extraer:",
            "• Filas con Modo de fallo «Falta de Calado»",
            "• Tipo de impacto OPEX (p. ej. ELO, ELS)",
        ],
        step5_lines=[
            "Sobre la tabla filtrada obtenida en el paso 4.",
            "Recorrer cada fila coincidente.",
            "Para cada fila, extraer:",
            "• Modo de fallo / Modo de parada",
            "• Variable climática",
            "• Tipo de impacto (p. ej. ELO, ELS)",
        ],
        step5b_modelo="OPEX falta de calado",
        step5b_tipo="(si está definido en la fila)",
        step6_extra=[
            "• Si es una formulación que depende de un input, calcularlo",
            "• Umbral seleccionado ya calculado si es formulación",
        ],
        step7_predef_note="(si el Excel fijó un indicador)",
        step8_header="8. Aplicar la formulación h = NM ? h0 ? hsedim",
        step8_lines=[
            "Para cada escenario calcular:",
            "h = NM ? h0 ? hsedim",
            "donde NM, h0 y hsedim proceden de los",
            "indicadores / datos del activo.",
        ],
        step9_table=[
            ["Escenario", "NM", "h sedimentacion", "h0", "h"],
            ["Histórico", "Valor", "Valor", "Valor", "NM-h0-hsedim"],
            ["SSP2-4.5 2040", "Valor", "Valor", "Valor", "NM-h0-hsedim"],
            ["SSP5-8.5 2040", "Valor", "Valor", "Valor", "NM-h0-hsedim"],
            ["...", "...", "...", "...", "..."],
        ],
        step10_lines=[
            "Según el resultado de h frente al umbral:",
            "• umbral ? h ? Es necesario dragar",
            "• umbral > h ? No es necesario dragar",
        ],
    )

    build_francobordo(folder / "PI FALTA DE FRANCOBORDO.pdf")

    build_calado_like(
        folder / "PI SUPERACIÓN DE UMBRAL.pdf",
        "DIAGRAMA DE FLUJO ? PI SUPERACIÓN DE UMBRAL",
        step3_extra=[],
        step4_lines=[
            "Entrar al Excel:",
            "EXCEL|Relación_impactos_variables_climáticas",
            "Buscar:",
            "Activo Físico u Operacional = Activo de la",
            "iteración CP",
            "Extraer:",
            "• Todas las filas coincidentes del activo",
        ],
        step5_lines=[
            "Sobre la tabla filtrada obtenida en el paso 4.",
            "Recorrer cada fila coincidente.",
            "Para cada fila, extraer:",
            "• Modo de fallo / Modo de parada",
            "• Variable climática",
            "• Tipo de impacto (p. ej. ELO, ELS)",
        ],
        step5b_modelo="PI agitación / PI viento / superación umbral",
        step5b_tipo="(si está definido en la fila)",
        step6_extra=[],
        step7_predef_note="(si el Excel fijó un indicador)",
        # Caso especial solo de PI Superación (Inundación costera ELO), no de calado.
        step7_por_umbral_title="Seleccionar por umbral / Fb",
        step7_por_umbral_lines=[
            "General: indicador con el umbral",
            "del paso 6 (o diagrama).",
            "Inundacion costera (ELO):",
            "referencia = Fb (o umbral si Fb",
            "vacio); menor valor >= ref. en",
            "inundacion costera en atraque.",
        ],
        step8_header="8. Calcular la variación",
        step8_lines=[
            "Para cada escenario:",
            "Variación = Indicador del escenario ? Indicador Histórico",
            "Donde: Histórico ? Variación = 0",
        ],
        step9_table=[
            ["Escenario", "Indicador", "Variación"],
            ["Histórico", "Valor", "0"],
            ["SSP2-4.5 2040", "Valor", "Futuro - Histórico"],
            ["SSP5-8.5 2040", "Valor", "Futuro - Histórico"],
            ["...", "...", "..."],
        ],
        step10_lines=[
            "Según el tipo de indicador.",
            "Ejemplo: Número de horas de cierre",
            "• Variación > 0 ? Empeora (aumentan horas)",
            "• Variación < 0 ? Mejora (disminuyen horas)",
            "• Variación = 0 ? Sin cambios",
        ],
    )

    _build_pdf_safe(
        build_precipitacion,
        folder / "PI EXCESO DE PRECIPITACIÓN.pdf",
    )


if __name__ == "__main__":
    main()
