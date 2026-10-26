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
        reqs = []
        fp.on("request", lambda r: reqs.append(r.method + " " + r.url[:200] + " " + (r.post_data or "")[:200]) if "frpg" in r.url or "seguimiento" in r.url else None)
        fp.goto("https://www.futbolfantasy.com/seguimiento/laliga/1", wait_until="domcontentloaded"); fp.wait_for_timeout(7000)
        note(f"FF seguimiento URL: {fp.url}")
        note("FF text: " + fp.inner_text("body")[:3500].replace("\n", " / "))
        note("FF els: " + fp.evaluate("() => [...document.querySelectorAll('a,button,select,input,label')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className.toString().split(' ').slice(0,3).join('.')+'['+(e.name||'')+']«'+(e.innerText||e.value||'').trim().replace(/\\s+/g,' ').slice(0,30)+'» '+(e.getAttribute('href')||'')).filter(e=>!/team-|link py-2|social/.test(e)).slice(0,70).join(' | ')"))
        note("FF block html: " + fp.evaluate("() => { const e=document.querySelector('.load-seguimiento-jugadores-new'); return e ? e.outerHTML.replace(/<svg.*?<\\/svg>/g,'').replace(/<img[^>]*>/g,'').replace(/\\s+/g,' ').slice(0,6000) : 'cap'; }"))
        note("FF reqs: " + " | ".join(reqs)[:2500])
    except Exception:
        import traceback
        note("ERR ff: " + traceback.format_exc()[-1200:])
    try:
        pg = new_context(b).new_page(); login(pg)
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        pass  # note("JUTGLA li: " + pg.evaluate("() => { const l=[...document.querySelectorAll('li[data-price]')].find(l=>/Jutgl/.test(l.innerText)); return l ? l.outerHTML.replace(/<svg.*?<\\/svg>/g,'').replace(/<img[^>]*>/g,'').replace(/\\s+/g,' ').slice(0,3000) : 'cap'; }"))
        note("MISTER offer buttons: " + pg.evaluate("() => [...document.querySelectorAll('[data-sw],[data-popup]')].map(e=>(e.dataset.sw||'')+'/'+(e.dataset.popup||'')+' «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,30)+'»').filter((v,i,a)=>a.indexOf(v)===i).slice(0,40).join(' | ')"))
    except Exception:
        import traceback
        note("ERR mister: " + traceback.format_exc()[-1200:])
    flush()
    b.close()
