"""Prova (només lectura): l'onze que agafaria ff_lineup per a un equip de Predicted11."""
import sys

from playwright.sync_api import sync_playwright

from bot.p11 import CFG, ff_lineup
from bot.web import login_predicted11, new_context

comp, slug = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "predicted11").new_page()
    login_predicted11(pg)
    e = ff_lineup(pg, comp, slug, [], CFG["alias"])
    print("::notice title=onze::" + (f"{e['src']} ({e['updated']}): " + " | ".join(", ".join(q["name"] for q in r) for r in e["rows"]) if e else "res"))
    b.close()
