"""Diagnosi (27/11): % llegits de «Mis equipos»."""
from playwright.sync_api import sync_playwright
from bot import misterff as M
from bot.web import login_futbolfantasy, new_context
with sync_playwright() as p:
    b = p.chromium.launch(); pg = new_context(b, "futbolfantasy").new_page(); login_futbolfantasy(pg)
    pc = M.read_pcts(pg); names = {x["id"]: x["n"] for x in M.ff_list(pg)}
    print("::notice title=pcts::" + f"{len(pc)}: " + ", ".join(f"{names.get(k, k)} {v}%" for k, v in pc.items() if k in names))
