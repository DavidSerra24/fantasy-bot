"""Diagnosi ràpida (26/11): jugadors posats en un joc de FutbolFantasy."""
import sys
from playwright.sync_api import sync_playwright
from bot import ff
from bot.ff import FF
from bot.web import inject, login_futbolfantasy, new_context
jid = sys.argv[1] if len(sys.argv) > 1 else "1078"
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_context(b, "futbolfantasy"); pg = ctx.new_page(); login_futbolfantasy(pg)
    c = next((c for c in ff.cards(pg) if c["id"] == jid), None)
    print("::notice title=joc::" + str({k: c.get(k) for k in ("label", "title", "empty", "ids", "end")} if c else "no trobat"))
    print("::notice title=caselles::" + str(pg.evaluate("(id) => __ff.slots(id)", jid)))
