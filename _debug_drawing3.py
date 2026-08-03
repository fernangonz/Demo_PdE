# -*- coding: utf-8 -*-
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
xml = open("_drawing1.xml", encoding="utf-8").read()
# regenerate from xlsx
import zipfile
xml = zipfile.ZipFile("Fichas/Ficha.xlsx").read("xl/drawings/drawing1.xml").decode("utf-8")
open("_drawing1.xml", "w", encoding="utf-8").write(xml)

idx = xml.find("Fallback")
print("Fallback idx", idx)
print(xml[idx-200:idx+100] if idx>=0 else "none")
print("---")
# find oneCellAnchor positions
for m in re.finditer(r"</?xdr:oneCellAnchor[^>]*>", xml):
    print(m.start(), m.group(0)[:80])
print("AlternateContent count", xml.count("AlternateContent"))
# Try extracting equation from whole xml fallback a:t
fb = re.search(r"<mc:Fallback>(.*?)</mc:Fallback>", xml, flags=re.S)
if fb:
    texts = re.findall(r"<a:t[^>]*>(.*?)</a:t>", fb.group(1))
    print("FALLBACK TEXTS:")
    for t in texts:
        print(repr(t))
    print("JOINED:", "".join(texts))
