"""Consulta (només lectura): l'onze que hi ha posat ara al Mister (propera jornada) a cada lliga."""
from playwright.sync_api import sync_playwright

from bot.mister import U, login, new_context
from bot.misterlineup import formation, open_next, slots
from bot.misterplan import LEAGUES
from bot.notify import telegram

out = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    login(pg)
    for name, cid, _, _ in LEAGUES:
        pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
        url = open_next(pg)
        if not url:
            out.append(f"{name}: no trobo la propera jornada")
            continue
        head = pg.evaluate("() => (document.querySelector('a.nav__item.gameweek.active, a.nav__item.gameweek[aria-current]') || {}).innerText || ''")
        sl = slots(pg)
        names = pg.evaluate("""() => [...document.querySelectorAll('.lineup-starting button.lineup-player')].map(b => (b.innerText || '').replace(/\\s+/g, ' ').trim())""")
        full = sum(1 for s in sl if s.get("pid"))
        out.append(f"🧢 {name} · {formation(pg)} · {full}/11 · {head.strip()[:40]}\n   " + ", ".join(f"{n}{' ©' if s['cap'] else ''}" for s, n in zip(sl, names)))
    b.close()
msg = "\n".join(out)
print("::notice title=onze mister::" + msg.replace("\n", " ¶ "))
