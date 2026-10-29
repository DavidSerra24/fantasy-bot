"""Reconeixement (només lectura): plantilles twig de les finestres de puja, venda i ofertes del Mister."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
B = "https://app-mister.mundodeportivo.com/file/forge-app/786c6e4f/app/dist/js/"
U = "https://mister.mundodeportivo.com"
t = requests.get(B + "functions.js", headers=H, timeout=30).text
for name in ("bid", "sale"):
    html = re.sub(r"\s+", " ", requests.get(U + "/views/ajax/" + name + ".twig", headers=H, timeout=30).text)
    i = html.find("<form")
    body = html[i:i + 12000]
    for k in range(0, len(body), 4000):
        print(f"::notice title={name}{k // 4000}::" + body[k:k + 4000])
