"""Reconeixement (només lectura): quins endpoints /ajax i /api2 fa servir el codi JavaScript de la web del Mister."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
U = "https://mister.mundodeportivo.com"
html = requests.get(U + "/", headers=H, timeout=30).text
js = sorted(set(re.findall(r'src="([^"]+\.js[^"]*)"', html)))
print("::notice title=js::" + " ".join(js)[:3000])
found = {}
for u in js:
    if u.startswith("//"):
        u = "https:" + u
    elif u.startswith("/"):
        u = U + u
    if "mundodeportivo" not in u:
        continue
    try:
        t = requests.get(u, headers=H, timeout=30).text
    except Exception:
        continue
    for m in re.finditer(r"['\"`](/?(?:ajax|api2|action)/[A-Za-z0-9_\-/]+)['\"`]", t):
        ctx = t[max(0, m.start() - 250):m.end() + 350].replace("\n", " ")
        found.setdefault(m.group(1), ctx)
print("::notice title=endpoints::" + " | ".join(sorted(found))[:6000])
for k in sorted(found):
    if re.search(r"bid|sale|sell|offer|transfer|lineup|formation|captain|substitution|market|clause|pool", k, re.I):
        print(f"::notice title={k[:60]}::" + found[k][:1500])
