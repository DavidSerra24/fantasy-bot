"""Reconeixement (només lectura): plantilles twig de les finestres de puja, venda i ofertes del Mister."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
B = "https://app-mister.mundodeportivo.com/file/forge-app/786c6e4f/app/dist/js/"
U = "https://mister.mundodeportivo.com"
t = requests.get(B + "functions.js", headers=H, timeout=30).text
for name in ("bid", "sale", "formation"):
    html = requests.get(U + "/views/ajax/" + name + ".twig", headers=H, timeout=30).text
    out = []
    for kw in ('type="tel"', "btn-send", "data-ajax", "btn-free", "name=\"price"):
        for m in list(re.finditer(re.escape(kw), html))[:3]:
            out.append(html[max(0, m.start() - 200):m.end() + 300].replace("\n", " "))
    print(f"::notice title={name}::" + " ¶¶ ".join(out)[:6000])
