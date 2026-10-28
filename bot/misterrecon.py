"""Reconeixement (només lectura): Quiniela del Mister."""
import re
from playwright.sync_api import sync_playwright
from bot.mister import U, new_context, login

LOG = []
DUMP = """() => { const c=[...document.querySelectorAll('.sw-content')].filter(e=>e.offsetParent!==null).pop() || document.body;
  return c.innerText.replace(/\\s+/g,' ').slice(0,1500) + ' ## ' + [...c.querySelectorAll('button,a,input,select,[data-sw],[data-popup]')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className.toString().slice(0,50)+'#'+e.id+'['+(e.name||'')+'='+(e.value||'')+'] «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,25)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,140)).slice(0,60).join(' | '); }"""
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    reqs = []
    pg.on("request", lambda r: reqs.append(r.method + " " + r.url.split("mundodeportivo.com")[-1] + " " + (r.post_data or "")[:200]) if "mundodeportivo.com/ajax" in r.url or "twig" in r.url else None)
    try:
        login(pg)
        for cid in (2519290, 2499621):
            pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
            pg.goto(U + "/feed", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
            LOG.append(f"[{cid}] quiniela links: " + pg.evaluate("() => [...document.querySelectorAll('a,button,div')].filter(e=>/quiniela|pool/i.test((e.innerText||'')+' '+e.className+' '+Object.values(e.dataset).join(' ')) && e.children.length<5).slice(0,12).map(e=>e.tagName+'.'+e.className.toString().slice(0,40)+' «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,40)+'» '+(e.getAttribute('href')||'')+' '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',')).join(' | ')"))
            reqs.clear()
            el = pg.locator("[data-sw='pool-public']").first
            if el.count():
                el.evaluate("e => e.click()"); pg.wait_for_timeout(4000)
                LOG.append(f"[{cid}] REQS: " + " || ".join(reqs))
                LOG.append(f"[{cid}] POOL: " + pg.evaluate(DUMP))
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
