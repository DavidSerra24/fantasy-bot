"""Diagnosi (26/11): equips d'una competició a SorareInside."""
import sys, datetime as dt
from playwright.sync_api import sync_playwright
from bot import si
from bot.web import login_sorareinside, new_context
country, league = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else ("Europe", "UEFA Conference League")
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_context(b, "sorareinside"); pg = ctx.new_page(); login_sorareinside(pg)
    d = si.extract_league(pg, country, league, dt.date.today(), use_cache=False)
    order = d.get("_order") or []
    print("::notice title=SI equips::" + " | ".join(order)[:3000])
    for t in order:
        if "etafe" in t or "beria" in t.lower():
            rows = d.get(t) or []
            print("::notice title=SI " + t + "::" + ", ".join(f"{p_['name']} {p_.get('pct')}% PS {p_.get('ps')}" for r in rows for p_ in r)[:2000])
