"""Reconeixement (només lectura): on surt l'oferta del Mister (feed, mercat, notificacions)."""
import re
from playwright.sync_api import sync_playwright
from bot.mister import U, new_context, login

LOG = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    try:
        login(pg)
        pg.goto(f"{U}/action/change?id_community=2519290", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        LOG.append("OFFERS EL: " + pg.evaluate("""() => [...document.querySelectorAll('*')].filter(e => /ofertas recibidas/i.test(e.innerText||'') && e.children.length < 4).slice(-3)
            .map(e => e.tagName + '.' + e.className + '#' + e.id + ' href=' + (e.getAttribute('href')||'') + ' ' + Object.keys(e.dataset).map(k => k + '=' + e.dataset[k]).join(',') + ' :: ' + e.outerHTML.replace(/\\s+/g, ' ').slice(0, 600)).join(' || ')"""))
        reqs = []
        pg.on("request", lambda r: reqs.append(r.method + " " + r.url.split("mundodeportivo.com")[-1] + " " + (r.post_data or "")[:200]) if "mundodeportivo.com/ajax" in r.url or "twig" in r.url else None)
        pg.locator("text=ofertas recibidas").last.click(); pg.wait_for_timeout(3500)
        LOG.append("REQS: " + " || ".join(reqs))
        LOG.append("AJAX: " + re.sub(r"\s+", " ", pg.evaluate("() => fetch('/ajax/sw/offers-received', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8','X-Requested-With':'XMLHttpRequest'}, body:'post=offers-received'}).then(r=>r.text())"))[:3000])
        LOG.append("SWDATA: " + pg.evaluate("() => { const c=document.querySelector('.sw-content'); if(!c) return 'cap'; return c.innerText.replace(/\\s+/g,' ').slice(0,600) + ' ## ' + [...c.querySelectorAll('*')].filter(e=>Object.keys(e.dataset).length || e.tagName=='BUTTON').map(e=>e.tagName+'.'+e.className.toString().slice(0,50)+' «'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,25)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,160)).slice(0,40).join(' | '); }"))
        LOG.append("AFTER: " + pg.evaluate("""() => { const c = [...document.querySelectorAll('.sw-content, .popup, [class*=popup]')].filter(e => e.offsetParent !== null).pop(); if (!c) return 'cap';
            return c.className + ' :: ' + c.innerText.replace(/\\s+/g, ' ').slice(0, 900) + ' ## ' + [...c.querySelectorAll('button,a,[data-sku],[data-ajax]')].filter(e => e.offsetParent !== null).map(e => e.tagName + '.' + e.className.toString().slice(0, 50) + '#' + e.id + ' «' + (e.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 25) + '» ' + Object.keys(e.dataset).map(k => k + '=' + e.dataset[k]).join(',').slice(0, 160)).join(' | '); }"""))
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
