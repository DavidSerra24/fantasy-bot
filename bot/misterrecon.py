"""Reconeixement de Mister (només lectura): finestra de puja i de venda (HTML de l'AJAX)."""
import re
from playwright.sync_api import sync_playwright
from bot.mister import U, new_context, login

LOG = []


def note(t):
    LOG.append(t)


def flush():
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))


def compact(h):
    h = re.sub(r"<svg.*?</svg>", "", h, flags=re.S)
    h = re.sub(r"<(img|source|link)[^>]*>", "", h)
    return re.sub(r"\s+", " ", h)


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    try:
        login(pg)
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
        li = pg.evaluate("() => { const l=[...document.querySelectorAll('li[data-owner=\"0\"]')][0]; return {pid: l.querySelector('[data-id_player]').dataset.id_player, price: l.dataset.price}; }")
        note(f"player {li}")
        r = pg.evaluate("""(pid) => fetch('/ajax/player-community-info', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8','X-Requested-With':'XMLHttpRequest'},
             body:'id_owner=0&id_player='+pid+'&popup=bid&style=secondary&preload=player-community-info'}).then(r=>r.text())""", li["pid"])
        note("BID AJAX: " + compact(r)[:9000])
        # també el clic real, per veure els scripts/forms que s'hi enganxen
        pg.locator("li[data-owner='0'] .btn-bid").first.click(); pg.wait_for_timeout(3000)
        note("BID DOM forms: " + pg.evaluate("() => [...document.querySelectorAll('form')].filter(f=>f.offsetParent!==null).map(f=>f.outerHTML.replace(/\\s+/g,' ').slice(0,2500)).join(' ### ')"))
        note("POPUP buttons: " + pg.evaluate("() => { const f=document.getElementById('form-bid'); const r=f.getBoundingClientRect(); return [...document.querySelectorAll('button')].filter(e=>e.offsetParent!==null&&!e.closest('form')).filter(e=>{const q=e.getBoundingClientRect(); return q.top>=r.top-400&&q.top<=r.bottom+400;}).map(e=>e.tagName+'.'+e.className+'#'+e.id+' type='+e.type+' «'+(e.innerText||'').trim().slice(0,30)+'» '+(e.getAttribute('onclick')||'')+' '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',')).slice(-12).join(' | '); }"))
        note("MARKET my bids: " + pg.evaluate("() => [...document.querySelectorAll('li[data-price]')].filter(l=>/teva|Tu puja|puja/i.test(l.innerText)).map(l=>l.innerText.replace(/\\s+/g,' ').slice(0,120)).slice(0,5).join(' || ')"))
        note("BID DOM inputs: " + pg.evaluate("() => [...document.querySelectorAll('input,button')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className+'['+e.name+'='+e.value+'] «'+(e.innerText||'').trim().slice(0,30)+'» '+(e.getAttribute('onclick')||'')+' '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',')).slice(-25).join(' | ')"))
    except Exception:
        import traceback
        note("ERR: " + traceback.format_exc()[-1500:])
    flush()
    b.close()
