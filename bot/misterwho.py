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
        lines = []
        for q in squad:
            src = q.get("si") or q.get("ff") or q.get("jp") or {}
            lines.append(f"{q['short']} | {q['name']} | {q.get('P')} | equip Mister: {q.get('team')} | {q.get('src')}: "
                         f"{src.get('name')} ({str(src.get('key', '')).split('/')[-1]}) {q.get('pct')}%")
        print(f"::notice title={name}::" + " ¶ ".join(lines))
        if cache.get("ffp"):
            for k in sys.argv[2:]:
                print(f"::notice title=FF {k}::" + ", ".join(f"{e['name']} {e['pct']}% ({e['key'].split('/')[-1]})" for e in cache["ffp"] if k in e["key"])[:5000])
        from bot.mistermarket import si_next
        from bot.sources import si_entries
        sid = si_next(spg, country, league)
        for t in sid.get("_order", []):
            if any(k in t.lower() for k in (sys.argv[2:] or ["albacete"])):
                rows = sid.get(t)
                print(f"::notice title=SI {t}::" + str(rows)[:5000])
    for r in rep:
        print("::notice title=rep::" + r)
    b.close()
