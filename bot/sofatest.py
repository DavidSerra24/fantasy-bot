import datetime as dt
from playwright.sync_api import sync_playwright
from bot import sofascore as S
from bot.web import new_context
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_context(b, "sofascore")
    pg = S.open_page(ctx)
    print(f"::notice title=s::pàgina: {pg.title()[:80]}")
    for comp, day in [("europa-league", dt.date(2026,10,22)), ("serie-a", dt.date(2026,10,23)), ("laliga", dt.date(2026,10,23))]:
        try:
            ev = S.events(pg, day, comp)
            print(f"::notice title=s::{comp} {day}: {len(ev)} partits; primer: {ev[0] if ev else None}")
            if ev:
                l = S.lineups(pg, ev[0]["id"])
                print(f"::notice title=s::  onzes {ev[0]['home']}-{ev[0]['away']}: confirmat={l['confirmed']} local={l['home'][:4]} visitant={l['away'][:4]}")
        except Exception as e:
            print(f"::notice title=s::{comp}: ERROR {type(e).__name__} {str(e)[:200]}")
    b.close()
