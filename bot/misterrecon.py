"""Reconeixement de Mister (només lectura): equip, alineació, mercat i peticions internes."""
from playwright.sync_api import sync_playwright
from bot.mister import U, new_context, login

LOG = []


def note(t):
    LOG.append(t)


def flush():
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))


with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    reqs = []
    pg.on("request", lambda r: reqs.append(r.method + " " + r.url.split("?")[0] + " " + (r.post_data or "")[:120]) if "mundodeportivo" in r.url and r.resource_type in ("xhr", "fetch") else None)
    try:
        login(pg)
        note("login ok")
        pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        note("TEAM text: " + pg.inner_text("main" if pg.locator("main").count() else "body")[:2500].replace("\n", " / "))
        note("TEAM html player: " + pg.evaluate("() => (document.querySelector('.player-row, .team__player, li.player, [class*=player-row]')||{}).outerHTML?.slice(0,2500) || 'cap'"))
        note("TEAM classes: " + pg.evaluate("() => [...new Set([...document.querySelectorAll('[class]')].map(e=>e.className.toString().split(' ')[0]).filter(c=>/player|lineup|squad|team/i.test(c)))].join(', ')"))
        note("LINEUP btn html: " + pg.evaluate("() => (document.querySelector('.lineup-player')||{}).outerHTML?.slice(0,1500) || 'cap'"))
        note("TEAM els: " + pg.evaluate("() => [...document.querySelectorAll('button,a,select')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className.toString().split(' ').slice(0,3).join('.')+'«'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,25)+'»').slice(15,90).join(' | ')"))
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        note("MARKET row html: " + pg.evaluate("() => { const b=document.querySelector('.btn-bid'); let c=b; for(let i=0;i<6&&c;i++){c=c.parentElement; if(c.tagName==='LI')break;} return (c||{}).outerHTML?.slice(0,3000)||'cap'; }"))
        note("MARKET n rows: " + str(pg.locator(".btn-bid").count()))
        note("SIDEBAR links: " + pg.evaluate("() => [...document.querySelectorAll('a')].filter(a=>/Fentaniños|Quique/.test(a.innerText)).map(a=>a.innerText.trim()+' -> '+a.getAttribute('href')+' '+(a.getAttribute('data-id')||'')+' '+a.outerHTML.slice(0,200)).join(' || ')"))
        note("GLOBALS: " + pg.evaluate("() => Object.keys(window).filter(k=>/sw|mister|user|community|token|app/i.test(k)).slice(0,40).join(', ')"))
    except Exception:
        import traceback
        note("ERR: " + traceback.format_exc()[-1500:])
    note("REQS: " + " | ".join(dict.fromkeys(reqs))[:4000])
    flush()
    b.close()
