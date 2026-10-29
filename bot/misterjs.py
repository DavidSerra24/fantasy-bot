"""Reconeixement (només lectura): plantilles twig de les finestres de puja, venda i ofertes del Mister."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
B = "https://app-mister.mundodeportivo.com/file/forge-app/786c6e4f/app/dist/js/"
U = "https://mister.mundodeportivo.com"
t = requests.get(B + "functions.js", headers=H, timeout=30).text
for name in ("bid", "sale", "market/offers-received/direct-transfer-confirmation", "market/offers-received", "formation", "team/substitution"):
    r = requests.get(U + "/views/ajax/" + name + ".twig", headers=H, timeout=30)
    if not r.ok:
        print(f"::notice title={name}::HTTP {r.status_code}")
        continue
    html = r.text
    keep = " ".join(re.findall(r"<form[^>]*>|<input[^>]*>|<button[^>]*(?:btn-send|data-ajax|btn-accept|btn-free|lineup)[^>]*>|data-ajax=\"[^\"]*\"", html))
    print(f"::notice title={name}::" + keep[:4000])
