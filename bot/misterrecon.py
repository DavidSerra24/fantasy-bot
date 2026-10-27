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
        for path in ("/feed", "/market"):
            pg.goto(U + path, wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
            t = pg.inner_text("body")
            for m in re.finditer(r"(?i)ofert|offer", t):
                LOG.append(f"{path} @{m.start()}: " + t[max(0, m.start() - 200):m.start() + 200].replace("\n", " / "))
            LOG.append(f"{path} rows Martín/Rey: " + pg.evaluate("""() => [...document.querySelectorAll('li, .card, article')].filter(e => /M\\. Martín|O\\. Rey|Mario Martín|Oriol Rey/.test(e.innerText) && e.innerText.length < 700)
                .slice(0, 6).map(e => e.className + ' :: ' + e.innerText.replace(/\\s+/g, ' ').slice(0, 300) + ' ## ' + [...e.querySelectorAll('button,a')].map(x => x.className.toString().slice(0, 50) + ' «' + (x.innerText || '').trim().slice(0, 20) + '» ' + Object.keys(x.dataset).map(k => k + '=' + x.dataset[k]).join(',').slice(0, 120)).join(' | ')).join(' || ')"""))
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
        btn = pg.locator('li button.btn-bid[data-id_player="58125"]').first
        if btn.count():
            btn.click(); pg.wait_for_timeout(3000)
            LOG.append("MARKET POPUP Martín: " + pg.evaluate("() => { const f=[...document.querySelectorAll('form')].filter(f=>f.offsetParent!==null).pop(); let c=f; for(let i=0;i<6&&c;i++) c=c.parentElement; return c ? c.innerText.replace(/\\s+/g,' ').slice(0,900) + ' ## ' + [...c.querySelectorAll('button,a,input')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className.toString().slice(0,40)+'#'+e.id+'['+(e.name||'')+'='+(e.value||'')+'] «'+(e.innerText||'').trim().slice(0,20)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,100)).join(' | ') : 'cap'; }"))
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
