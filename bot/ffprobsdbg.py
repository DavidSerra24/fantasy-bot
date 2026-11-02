"""Diagnosi (només lectura): d'on surten els % de la propera jornada a futbolfantasy.com."""
import re

from playwright.sync_api import sync_playwright

FF = "https://www.futbolfantasy.com"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(f"{FF}/laliga/posibles-alineaciones", wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(4000)
    links = pg.evaluate("() => [...new Set([...document.querySelectorAll('a')].map(a => a.href.split('#')[0]))]")
    print("::notice title=links partits::" + " ".join(l.split('/')[-1] for l in links if "/partidos/" in l)[:2500])
    print("::notice title=links jornada::" + " ".join(l for l in links if re.search(r"jornada|posibles-alineaciones", l))[:2500])
    print("::notice title=text::" + re.sub(r"\s+", " ", pg.inner_text("body"))[:2500])
    m = [l for l in links if "dimitrievski" in l.lower()]
    print("::notice title=dimi links::" + " ".join(m[:5]))
    pg.goto(f"{FF}/jugadores/dimitrievski", wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(3000)
    t = re.sub(r"\s+", " ", pg.inner_text("body"))
    i = t.find("%")
    print("::notice title=perfil::" + pg.url + " | " + t[max(0, i - 800):i + 600])
    b.close()
