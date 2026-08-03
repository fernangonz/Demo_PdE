# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from core.modelos.fichas_excel import invalidar_cache_fichas, _cargar_fichas_excel

invalidar_cache_fichas()
fichas = _cargar_fichas_excel()
print("keys", list(fichas.keys()))
for k, f in fichas.items():
    print("===", k, f.hoja)
    print("imgs", [str(p) for p in f.imagenes])
    print("html len", len(f.html))
    # show key snippets
    html = f.html
    for needle in ("1F4E79", "MODELO", "pde-ficha-eq", "?Rs", "rowspan", "FFFFFF", "background"):
        print(needle, needle in html)
    # extract equation div
    import re
    eqs = re.findall(r'class="pde-ficha-eq">(.*?)</div>', html)
    print("EQS:", eqs)
    # header cell snippet
    m = re.search(r"<td[^>]*>PI \(ELO\).*?</td>", html)
    print("HEADER:", m.group(0)[:200] if m else None)
    m2 = re.search(r'rowspan="[^"]*"[^>]*>MODELO[^<]*', html)
    print("SIDE:", m2.group(0) if m2 else None)
