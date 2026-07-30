# -*- coding: utf-8 -*-
from pathlib import Path
import runpy
import sys
import re

p = Path(r"E:\PDE\DEMO\Flujo de modelos\generar_flujo_master.py")
t = p.read_text(encoding="utf-8")
for i, l in enumerate(t.splitlines(), 1):
    if "beside_merge" in l or ("label" in l and "join_y" in l) or "rail_r -" in l:
        print(i, repr(l))
    if 'cy"] + 2' in l and "pdf.label" in l:
        print(i, repr(l))

t2, n1 = re.subn(
    r"pdf\.label\(cx \+ \d+, join_y \+ \d+, text, size=11\)",
    "pdf.label(cx + 42, join_y + 28, text, size=11)",
    t,
)
t2, n2 = re.subn(
    r'(d1[12]\["cy"\] \+) \d+',
    r"\g<1>28",
    t2,
)
t2, n3 = re.subn(r"rail_r - \d+", "rail_r - 110", t2)
print("subs", n1, n2, n3)
if n1 < 1:
    raise SystemExit("failed to bump Continuar")
p.write_text(t2, encoding="utf-8", newline="\n")
sys.path.insert(0, str(p.parent))
runpy.run_path(str(p), run_name="__main__")
print("done")
