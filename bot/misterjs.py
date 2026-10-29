"""Reconeixement (només lectura): plantilles twig de les finestres de puja, venda i ofertes del Mister."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
B = "https://app-mister.mundodeportivo.com/file/forge-app/786c6e4f/app/dist/js/"
U = "https://mister.mundodeportivo.com"
t = requests.get(B + "functions.js", headers=H, timeout=30).text
i = t.find("function popup_twig")
print("::notice title=popup_twig::" + t[i:i + 2500].replace("\n", " "))
i = t.find("function popup_open") if "function popup_open" in t else t.find("function popup(")
print("::notice title=popup::" + t[i:i + 2000].replace("\n", " "))
for name in ("bid", "sale", "market/offers-received/direct-transfer-confirmation", "market/offers-received", "offers"):
    for base in ("/views/popup/", "/views/ajax/popup/", "/views/popups/"):
        r = requests.get(U + base + name + ".twig", headers=H, timeout=30)
        if r.ok and "{%" in r.text or "{{" in r.text:
            html = r.text
            keep = " ".join(re.findall(r"<form[^>]*>|<input[^>]*>|<button[^>]*btn-send[^>]*>|data-ajax=\"[^\"]*\"|id=\"btn-send\"[^>]*>", html))
            print(f"::notice title={base}{name}::" + keep[:3000])
            break
    else:
        print(f"::notice title={name}::no trobada")
