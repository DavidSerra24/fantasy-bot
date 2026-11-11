"""Diagnosi: HTML d'una pàgina de partit de futbolfantasy.com al voltant d'un nom.
Ús: python -m bot.ffpage 22551-racing-real-sociedad "Gómez" """
import re
import sys

from playwright.sync_api import sync_playwright

from bot.web import login_futbolfantasy, new_context

slug, q = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "futbolfantasy").new_page(); login_futbolfantasy(pg)
    pg.goto(f"https://www.futbolfantasy.com/partidos/{slug}", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    html = pg.content()
    b.close()
hits = [m.start() for m in re.finditer(re.escape(q), html)]
print(f"::notice title=ffpage::{len(hits)} coincidències de «{q}»")
for k, i in enumerate(hits[:6]):
    print(f"::notice title=ffpage {k}::" + html[max(0, i - 1200):i + 400].replace("\n", " ")[:3800])
