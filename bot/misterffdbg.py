"""Diagnosi (27/11): què mostra «Mis equipos» de cada jugador (%) i l'apartat de canvis de %."""
from playwright.sync_api import sync_playwright
from bot import misterff as M
from bot.web import login_futbolfantasy, new_context
with sync_playwright() as p:
    b = p.chromium.launch(); pg = new_context(b, "futbolfantasy").new_page(); login_futbolfantasy(pg)
    pg.goto(M.URL, wait_until="domcontentloaded"); pg.wait_for_timeout(5000)
    print("::notice title=jugador::" + pg.evaluate("() => { const a = [...document.querySelectorAll('a.juggador')].find(a => a.offsetParent !== null); const w = a && (a.closest('[class*=jugador]') || a.parentElement); return w ? w.outerHTML.slice(0, 1800) : 'cap'; }"))
    print("::notice title=textos::" + pg.evaluate("() => [...document.querySelectorAll('a.juggador')].filter(a => a.offsetParent !== null).slice(0, 8).map(a => a.innerText.replace(/\\s+/g, ' ')).join(' | ')"))
    txt = pg.inner_text("body")
    for k in ("cambi", "Cambi", "variaci", "Variaci", "subid", "bajad", "Últimos"):
        i = txt.find(k)
        if i >= 0:
            print("::notice title=text " + k + "::" + txt[max(0, i - 200):i + 900].replace("\n", " | "))
            break
    print("::notice title=blocs::" + str(pg.evaluate("() => [...document.querySelectorAll('h2, h3, h4, .titulo, .title')].map(e => e.innerText.trim()).filter(t => t && t.length < 60).slice(0, 30)")))
