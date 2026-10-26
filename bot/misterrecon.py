"""Reconeixement (només lectura): finestra de venda del Mister, ofertes rebudes i "Mis equipos" de FutbolFantasy."""
import re
from playwright.sync_api import sync_playwright
from bot.mister import U, new_context, login
from bot import web

LOG = []


def note(t):
    LOG.append(t)


def flush():
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))


VIS = """(sel) => [...document.querySelectorAll(sel)].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className.toString().split(' ').slice(0,4).join('.')+'#'+e.id+'['+(e.name||'')+'='+(e.value||'')+']«'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,30)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',')).slice(-30).join(' | ')"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    try:
        login(pg)
        pg.goto(f"{U}/action/change?id_community=2519290", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
        pg.locator("button.btn-popup:has-text('Gestionar')").first.click(); pg.wait_for_timeout(3000)
        note("GESTIONAR forms: " + pg.evaluate("() => [...document.querySelectorAll('form')].filter(f=>f.offsetParent!==null).map(f=>f.outerHTML.replace(/<svg.*?<\\/svg>/g,'').replace(/\\s+/g,' ').slice(0,2000)).join(' ### ')"))
        note("GESTIONAR buttons: " + pg.evaluate(VIS, "button"))
        # pestanyes de la finestra (Vendre / Clàusula...)
        for t in ["Vendre", "Vender", "Venda", "Mercat"]:
            el = pg.locator(f"button.tab:has-text('{t}'), .tab:has-text('{t}')").first
            if el.count():
                el.click(); pg.wait_for_timeout(2000)
                note(f"TAB {t} forms: " + pg.evaluate("() => [...document.querySelectorAll('form')].filter(f=>f.offsetParent!==null).map(f=>f.outerHTML.replace(/<svg.*?<\\/svg>/g,'').replace(/\\s+/g,' ').slice(0,2000)).join(' ### ')"))
                note(f"TAB {t} buttons: " + pg.evaluate(VIS, "button"))
                break
        pg.keyboard.press("Escape"); pg.wait_for_timeout(800)
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        note("MARKET tabs: " + pg.evaluate(VIS, "a, button.tab, .tabs *"))
        for path in ["/market/offers", "/market/sales", "/market/received"]:
            pg.goto(U + path, wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            note(f"{path}: {pg.url} :: " + pg.inner_text("body")[300:1200].replace("\n", " / "))
    except Exception:
        import traceback
        note("ERR mister: " + traceback.format_exc()[-1200:])
    try:
        ctx = web.new_context(b, "futbolfantasy"); fp = ctx.new_page(); web.login_futbolfantasy(fp)
        fp.goto("https://www.futbolfantasy.com/", wait_until="domcontentloaded"); fp.wait_for_timeout(2500)
        note("FF links equipos: " + fp.evaluate("() => [...new Set([...document.querySelectorAll('a')].filter(a=>/equipo/i.test(a.innerText+a.href)).map(a=>a.innerText.trim().slice(0,30)+' -> '+a.href))].slice(0,25).join(' | ')"))
        for url in ["https://www.futbolfantasy.com/mis-equipos", "https://www.futbolfantasy.com/usuario/mis-equipos", "https://www.futbolfantasy.com/laliga/mis-equipos"]:
            r = fp.goto(url, wait_until="domcontentloaded"); fp.wait_for_timeout(2500)
            note(f"FF {url}: {r.status if r else None} {fp.url} :: " + fp.inner_text("body")[:900].replace("\n", " / "))
    except Exception:
        import traceback
        note("ERR ff: " + traceback.format_exc()[-1200:])
    flush()
    b.close()
