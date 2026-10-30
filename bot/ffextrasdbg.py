"""Diagnosi (només lectura): jocs extres de FutbolFantasy, caselles i regles."""
from playwright.sync_api import sync_playwright

from bot import ff
from bot.extras import kind_of
from bot.web import login_futbolfantasy, new_context

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "futbolfantasy").new_page()
    login_futbolfantasy(pg)
    for c in ff.cards(pg):
        if not kind_of(c):
            continue
        sl = ff.read_slots(pg, c["id"])
        print(f"::notice title=extra {c['id']}::{c['label']} | {c['title']} | tanca {c['end']} | buides {c['empty']} | " + ", ".join(f"{s['slot']}:{s['name']}" for s in sl))
        html = pg.evaluate("(id) => { const e = document.getElementById('juego-' + id); return e ? e.innerText.slice(0, 600) : '' }", c["id"])
        print(f"::notice title=text {c['id']}::" + html.replace("\n", " | "))
    b.close()
