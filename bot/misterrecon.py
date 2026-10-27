"""Reconeixement (només lectura): finestra d'una puja ja feta (per retirar-la)."""
from playwright.sync_api import sync_playwright
from bot.mister import U, new_context, login

LOG = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    try:
        login(pg)
        pg.goto(f"{U}/action/change?id_community=2499621", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
        LOG.append("MINE: " + pg.evaluate("() => [...document.querySelectorAll('li[data-owner=\"0\"]')].filter(l=>l.querySelector('.btn-bid.btn--accent')).map(l=>l.querySelector('.name').innerText.trim()+' tid='+((l.querySelector('img.team-logo')||{}).src||'')).join(' | ')"))
        pg.locator("li[data-owner='0'] .btn-bid.btn--accent").first.click(); pg.wait_for_timeout(3000)
        LOG.append("POPUP: " + pg.evaluate("() => { const f=document.getElementById('form-bid'); const r=f?f.getBoundingClientRect():{top:0,bottom:2000}; return [...document.querySelectorAll('button,a')].filter(e=>e.offsetParent!==null&&!e.closest('li')).filter(e=>{const q=e.getBoundingClientRect(); return q.top>=r.top-500&&q.top<=r.bottom+500;}).map(e=>e.tagName+'.'+e.className+'#'+e.id+' «'+(e.innerText||'').trim().slice(0,30)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',')).slice(-12).join(' | '); }"))
        LOG.append("FORM: " + pg.evaluate("() => (document.getElementById('form-bid')||{}).outerHTML?.replace(/<svg.*?<\\/svg>/g,'').replace(/\\s+/g,' ').slice(0,1500) || 'cap'"))
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1200:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
