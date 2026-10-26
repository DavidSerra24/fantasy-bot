"""Reconeixement (només lectura): "Mis Equipos" de FutbolFantasy i finestra d'ofertes rebudes del Mister."""
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


with sync_playwright() as p:
    b = p.chromium.launch()
    try:
        ctx = web.new_context(b, "futbolfantasy"); fp = ctx.new_page(); web.login_futbolfantasy(fp)
        fp.goto("https://www.futbolfantasy.com/", wait_until="domcontentloaded"); fp.wait_for_timeout(3000)
        note("FF candidates: " + fp.evaluate("() => [...document.querySelectorAll('a,button')].filter(e=>/mis equipos/i.test(e.innerText||e.title||'')).map(e=>e.tagName+' '+(e.href||'')+' «'+e.innerText.trim()+'» '+e.className).join(' | ')"))
        el = fp.get_by_text("Mis Equipos", exact=False).first
        el.click(); fp.wait_for_timeout(4000)
        note(f"FF mis equipos URL: {fp.url}")
        note("FF text: " + fp.inner_text("body")[:3000].replace("\n", " / "))
        note("FF els: " + fp.evaluate("() => [...document.querySelectorAll('a,button,select,input')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className.toString().split(' ').slice(0,3).join('.')+'['+(e.name||'')+']«'+(e.innerText||e.value||'').trim().replace(/\\s+/g,' ').slice(0,30)+'» '+(e.getAttribute('href')||'')).slice(0,80).join(' | ')"))
    except Exception:
        import traceback
        note("ERR ff: " + traceback.format_exc()[-1200:])
    try:
        pg = new_context(b).new_page(); login(pg)
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        note("MISTER offer buttons: " + pg.evaluate("() => [...document.querySelectorAll('[data-sw],[data-popup]')].map(e=>(e.dataset.sw||'')+'/'+(e.dataset.popup||'')+' «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,30)+'»').filter((v,i,a)=>a.indexOf(v)===i).slice(0,40).join(' | ')"))
    except Exception:
        import traceback
        note("ERR mister: " + traceback.format_exc()[-1200:])
    flush()
    b.close()
