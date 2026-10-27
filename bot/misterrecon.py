"""Reconeixement (només lectura): finestres de treure i afegir jugador a "Mis equipos" de FutbolFantasy."""
from playwright.sync_api import sync_playwright
from bot.web import new_context, login_futbolfantasy

LOG = []
MODAL = """() => { const m=document.querySelector('.modal.show'); if(!m) return 'cap modal';
  return m.id+' :: '+m.innerText.replace(/\\s+/g,' ').slice(0,700)+' :: '+[...m.querySelectorAll('a,button,input,.sel-item')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className.toString().slice(0,40)+'#'+e.id+' «'+(e.innerText||e.value||'').trim().replace(/\\s+/g,' ').slice(0,30)+'» '+(e.getAttribute('onclick')||'').slice(0,140)+' '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,80)).slice(0,40).join(' | '); }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "futbolfantasy").new_page()
    try:
        login_futbolfantasy(pg)
        pg.goto("https://www.futbolfantasy.com/seguimiento/laliga/1", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        LOG.append("CLICK: " + str(pg.evaluate("""() => { const a=[...document.querySelectorAll('a.juggador')].find(a=>a.offsetParent!==null && a.innerText.trim().startsWith('Mario')); if(!a) return 'no'; a.click(); return 'ok'; }""")))
        pg.wait_for_timeout(2500)
        LOG.append("PLAYER MODAL: " + pg.evaluate(MODAL))
        pg.keyboard.press("Escape"); pg.wait_for_timeout(1200)
        pg.evaluate("""() => [...document.querySelectorAll('a.select-option-link')].find(a=>a.offsetParent!==null && /Suplente/.test(a.innerText)).click()""")
        pg.wait_for_timeout(2500)
        LOG.append("ADD MODAL: " + pg.evaluate(MODAL))
        inp = pg.locator(".modal.show input[type=text], .modal.show input:not([type=hidden])").first
        inp.fill("Jutgla"); inp.dispatch_event("keyup"); pg.wait_for_timeout(2500)
        LOG.append("SEARCH Jutgla: " + pg.evaluate(MODAL))
        pg.keyboard.press("Escape")
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
