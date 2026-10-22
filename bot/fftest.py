"""Prova segura del canvi de jugadors: afegeix i treu un jugador a l'Europa League J4 (tanca d'aquí a setmanes)."""
from playwright.sync_api import sync_playwright
from bot import ff
from bot.web import new_context, login_futbolfantasy, save_session

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = new_context(b, "futbolfantasy")
    pg = ctx.new_page()
    login_futbolfantasy(pg)
    cs = ff.cards(pg)
    g = next(c for c in cs if c["label"].startswith("Europa League") and c["empty"] == 11)
    print(f"::notice title=t::joc {g['id']} {g['label']} tanca {g['end']} buit={g['empty']}")
    ff.fill(pg, g["id"], [{"ff": "Dion Beljo"}])
    c1 = next(c for c in ff.cards(pg) if c["id"] == g["id"])
    print(f"::notice title=t::després d'afegir: ids={c1['ids']} buit={c1['empty']} slots={c1['slots']}")
    log = []
    ff.remove_players(pg, g["id"], set(c1["ids"]), log)
    c2 = next(c for c in ff.cards(pg) if c["id"] == g["id"])
    print(f"::notice title=t::després de treure: ids={c2['ids']} buit={c2['empty']} {log}")
    save_session(ctx, "futbolfantasy")
    b.close()
