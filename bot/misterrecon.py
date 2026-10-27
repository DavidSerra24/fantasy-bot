"""Reconeixement (només lectura): alineació del Mister (caselles, tàctica, capità, canvi de jugador)."""
import re
from playwright.sync_api import sync_playwright
from bot.mister import U, new_context, login

LOG = []


def compact(h):
    h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
    h = re.sub(r"<(img|source|link)[^>]*>", "", h)
    return re.sub(r"\s+", " ", h)


VIS = """() => { const m=[...document.querySelectorAll('.popup, [class*=popup], .modal')].filter(e=>e.offsetParent!==null).pop(); if(!m) return 'cap';
  return m.className+' :: '+m.innerText.replace(/\\s+/g,' ').slice(0,900)+' :: '+[...m.querySelectorAll('button,a,input,select')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className.toString().slice(0,50)+'#'+e.id+'['+(e.name||'')+'='+(e.value||'')+'] «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,25)+'» '+(e.getAttribute('onclick')||'').slice(0,80)+' '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,120)).slice(0,40).join(' | '); }"""

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    try:
        login(pg)
        pg.goto(f"{U}/action/change?id_community=2519290", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        LOG.append("LINEUP HTML: " + compact(pg.evaluate("() => { const s=document.querySelector('button.lineup-player'); let c=s; for(let i=0;i<5&&c;i++){ c=c.parentElement; if(c.querySelectorAll('button.lineup-player').length>=11) break; } return c? c.outerHTML : 'cap'; }"))[:9000])
        LOG.append("TOP CONTROLS: " + pg.evaluate("() => [...document.querySelectorAll('button,select,a.btn')].filter(e=>e.offsetParent!==null && !e.closest('.player-row') && !/lineup-player/.test(e.className)).map(e=>e.tagName+'.'+e.className.toString().slice(0,50)+' «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,25)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,120)).slice(0,40).join(' | ')"))
        # clic a la casella del porter (slot-0?) per veure la finestra de canvi
        pg.locator("button.lineup-player").first.click(); pg.wait_for_timeout(2500)
        LOG.append("SLOT POPUP: " + pg.evaluate(VIS))
        pg.keyboard.press("Escape"); pg.wait_for_timeout(1000)
        # botó de tàctica
        t = pg.locator("button, a").filter(has_text=re.compile(r"^\s*\d-\d-\d\s*$")).first
        if t.count():
            t.click(); pg.wait_for_timeout(2000)
            LOG.append("TACTIC POPUP: " + pg.evaluate(VIS))
            pg.keyboard.press("Escape")
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
