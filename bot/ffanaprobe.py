"""Diagnosi (només lectura): estructura de futbolfantasy.com/analytics/laliga2/futbolfantasy-rpg/2027."""
import re
import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
url = "https://www.futbolfantasy.com/analytics/laliga2/estadisticas-puntos/2027?puntuacion=futbolfantasy-rpg"
h = requests.get(url, headers=H, timeout=60).text
print(f"::notice title=len::{len(h)}")
for kw in ("Otero", "<tr", "data-", "Media"):
    ms = list(re.finditer(re.escape(kw), h))
    print(f"::notice title=count {kw}::{len(ms)}")
    for m in ms[:2]:
        print(f"::notice title=kw {kw}::" + re.sub(r"\s+", " ", h[max(0, m.start() - 1200):m.start() + 1500]))
