"""Diagnosi (només lectura): estat de cada equip a SorareInside (per què «onze no disponible»)."""
import datetime as dt
import sys

from playwright.sync_api import sync_playwright

from bot import si
from bot.web import login_sorareinside, new_context

country, league = (sys.argv[1], " ".join(sys.argv[2:])) if len(sys.argv) > 2 else ("Spain", "Segunda División")
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "sorareinside").new_page()
    login_sorareinside(pg)
    d = si.extract_league(pg, country, league, dt.date.today() + dt.timedelta(days=1), use_cache=False)
    for t in d["_order"]:
        v = d.get(t)
        if not isinstance(v, list):
            txt = pg.evaluate("() => (document.querySelector('[role=dialog]')||{}).innerText || ''")
            print(f"::notice title=equip {t}::{v}")
        else:
            print(f"::notice title=equip {t}::ok {sum(len(r) for r in v)} jugadors")
    # torna a obrir un dels que fallen i mira què hi ha
    bad = [t for t in d["_order"] if not isinstance(d.get(t), list)]
    from bot.web import inject
    for t in bad[:2]:
        inject(pg, "si")
        st = pg.evaluate("(t) => __si.openTeam(t)", t)
        txt = pg.evaluate("() => (document.querySelector('[role=dialog]')||{}).innerText || 'SENSE DIÀLEG'")
        n = pg.evaluate("() => { const d = document.querySelector('[role=dialog]'); const f = d && d.querySelector('[class*=_field_]'); return f ? f.querySelectorAll('[data-has-player]').length : -1; }")
        print(f"::notice title=reobro {t}::{st} · caselles {n} · " + txt.replace("\\n", " | ")[:1500])
        pg.evaluate("() => __si.close()")
    b.close()
