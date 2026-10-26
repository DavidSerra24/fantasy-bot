"""Reconeixement (només lectura): onzes probables de LaLiga Hypermotion a jornadaperfecta.com."""
from playwright.sync_api import sync_playwright
from bot.mister import new_context

LOG = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    try:
        pg.goto("https://www.jornadaperfecta.com/segunda/onces-posibles/", wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(4000)
        for t in ["Aceptar", "ACEPTAR", "Accept", "Consentir", "De acuerdo"]:
            el = pg.get_by_text(t, exact=True).first
            if el.count() and el.is_visible():
                el.click(); pg.wait_for_timeout(1500); break
        LOG.append("TEXT: " + pg.inner_text("body")[:1500].replace("\n", " / "))
        ver = pg.get_by_text("Ver 11").first
        LOG.append(f"ver11 count: {pg.get_by_text('Ver 11').count()}")
        LOG.append("VER html: " + pg.evaluate("() => { const e=[...document.querySelectorAll('a,button')].find(x=>/Ver 11/.test(x.innerText)); return e ? e.outerHTML.slice(0,600) : 'cap'; }"))
        if ver.count():
            ver.click(); pg.wait_for_timeout(4000)
            LOG.append(f"after click URL: {pg.url}")
            LOG.append("AFTER text: " + pg.inner_text("body")[:3000].replace("\n", " / "))
            LOG.append("AFTER players html: " + pg.evaluate("() => { const e=document.querySelector('[class*=jugador], [class*=player], [class*=once]'); return e ? e.className + ' :: ' + e.outerHTML.replace(/<svg.*?<\\/svg>/g,'').replace(/<img[^>]*>/g,'').replace(/\\s+/g,' ').slice(0,2500) : 'cap'; }"))
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1200:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
