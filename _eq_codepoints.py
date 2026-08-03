# -*- coding: utf-8 -*-
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
xml = open("_drawing1.xml", encoding="utf-8").read()
# get fallback a:t
m = re.search(r"<mc:Fallback>.*?<a:t[^>]*>(.*?)</a:t>", xml, re.S)
fb = m.group(1) if m else ""
print("FB:", fb)
print("codepoints:", [hex(ord(c)) for c in fb[:40]])
# m:t texts
mts = re.findall(r"<m:t[^>]*>(.*?)</m:t>", xml)
joined = "".join(mts)
print("MTS:", joined)
print("mts cps sample:", [hex(ord(c)) for c in joined[:30]])
