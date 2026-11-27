"""Diagnosi (27/11): Pyshchur a SorareInside i a les plantilles del Mister."""
from playwright.sync_api import sync_playwright
from bot import psest
from bot.ff import name_score
from bot.mistermarket import _si_next
from bot.web import login_sorareinside, new_context
with sync_playwright() as p:
    b = p.chromium.launch(); pg = new_context(b, "sorareinside").new_page(); login_sorareinside(pg)
    d = _si_next(pg, "Spain", "Segunda División")
    for t in d.get("_order", []):
        for r in d.get(t) or []:
            for x in r:
                if "yshch" in (x.get("name") or "").lower():
                    print("::notice title=SI::" + f"{t}: {x}")
    R = psest.rosters()
    for k, v in R.items():
        for q in v:
            if "yshch" in q["name"].lower():
                print("::notice title=Mister::" + f"{k}: {q}")
    print("::notice title=equips Mister::" + ", ".join(sorted(R))[:1500])
