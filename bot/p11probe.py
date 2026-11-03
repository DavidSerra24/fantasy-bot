"""Prova (només lectura): text i HTML de la pàgina d'un equip de Predicted11 (onze probable de FutbolFantasy)."""
import sys

from playwright.sync_api import sync_playwright

from bot.web import login_predicted11, new_context

comp, slug = (sys.argv[1:3] + ["champions", "bodo-glimt"])[0:2] if len(sys.argv) > 2 else ("champions", "bodo-glimt")
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = new_context(b, "predicted11")
    pg = ctx.new_page()
    login_predicted11(pg)
    pg.goto(f"https://www.predicted11.com/es/{comp}/equipo/{slug}", wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)
    t = pg.inner_text("body")
    i = t.lower().find("futbolfantasy")
    print("::notice title=text::" + t[max(0, i - 1500):i + 2500].replace("\n", " ¶ ")[:3900])
    h = pg.evaluate("""() => { const el = [...document.querySelectorAll('*')].filter(e => /futbolfantasy/i.test(e.textContent) && e.children.length < 40).pop();
        let x = el; for (let k = 0; k < 4 && x && x.parentElement; k++) x = x.parentElement; return x ? x.outerHTML : 'cap'; }""")
    for k in range(0, min(len(h), 15000), 3800):
        print(f"::notice title=html{k}::" + h[k:k + 3800])
    b.close()
