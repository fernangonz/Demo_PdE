# -*- coding: utf-8 -*-
import re

xml = open("_drawing1.xml", encoding="utf-8").read()
parts = re.split(r"(?=<xdr:(?:twoCellAnchor|oneCellAnchor|absoluteAnchor)\b)", xml)
for i, p in enumerate(parts):
    if "CellAnchor" not in p[:80] and "absoluteAnchor" not in p[:80]:
        continue
    kind = "two" if p.startswith("<xdr:twoCellAnchor") else (
        "one" if p.startswith("<xdr:oneCellAnchor") else "abs"
    )
    print("====", i, kind, "len", len(p))
    fr = re.search(r"<xdr:from>.*?</xdr:from>", p, re.S)
    if fr:
        print("FROM", re.sub(r"\s+", " ", fr.group(0)))
    to = re.search(r"<xdr:to>.*?</xdr:to>", p, re.S)
    if to:
        print("TO", re.sub(r"\s+", " ", to.group(0))[:400])
    texts = re.findall(r"<a:t[^>]*>(.*?)</a:t>", p)
    if texts:
        print("TEXTS:", texts)
    names = re.findall(r'\bname="([^"]+)"', p)
    if names:
        print("names:", names[:5])
    print("has pic", "<xdr:pic" in p, "has sp", "<xdr:sp" in p)
