"""Reconeixement (només lectura): buscador de jugadors del Mister."""
import re
from playwright.sync_api import sync_playwright
from bot.mister import U, new_context, login

LOG = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    reqs = []
    pg.on("request", lambda r: reqs.append(r.method + " " + r.url.split("mundodeportivo.com")[-1] + " " + (r.post_data or "")[:200]) if "mundodeportivo.com/ajax" in r.url or "/api" in r.url else None)
    try:
        login(pg)
        pg.goto(f"{U}/action/change?id_community=2499621", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        pg.goto(U + "/search", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
        LOG.append("INPUTS: " + pg.evaluate("() => [...document.querySelectorAll('input,select,button')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className.toString().slice(0,40)+'#'+e.id+'['+(e.name||'')+'|'+(e.type||'')+'|'+(e.placeholder||'')+'] '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,80)).slice(0,25).join(' | ')"))
        inp = pg.locator("input[type=search]:visible, input[type=text]:visible").first
        reqs.clear()
        inp.fill("Rober"); inp.dispatch_event("input"); inp.dispatch_event("keyup"); pg.wait_for_timeout(3000)
        LOG.append("REQS: " + " || ".join(reqs))
        LOG.append("RESULTS: " + pg.evaluate("() => [...document.querySelectorAll('a[href*=\"players/\"]')].filter(e=>e.offsetParent!==null).slice(0,15).map(a=>a.getAttribute('href')+' «'+a.innerText.replace(/\\s+/g,' ').trim().slice(0,60)+'» '+((a.closest('li,div')||a).querySelector('img.team-logo')||{}).src).join(' | ')"))
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
