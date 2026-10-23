from playwright.sync_api import sync_playwright
from bot.web import new_context
def note(m):
    for i in range(0, len(m), 900):
        print("::notice title=rv::" + m[i:i+900])
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_context(b, "anon"); pg = ctx.new_page()
    pg.goto("https://www.futbolfantasy.com/partidos/22519-racing-espanyol", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(6000)
    h = pg.content()
    import re
    note("mencions revulsiv: " + " ### ".join(m.group(0) for m in re.finditer(r".{0,250}revulsiv.{0,250}", h, re.I | re.S))[:2600])
    i = h.find("Puado")
    note("Puado: " + h[max(0, i-1500):i+600] if i >= 0 else "Puado no és a l'HTML")
    b.close()
