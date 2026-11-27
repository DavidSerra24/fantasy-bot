"""Diagnosi (27/11): per què Vlachodimos no queda afegit a «Mis equipos»."""
from playwright.sync_api import sync_playwright
from bot import misterff as M
from bot.web import login_futbolfantasy, new_context
with sync_playwright() as p:
    b = p.chromium.launch(); pg = new_context(b, "futbolfantasy").new_page(); login_futbolfantasy(pg)
    cur = M.ff_list(pg)
    print("::notice title=llista::" + f"{len(cur)}: " + ", ".join(x["n"] for x in cur))
    print("::notice title=opcions::" + str(pg.evaluate("() => [...document.querySelectorAll('a.select-option-link')].map(a => [a.innerText.trim().slice(0,40), a.offsetParent !== null, a.getAttribute('onclick') || a.className].join(' · '))"))[:1500])
    pg.on("console", lambda m: print("::notice title=console::" + m.text[:200]))
    print("::notice title=seccions::" + str(pg.evaluate("() => [...document.querySelectorAll('[class*=titular], [class*=suplente], .once-titular, .once-suplentes')].slice(0,6).map(e => e.className + ' ' + e.querySelectorAll('a.juggador').length)")))
    pg.evaluate("""() => [...document.querySelectorAll('a.select-option-link')].find(a => a.offsetParent !== null && /Suplente/.test(a.innerText)).click()""")
    pg.locator("#seleccionar-respuesta-input").wait_for(state="visible", timeout=10000)
    inp = pg.locator("#seleccionar-respuesta-input"); inp.fill("Vlachodimos"); inp.dispatch_event("keyup"); pg.wait_for_timeout(2500)
    res = pg.evaluate("""() => [...document.querySelectorAll('#buscador-selector a.ls-follow')].filter(a => a.offsetParent !== null).map(a => ({ n: a.innerText.trim(), id: a.dataset.jugador }))""")
    print("::notice title=cerca::" + str(res))
    html = pg.evaluate("() => { const a = [...document.querySelectorAll('#buscador-selector a.ls-follow')].find(a => a.offsetParent !== null); return a ? a.outerHTML.slice(0, 600) : 'cap'; }")
    print("::notice title=enllaç::" + html)
    if res:
        pg.on("response", lambda r: print("::notice title=resp::" + r.url[:150] + " " + str(r.status)) if "futbolfantasy" in r.url and not r.url.endswith((".js", ".css", ".png", ".jpg", ".webp", ".svg", ".woff2")) else None)
        pg.evaluate("(id) => { const a = [...document.querySelectorAll('#buscador-selector a.ls-follow[data-jugador=\"' + id + '\"]')].find(a => a.offsetParent !== null); a && a.click(); }", res[0]["id"])
        pg.wait_for_timeout(4000)
        print("::notice title=després::" + pg.evaluate("() => (document.querySelector('.swal2-popup, .toast, .alert, .modal.show') || {innerText: 'cap missatge'}).innerText.slice(0, 300)"))
        M.close(pg)
        cur2 = M.ff_list(pg)
        print("::notice title=llista2::" + f"{len(cur2)}: " + ", ".join(x["n"] for x in cur2))
