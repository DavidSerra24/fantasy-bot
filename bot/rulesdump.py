"""Llegeix les regles dels jocs extres de FutbolFantasy (no canvia res)."""
from playwright.sync_api import sync_playwright
from bot import ff
from bot.web import new_context, login_futbolfantasy, inject

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = new_context(b, "futbolfantasy")
    pg = ctx.new_page()
    login_futbolfantasy(pg)
    cs = ff.cards(pg)
    for c in cs:
        if any(c["label"].startswith(x + " ·") for x in ["LaLiga", "LaLiga 2", "Premier League", "Serie A", "Champions", "Europa League"]):
            continue
        card = pg.locator(f"#juego-{c['id']}")
        card.locator("text=REGLAS").first.click()
        pg.locator(".modal.show").wait_for(timeout=10000)
        pg.wait_for_timeout(800)
        txt = pg.locator(".modal.show").inner_text()
        txt = txt.split("Estadísticas puntuables")[0].replace("\n", " ")
        print(f"::notice title=r::{c['label']} | {c['title']} | tanca {c['end']} | buit {c['empty']} | {txt[:700]}")
        ff.close_modal(pg)
    b.close()
