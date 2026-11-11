"""Diagnosi: què mostra la fitxa d'un jugador a futbolfantasy.com (probabilitat de jugar).
Ús: python -m bot.ffprofile sergio-gomez"""
import re
import sys

from playwright.sync_api import sync_playwright

from bot.web import login_futbolfantasy, new_context

slug = sys.argv[1]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "futbolfantasy").new_page(); login_futbolfantasy(pg)
    pg.goto(f"https://www.futbolfantasy.com/jugadores/{slug}/laliga-26-27", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    txt = re.sub(r"\s+", " ", pg.inner_text("body"))
    probs = pg.evaluate("() => [...document.querySelectorAll('[data-probabilidad], [class*=probabilidad]')].slice(0, 15).map(e => e.tagName + '.' + e.className + ' ' + (e.getAttribute('data-probabilidad') || '') + ' | ' + e.innerText.replace(/\\s+/g, ' ').slice(0, 80))")
    b.close()
print("::notice title=fitxa probs::" + " ¶ ".join(probs)[:3900])
for k, m in enumerate(list(re.finditer(r"\d{1,3}\s?%", txt))[:6]):
    print(f"::notice title=fitxa {k}::" + txt[max(0, m.start() - 200):m.end() + 100])
