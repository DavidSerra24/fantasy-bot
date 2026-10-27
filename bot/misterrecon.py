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
        resp = []
        pg.on("response", lambda r: resp.append(r) if "/ajax/sw/substitution" in r.url or "substitution.twig" in r.url else None)
        pg.locator("#slot-11").click(); pg.wait_for_timeout(3000)
        for r in resp:
            try:
                if "twig" in r.url: continue
                LOG.append("RESP " + r.url.split("mundodeportivo.com")[-1] + ": " + re.sub(r"\s+", " ", r.text())[:5000])
            except Exception as e:
                LOG.append(f"RESP err {e}")
        LOG.insert(0, "SWDATA: " + pg.evaluate("() => { const c=document.querySelector('.sw-content'); if(!c) return 'cap'; return [...c.querySelectorAll('*')].filter(e=>Object.keys(e.dataset).length || e.tagName=='BUTTON' || e.getAttribute('onclick')).map(e=>e.tagName+'.'+e.className.toString().slice(0,50)+' «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,25)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,150)).slice(0,40).join(' | '); }"))
        LOG.append("SW DOM: " + pg.evaluate("() => { const c=[...document.querySelectorAll('.sw, [class*=sw-], #sw, .switch-view, .side-view')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className+'#'+e.id+' n='+e.querySelectorAll('button').length); return c.join(' | '); }"))
        LOG.append("SUB BUTTONS: " + pg.evaluate("() => [...document.querySelectorAll('button,a')].filter(e=>e.offsetParent!==null && e.dataset.event && !/lineup-player|gameweek|credits|formation/.test(e.className+e.dataset.event)).map(e=>e.tagName+'.'+e.className.toString().slice(0,60)+' «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,30)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,180)).slice(0,30).join(' | ')"))
        LOG.append("SUB TEXT: " + pg.evaluate("() => { const e=[...document.querySelectorAll('[class*=sw], [id*=substitution], .panel')].filter(e=>e.offsetParent!==null && /substitu/i.test(e.className+e.id+e.innerHTML.slice(0,500))).pop(); return e ? e.className+' :: '+e.innerText.replace(/\\s+/g,' ').slice(0,700) : 'cap'; }"))
        pg.keyboard.press("Escape"); pg.wait_for_timeout(1000)
        pg.goto(U + "/team?gameweek=11", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
        pg.evaluate("() => document.querySelector('button[data-popup=formation]').click()"); pg.wait_for_timeout(2500)
        LOG.append("FORMATION: " + pg.evaluate("() => [...document.querySelectorAll('button,a,input')].filter(e=>e.offsetParent!==null && /\\d-\\d-\\d|formation|Guardar|Desar|Acceptar/i.test((e.innerText||'')+e.className+(e.name||'')+(e.value||''))).map(e=>e.tagName+'.'+e.className.toString().slice(0,60)+'#'+e.id+'['+(e.name||'')+'='+(e.value||'')+'] «'+(e.innerText||'').trim().slice(0,20)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,120)).slice(0,25).join(' | ')"))
        LOG.append("REQS: " + " || ".join(reqs[-6:]))
        pg.keyboard.press("Escape"); pg.wait_for_timeout(1000)
        pg.evaluate("() => document.querySelector('button[data-popup=auto-lineup]').click()"); pg.wait_for_timeout(2500)
        LOG.append("AUTO: " + pg.evaluate("() => { const f=[...document.querySelectorAll('form')].filter(f=>f.offsetParent!==null).pop(); return f ? f.outerHTML.replace(/<svg.*?<\\/svg>/gs,'').replace(/\\s+/g,' ').slice(0,2500) : 'cap form'; }"))
        pg.keyboard.press("Escape")
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
