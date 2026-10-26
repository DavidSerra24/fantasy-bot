"""Prova de només lectura: busca noms al selector del Fantasy de la Premier i mostra què troba (usos inclosos)."""
from playwright.sync_api import sync_playwright
from bot import ff
from bot.web import new_context, login_futbolfantasy, inject

FF = "https://www.futbolfantasy.com"
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = new_context(b, "futbolfantasy")
    pg = ctx.new_page()
    login_futbolfantasy(pg)
    cs = [c for c in ff.cards(pg) if c["label"].startswith("Premier League") and c["hours"] and c["hours"] > 0]
    for g in cs[:1]:
        print(f"::notice title=t::joc {g['label']} buit={g['empty']} slots={ff.read_slots(pg, g['id'])}")
        pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500); inject(pg, "ff")
        if g["empty"] == 0:
            print("::notice title=t::joc ple: no es pot obrir el buscador sense treure ningú")
            continue
        ff.open_picker(pg, g["id"])
        for q in ["Martin Ødegaard", "Martin Odegaard", "Ødegaard", "Odegaard", "degaard"]:
            r = pg.evaluate("(q) => __ff.search(q)", q) or []
            print(f"::notice title=t::{q} -> {r[:5]}")
        ff.close_modal(pg)
        f, m = ff.lookup(pg, g["id"], [{"si": "Martin Ødegaard", "team": "Arsenal", "opp": None, "ps": 99, "pct": 90, "idx": 0}])
        print(f"::notice title=t::lookup trobats={f} falten={m}")
    b.close()
