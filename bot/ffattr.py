"""Diagnosi (26/11): atributs dels jugadors a la pàgina d'un partit de futbolfantasy.com."""
import sys
from playwright.sync_api import sync_playwright
from bot.ff import FF
from bot.web import login_futbolfantasy, new_context
url = sys.argv[1] if len(sys.argv) > 1 else f"{FF}/partidos/24398-iberia-1999-getafe"
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_context(b, "futbolfantasy"); pg = ctx.new_page(); login_futbolfantasy(pg)
    pg.goto(url, wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(3000)
    out = pg.evaluate("""() => [...document.querySelectorAll('[class*="jugador_"]')].slice(0, 6).map(e => {
        const a = e.querySelector('a[data-probabilidad]');
        return (e.className + ' || ' + (a ? [...a.attributes].map(x => x.name + '=' + x.value).join(' ') : 'cap') + ' || ' + e.innerText.replace(/\\s+/g,' ').slice(0,80));
    })""")
    for l in out:
        print("::notice title=attr::" + l[:900])
    txt = pg.inner_text("body")
    i = txt.find("Getafe")
    print("::notice title=text::" + txt[:1500].replace("\\n", " | "))
