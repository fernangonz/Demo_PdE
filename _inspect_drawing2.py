# -*- coding: utf-8 -*-
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
xml = open("_drawing1.xml", encoding="utf-8").read()
parts = re.split(r"(?=<xdr:(?:twoCellAnchor|oneCellAnchor|absoluteAnchor)\b)", xml)
for i, p in enumerate(parts):
    if not p.startswith("<xdr:"):
        continue
    texts = re.findall(r"<a:t[^>]*>(.*?)</a:t>", p)
    fr = re.search(
        r"<xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>",
        p,
        re.S,
    )
    print("part", i, "from", fr.groups() if fr else None)
    print("pic", "<xdr:pic" in p, "sp", "<xdr:sp" in p)
    if texts:
        joined = "".join(texts)
        print("JOINED:", joined)
        print("TEXTS LIST:", texts)
