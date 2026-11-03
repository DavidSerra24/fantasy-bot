"""Diagnosi (només lectura): noms dels jugadors a Predicted11 d'alguns equips."""
from playwright.sync_api import sync_playwright

from bot.p11 import BASE
from bot.web import new_context

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "p11").new_page()
    for comp, slug, keys in (("champions", "lille", ("kj", "maurit")), ("laliga2", "ceuta", ("anuar", "tuhami")), ("laliga2", "burgos", ("sergio", "gonz"))):
        pg.goto(f"{BASE}{comp}/equipo/{slug}", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        names = pg.evaluate("() => [...document.querySelectorAll('#playerList .player-item')].map(e => e.dataset.nombre + ' | ' + (e.dataset.nombrecorto||''))")
        print(f"::notice title={comp}/{slug}::{len(names)} jugadors · " + " ; ".join(n for n in names if any(k in n.lower() for k in keys)))
    b.close()
