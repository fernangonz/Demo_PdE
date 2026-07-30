# -*- coding: utf-8 -*-
"""Patch master flowchart labels, regenerate PDF, then removable."""
from __future__ import annotations

import re
import runpy
import sys
from pathlib import Path

FOLDER = Path(r"E:\PDE\DEMO\Flujo de modelos")
MASTER = FOLDER / "generar_flujo_master.py"

text = MASTER.read_text(encoding="utf-8")

helpers = '''def _label_beside_merge(pdf: FlowPDF, cx: float, join_y: float, text: str = "Continuar") -> None:
    """Etiqueta a la derecha del T de fusion, por encima de la horizontal (nunca en la flecha)."""
    pdf.label(cx + 18, join_y + 12, text, size=11)


def _merge_down_to_top(pdf: FlowPDF, left_box, right_box, target_cx: float, target_top: float) -> None:
    """Fusion sin SI/NO: ambas cajas bajan a una linea y entran por arriba con flecha."""
    join_y = min(left_box["bottom"], right_box["bottom"]) - 40
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
    _label_beside_merge(pdf, target_cx, join_y, "Continuar")


def _merge_four_to_top(pdf: FlowPDF, boxes, target_cx: float, target_top: float) -> None:
    """Fusion no etiquetada de varias cajas hacia el siguiente paso."""
    join_y = min(b["bottom"] for b in boxes) - 40
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
    _label_beside_merge(pdf, target_cx, join_y, "Continuar")


'''

m = re.search(
    r"(?:def _label_beside_arrow_down|def _label_above_hline|def _merge_down_to_top).*?\n(?=class MasterFlowPDF)",
    text,
    flags=re.S,
)
if not m:
    raise SystemExit("helper block not found")
text = text[: m.start()] + helpers + text[m.end() :]

text = text.replace(
    'pred_cy = min(b_si["bottom"], b_no["bottom"]) - 110',
    'pred_cy = min(b_si["bottom"], b_no["bottom"]) - 200',
)
text = text.replace(
    "d11_cy = merge_bottom - 130",
    "d11_cy = merge_bottom - 210",
)

m = re.search(
    r'    rail_r = PAGE_W - MARGIN - 40\n.*?    fin_y = min\(b11_si',
    text,
    flags=re.S,
)
if not m:
    raise SystemExit("rail_r block not found")
new_cp = (
    "    rail_r = PAGE_W - MARGIN - 40\n"
    "    b3_mid = _mid(b3)\n"
    "    pdf.polyline(\n"
    "        [\n"
    '            (d12["right"], d12["cy"]),\n'
    '            (rail_r, d12["cy"]),\n'
    "            (rail_r, b3_mid),\n"
    '            (b3["right"], b3_mid),\n'
    "        ]\n"
    "    )\n"
    '    pdf.label(d12["right"] + 18, d12["cy"] + 20, "S\u00cd", size=12)\n'
    '    pdf.label(rail_r - 100, (d12["cy"] + b3_mid) / 2, "\u2192 paso 3", size=12)\n'
    "\n"
    "    fin_y = min(b11_si"
)
text = text[: m.start()] + new_cp + text[m.end() :]

text = re.sub(
    r'[ \t]*_label_above_hline\(pdf, left_cx \+ 16, d11\["cy"\], [^\n]+\)\n',
    '    pdf.label(left_cx + 16, d11["cy"] + 20, "S\u00cd", size=12)\n',
    text,
)
text = re.sub(
    r'[ \t]*_label_above_hline\(pdf, right_cx - 50, d11\["cy"\], [^\n]+\)\n',
    '    pdf.label(right_cx - 36, d11["cy"] + 20, "NO", size=12)\n',
    text,
)
text = re.sub(
    r'[ \t]*_label_above_hline\(pdf, cx \+ 16, d12\["cy"\], [^\n]+\)\n',
    '    pdf.label(d12["left"] - 40, d12["cy"] + 20, "NO", size=12)\n',
    text,
)

text = re.sub(r'"[^"]*volver a paso 5"', '"\u2192 paso 5"', text)
text = text.replace("\u2192 Continuar", "Continuar")
text = text.replace("? Continuar", "Continuar")

MASTER.write_text(text, encoding="utf-8", newline="\n")
print("patched", MASTER)

check = MASTER.read_text(encoding="utf-8")
assert "_label_beside_merge" in check
assert "- 200" in check
assert "- 210" in check
assert "\u2192 paso 3" in check
assert "_label_above_hline" not in check
assert "_label_beside_arrow_down" not in check
print("sanity OK")

sys.path.insert(0, str(FOLDER))
runpy.run_path(str(MASTER), run_name="__main__")
print("PDF regenerated")
