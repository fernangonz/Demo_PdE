# -*- coding: utf-8 -*-
from pathlib import Path

p = Path("core/modelos/fichas_excel.py")
t = p.read_text(encoding="utf-8")
old = '    t = re.sub(r"\\s*=\\s*max", " = max", t, flags=re.I)\n    return t.strip()'
new = (
    '    t = re.sub(r"\\s*=\\s*max", " = max", t, flags=re.I)\n'
    '    t = t.replace("T_port", "Tport").replace("C_conc", "Cconc")\n'
    '    t = t.replace("(Tport +Cconc)", "(Tport+Cconc)")\n'
    '    t = re.sub(r"max\\{0,\\s*", "max{0, ", t)\n'
    "    return t.strip()"
)
if old not in t:
    raise SystemExit("anchor not found: " + repr(old[:60]))
p.write_text(t.replace(old, new, 1), encoding="utf-8")
print("ok")
