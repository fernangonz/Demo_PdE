# -*- coding: utf-8 -*-
from pathlib import Path

p = Path("core/modelos/fichas_excel.py")
t = p.read_text(encoding="utf-8")

t = t.replace(r"<a:t[^>]*>", r"<a:t(?:\s[^>]*)?>")
t = t.replace(
    r'r"<mc:Fallback>(.*?)</mc:Fallback>"',
    r'r"<mc:Fallback\b[^>]*>(.*?)</mc:Fallback>"',
)

needle = '"\\U0001d45b": "n",'
if needle in t and "1d46f" not in t:
    insert = (
        '"\\U0001d45b": "n",\n'
        '            "\\U0001d46f": "H",\n'
        '            "\\U0001d46d": "F",\n'
        '            "\\U0001d494": "s",\n'
        '            "\\U0001d489": "h",\n'
        '            "\\U0001d48a": "i",'
    )
    t = t.replace(needle, insert, 1)

# Prefer readable form with spaces around =
t = t.replace(
    't = re.sub(r"^\\u0394R[_]?S\\s*=", "\\u0394Rs =", t)\n'
    '    t = re.sub(r"^\\u0394RS\\s*=", "\\u0394Rs =", t)\n'
    '    t = re.sub(r"^\\u0394Rs\\s*=", "\\u0394Rs =", t)',
    't = re.sub(r"^\\u0394R[_]?S\\s*=\\s*", "\\u0394Rs = ", t)\n'
    '    t = re.sub(r"^\\u0394RS\\s*=\\s*", "\\u0394Rs = ", t)\n'
    '    t = re.sub(r"^\\u0394Rs\\s*=\\s*", "\\u0394Rs = ", t)\n'
    '    t = re.sub(r"\\s*=\\s*max", " = max", t, flags=re.I)',
)

p.write_text(t, encoding="utf-8")
print("ok")
for line in p.read_text(encoding="utf-8").splitlines():
    if "a:t" in line or "Fallback" in line or "1d46f" in line or "0394R" in line or "= max" in line:
        print(line)
