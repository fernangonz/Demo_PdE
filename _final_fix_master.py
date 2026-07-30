# -*- coding: utf-8 -*-
"""Final master-flowchart label fix + PDF regenerate."""
from __future__ import annotations

import re
import runpy
import sys
from pathlib import Path

MASTER = Path(r"E:\PDE\DEMO\Flujo de modelos\generar_flujo_master.py")
text = MASTER.read_text(encoding="utf-8")

helpers = '''def _label_white(pdf: FlowPDF, x: float, y: float, text: str, size: int = 11) -> None:
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


'''

m = re.search(
    r"def _label_clear_of_vline.*?\n(?=class MasterFlowPDF)"
    r"|def _label_beside_merge.*?\n(?=class MasterFlowPDF)"
    r"|def _label_white.*?\n(?=class MasterFlowPDF)"
    r"|def _merge_down_to_top.*?\n(?=class MasterFlowPDF)",
    text,
    flags=re.S,
)
if not m:
    # fallback: from first helper def to class
    m = re.search(
        r"def _label_.*?\n(?=class MasterFlowPDF)|def _merge_down_to_top.*?\n(?=class MasterFlowPDF)",
        text,
        flags=re.S,
    )
if not m:
    raise SystemExit("helpers block not found")
text = text[: m.start()] + helpers + text[m.end() :]

# Bigger gaps before diamonds
text = re.sub(
    r'pred_cy = min\(b_si\["bottom"\], b_no\["bottom"\]\) - \d+',
    'pred_cy = min(b_si["bottom"], b_no["bottom"]) - 200',
    text,
)
text = re.sub(
    r"d11_cy = merge_bottom - \d+",
    "d11_cy = merge_bottom - 210",
    text,
)

# Clean decision labels
text = re.sub(
    r'_label_above_hline\(pdf, left_cx \+ 16, d11\["cy"\], "[^"]*"\)',
    '_label_above_hline(pdf, left_cx + 16, d11["cy"], "S\u00cd")',
    text,
)
text = re.sub(
    r'_label_above_hline\(pdf, right_cx - 48, d11\["cy"\], "[^"]*"\)',
    '_label_above_hline(pdf, right_cx - 36, d11["cy"], "NO")',
    text,
)
text = re.sub(
    r'_label_above_hline\(pdf, cx \+ 20, d12\["cy"\], "[^"]*"\)',
    '_label_above_hline(pdf, d12["left"] - 50, d12["cy"], "NO")',
    text,
)
text = re.sub(
    r'_label_beside_vline\(\s*pdf,\s*rail_r,\s*\(d12\["cy"\] \+ b3_mid\) / 2,\s*"[^"]*",\s*right=False,\s*\)',
    '_label_above_hline(pdf, d12["right"] + 18, d12["cy"], "S\u00cd")\n'
    '    _label_beside_vline(\n'
    "        pdf,\n"
    "        rail_r,\n"
    '        (d12["cy"] + b3_mid) / 2,\n'
    '        "\u2192 paso 3",\n'
    "        right=False,\n"
    "    )",
    text,
)
text = re.sub(
    r'_label_beside_vline\(pdf, rail, \(b5_mid \+ b11_mid\) / 2, "[^"]*", right=True\)',
    '_label_beside_vline(pdf, rail, (b5_mid + b11_mid) / 2, "\u2192 paso 5", right=True)',
    text,
)

# TXT cleanup of Continuar ?
text = text.replace("Continuar ?", "Continuar")
text = text.replace("Continuar \u2193", "Continuar")

MASTER.write_text(text, encoding="utf-8", newline="\n")
check = MASTER.read_text(encoding="utf-8")
assert "_label_beside_merge" in check
assert 'pred_cy = min(b_si["bottom"], b_no["bottom"]) - 200' in check
assert "d11_cy = merge_bottom - 210" in check
assert "\u2192 paso 3" in check
print("patched OK")

sys.path.insert(0, str(MASTER.parent))
runpy.run_path(str(MASTER), run_name="__main__")
print("PDF regenerated")
