"""Diagnosi (només lectura): quiniela del Mister tal com es veu al navegador."""
import json

from playwright.sync_api import sync_playwright

from bot.mister import login, new_context
from bot.misterpool import open_pool

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    login(pg)
    for cid, sw in ((2519290, "pool-public"), (2519290, "pool-private"), (2499621, "pool-private")):
        try:
            rows = open_pool(pg, cid, sw)
            print(f"::notice title=pool {cid} {sw}::" + json.dumps([(r['home'], r['away'], r['sel'], r['locked']) for r in rows], ensure_ascii=False)[:2500])
        except Exception as e:
            print(f"::notice title=pool {cid} {sw}::{type(e).__name__}: {str(e)[:300]}")
        try:
            print(f"::notice title=pool text {cid} {sw}::" + pg.locator(".sw-content").first.inner_text()[:1500].replace("\n", " · "))
        except Exception as e:
            print(f"::notice title=pool text::{e}")
    b.close()
