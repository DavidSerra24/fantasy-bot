"""Reconeixement (només lectura): on surten les ofertes del Mister pels meus jugadors en venda."""
import re
from playwright.sync_api import sync_playwright
from bot.mister import U, new_context, login

LOG = []


def note(t):
    LOG.append(t)


def compact(h):
    h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
    h = re.sub(r"<(img|source|link)[^>]*>", "", h)
    return re.sub(r"\s+", " ", h)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    try:
        login(pg)
        for cid in (2519290, 2499621):
            pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
            pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
            rows = pg.evaluate("""() => [...document.querySelectorAll('.player-row')].map(r => { const box = r.closest('li') || r.parentElement;
                return (box.innerText||'').replace(/\\s+/g,' ').slice(0,160) + ' ## ' + [...box.querySelectorAll('button')].map(e=>e.className+' «'+(e.innerText||'').trim().slice(0,20)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',')).join(' | '); })
                .filter(t => /venda|venta|oferta/i.test(t))""")
            note(f"[{cid}] TEAM on sale: " + " || ".join(rows))
            # finestra de venda d'un jugador que ja està en venda
            btn = pg.locator('button.btn-popup[data-popup="sale"]')
            for i in range(btn.count()):
                box = btn.nth(i).evaluate("e => (e.closest('li')||e.parentElement).innerText")
                if re.search(r"venda|venta|oferta", box, re.I):
                    btn.nth(i).click(); pg.wait_for_timeout(3000)
                    note(f"[{cid}] SALE POPUP: " + pg.evaluate("() => [...document.querySelectorAll('form')].filter(f=>f.offsetParent!==null).map(f=>f.outerHTML).join(' ### ')").replace("\n", " ")[:6000])
                    note(f"[{cid}] SALE POPUP text: " + pg.evaluate("() => { const f=document.querySelector('form:not([hidden])'); let c=f; for(let i=0;i<5&&c;i++) c=c.parentElement; return c? c.innerText.replace(/\\s+/g,' ').slice(0,800):''; }"))
                    pg.keyboard.press("Escape"); pg.wait_for_timeout(1000)
                    break
            pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
            note(f"[{cid}] MARKET tabs: " + pg.evaluate("() => [...document.querySelectorAll('a,button')].filter(e=>e.offsetParent!==null && /venda|venta|oferta|ofertes|operac/i.test(e.innerText)).map(e=>e.tagName+'.'+e.className+' «'+e.innerText.trim().slice(0,30)+'» '+(e.getAttribute('href')||'')+' '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',')).slice(0,15).join(' | ')"))
            note(f"[{cid}] MARKET mine: " + pg.evaluate("() => [...document.querySelectorAll('li[data-price]')].filter(l=>l.dataset.owner!=='0' && /oferta|Acceptar|Aceptar/i.test(l.innerText)).map(l=>l.dataset.owner+': '+l.innerText.replace(/\\s+/g,' ').slice(0,200)+' ## '+[...l.querySelectorAll('button')].map(e=>e.className+' «'+e.innerText.trim().slice(0,20)+'» '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',')).join(' | ')).slice(0,6).join(' || ')"))
            pg.goto(U + "/feed", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
            note(f"[{cid}] FEED oferta: " + pg.evaluate("() => [...document.querySelectorAll('.card, li, article')].filter(e=>/oferta/i.test(e.innerText) && e.innerText.length<600).map(e=>e.className+': '+e.innerText.replace(/\\s+/g,' ').slice(0,250)+' ## '+[...e.querySelectorAll('button,a')].map(x=>x.tagName+'.'+x.className+' «'+x.innerText.trim().slice(0,20)+'» '+(x.getAttribute('href')||'')+' '+Object.keys(x.dataset).map(k=>k+'='+x.dataset[k]).join(',')).join(' | ')).slice(0,6).join(' || ')"))
    except Exception:
        import traceback
        note("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
