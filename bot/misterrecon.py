"""Reconeixement (només lectura): "Mis equipos" de FutbolFantasy (/seguimiento/laliga/1)."""
import re
from playwright.sync_api import sync_playwright
from bot.web import new_context, login_futbolfantasy

LOG = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "futbolfantasy").new_page()
    try:
        login_futbolfantasy(pg)
        pg.goto("https://www.futbolfantasy.com/seguimiento/laliga/1", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        LOG.append("URL " + pg.url)
        LOG.append("BODY: " + pg.inner_text("body")[:3000].replace("\n", " / "))
        LOG.append("CTRL: " + pg.evaluate("""() => [...document.querySelectorAll('a,button,input,select')].filter(e=>e.offsetParent!==null)
            .map(e=>e.tagName+'.'+e.className.toString().slice(0,40)+'#'+e.id+'['+(e.name||'')+'|'+(e.type||'')+'|'+(e.placeholder||'')+'] «'+(e.innerText||e.value||'').trim().replace(/\\s+/g,' ').slice(0,25)+'» '+(e.getAttribute('href')||'').slice(0,60)+' '+(e.getAttribute('onclick')||'').slice(0,60)+' '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,80))
            .filter(t=>!/\\/(noticias|lesionados|sanciones)\\//.test(t)).slice(0,140).join(' | ')"""))
        # un jugador de la llista: estructura HTML
        LOG.append("ROW: " + pg.evaluate("""() => { const a=[...document.querySelectorAll('a[href*="/jugadores/"]')].find(e=>e.offsetParent!==null); if(!a) return 'cap';
            let c=a; for(let i=0;i<4;i++) c=c.parentElement; return c.outerHTML.replace(/<svg.*?<\\/svg>/gs,'').replace(/\\s+/g,' ').slice(0,3000); }"""))
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
