"""Neteja i diagnosi: Europa League J4 (tanca d'aquí a setmanes)."""
from playwright.sync_api import sync_playwright
from bot import ff
from bot.web import new_context, login_futbolfantasy
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_context(b, "futbolfantasy"); pg = ctx.new_page()
    login_futbolfantasy(pg)
    g = next(c for c in ff.cards(pg) if c["label"].startswith("Europa League · J4"))
    print(f"::notice title=p::abans: {g['ids']} buits={g['empty']} caselles={ff.read_slots(pg, g['id'])}")
    for s in ff.read_slots(pg, g["id"]):
        ff.remove_slot(pg, g["id"], s["slot"])
    g2 = next(c for c in ff.cards(pg) if c["id"] == g["id"])
    print(f"::notice title=p::després: {g2['ids']} buits={g2['empty']}")
    b.close()
