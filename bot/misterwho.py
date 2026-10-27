"""Diagnosi (només lectura): amb quin jugador de la font ha relacionat el bot cada jugador de la plantilla del Mister.
Ús: python -m bot.misterwho [Quique|Fentaniños]
"""
import sys

from playwright.sync_api import sync_playwright

from bot.mister import login, new_context as mister_context
from bot.misterplan import LEAGUES
from bot.mistermarket import league_data
from bot.web import login_sorareinside, new_context, save_session

only = sys.argv[1] if len(sys.argv) > 1 else None
with sync_playwright() as p:
    b = p.chromium.launch()
    sctx = new_context(b, "sorareinside"); spg = sctx.new_page(); login_sorareinside(spg); save_session(sctx, "sorareinside")
    pg = mister_context(b).new_page()
    login(pg)
    rep, cache = [], {}
    for name, cid, (country, league), minimum in LEAGUES:
        if only and only != name:
            continue
        bal, squad, market, have, cap = league_data(b, pg, spg, cid, country, league, rep, cache)
        for q in squad:
            src = q.get("si") or q.get("ff") or q.get("jp") or {}
            print(f"::notice title={name}::{q['short']} | {q['name']} | equip Mister: {q.get('team')} | {q.get('src')}: "
                  f"{src.get('name')} ({str(src.get('key', '')).split('/')[-1]}) {q.get('pct')}%")
    for r in rep:
        print("::notice title=rep::" + r)
    b.close()
