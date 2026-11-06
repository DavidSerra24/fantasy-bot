"""Diagnosi (només lectura): estructura de futbolfantasy.com/analytics/laliga2/futbolfantasy-rpg/2027."""
import re
import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
url = "https://www.futbolfantasy.com/analytics/laliga2/estadisticas-puntos/2027?puntuacion=futbolfantasy-rpg"
h = requests.get(url, headers=H, timeout=60).text
print(f"::notice title=len::{len(h)}")
i = h.find('data-name="juan otero"')
row = h[i:h.find("</tr>", i)]
cells = re.findall(r'<td[^>]*data-value="([^"]+)"[^>]*data-total="([^"]*)"[^>]*data-casa="([^"]*)"[^>]*data-fuera="([^"]*)"', row)
print("::notice title=cells::" + " | ".join(f"{a}={b}/{c}/{d}" for a, b, c, d in cells)[:6000])
print("::notice title=rest::" + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", row[-3000:]))[:2000])
