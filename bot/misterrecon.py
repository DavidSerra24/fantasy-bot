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
        LOG.append("GW NAV: " + pg.evaluate("""() => [...document.querySelectorAll('*')].filter(e=>e.children.length<6 && /JORNADA\\s*11/i.test(e.innerText||'') && (e.innerText||'').length<80).slice(0,6).map(e=>e.tagName+'.'+e.className.toString().slice(0,60)+' «'+e.innerText.replace(/\\s+/g,' ')+'» '+(e.getAttribute('href')||'')+' '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',')).join(' | ')"""))
        el = pg.locator("button, a").filter(has_text=re.compile(r"JORNADA\s*11", re.I)).first
        LOG.append(f"GW11 clickable: {el.count()}")
        if el.count():
            el.click(); pg.wait_for_timeout(3500)
        LOG.append("URL " + pg.url)
        LOG.append("SLOTS: " + pg.evaluate("() => [...document.querySelectorAll('button.lineup-player')].map(e=>e.id+':'+(e.querySelector('.name')||{}).innerText+':'+e.dataset.position+':gw'+e.dataset.gwid+(e.disabled?':DIS':'')+(e.querySelector('.captain-badge')?':CAP':'')).join(' | ')"))
        LOG.append("CONTROLS: " + pg.evaluate("() => [...document.querySelectorAll('button,select,a.btn')].filter(e=>e.offsetParent!==null && !e.closest('.player-row') && !/lineup-player|btn-match/.test(e.className)).map(e=>e.tagName+'.'+e.className.toString().slice(0,50)+' «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,25)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,120)).slice(0,45).join(' | ')"))
        reqs = []
        pg.on("request", lambda r: reqs.append(r.method + " " + r.url.split("mundodeportivo.com")[-1] + " " + (r.post_data or "")[:200]) if "/ajax/" in r.url or "/api" in r.url else None)
        pg.locator("#slot-7").click(); pg.wait_for_timeout(3000)
        LOG.append("AFTER SLOT-7: " + pg.evaluate("() => [...document.querySelectorAll('button,a')].filter(e=>e.offsetParent!==null && /select|subst|change|swap|candidate|available/i.test(e.className+' '+Object.keys(e.dataset).join(' ')+' '+Object.values(e.dataset).join(' '))).map(e=>e.tagName+'.'+e.className.toString().slice(0,60)+' «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,30)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,150)).slice(0,30).join(' | ')"))
        LOG.append("POPUPS: " + pg.evaluate(VIS))
        LOG.append("REQS: " + " || ".join(reqs[-8:]))
        pg.keyboard.press("Escape"); pg.wait_for_timeout(1000)
        pg.goto(U + "/team?gameweek=11", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
        pg.locator("button[data-popup=formation]").click(); pg.wait_for_timeout(2500)
        LOG.append("FORMATION: " + pg.evaluate(VIS))
        LOG.append("REQS2: " + " || ".join(reqs[-5:]))
        pg.keyboard.press("Escape"); pg.wait_for_timeout(1000)
        pg.locator("button[data-popup=auto-lineup]").click(); pg.wait_for_timeout(2500)
        LOG.append("AUTO: " + pg.evaluate(VIS))
        pg.keyboard.press("Escape")
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
