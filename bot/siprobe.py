"""Diagnosi (només lectura): seccions Bench / DNP de la fitxa d'un equip de SorareInside."""
import datetime as dt
import sys

from playwright.sync_api import sync_playwright

from bot import si
from bot.web import inject, login_sorareinside, new_context

team = " ".join(sys.argv[1:]) or "AD Ceuta FC"
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "sorareinside").new_page()
    login_sorareinside(pg)
    pg.goto("https://sorareinside.com/lineups", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
    si.pick_gameweek(pg, dt.date.today() + dt.timedelta(days=1))
    inject(pg, "si")
    print("::notice title=lliga::" + str(pg.evaluate("([c,l]) => __si.league(c,l)", ["Spain", "Segunda División"])))
    pg.wait_for_timeout(2500)
    names = pg.evaluate("() => __si.anchors()")
    t = next((n for n in names if team.lower().split()[0] in n.lower() or "ceuta" in n.lower()), names[0])
    print("::notice title=obro::" + t + " · " + ", ".join(names))
    print("::notice title=st::" + str(pg.evaluate("(t) => __si.openTeam(t)", t)))
    txt = pg.evaluate("() => document.querySelector('[role=dialog]').innerText")
    for kw in ("Bench", "DNP", "Not in squad", "Injur", "Lapeña"):
        i = txt.find(kw)
        print(f"::notice title=kw {kw}::{i} " + (txt[max(0, i - 300):i + 900].replace("\n", " | ") if i >= 0 else ""))
    print("::notice title=final::" + txt[-2500:].replace("\n", " | "))
    html = pg.evaluate("""() => { const d = document.querySelector('[role=dialog]'); const out = [];
        for (const e of d.querySelectorAll('*')) { if (e.childElementCount === 0 && /^(Bench|DNP)$/i.test(e.textContent.trim())) {
            let c = e; for (let i = 0; i < 3 && c.parentElement; i++) c = c.parentElement; out.push(c.outerHTML.slice(0, 2500)); } } return out; }""")
    for h in html[:4]:
        print("::notice title=html::" + h.replace("\n", " "))
    b.close()
