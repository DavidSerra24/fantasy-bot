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
        def popup(tag):
            pg.wait_for_timeout(2500)
            h = pg.evaluate("() => { const m=[...document.querySelectorAll('.popup, .sw-popup, [class*=popup]')].filter(e=>e.offsetParent!==null&&e.innerText.trim()).pop(); return m ? m.className + ' :: ' + m.innerText.replace(/\\s+/g,' ').slice(0,700) + ' :: ' + [...m.querySelectorAll('button,input,select,a')].map(e=>e.tagName+'.'+e.className.toString().split(' ').slice(0,4).join('.')+'['+(e.name||'')+'='+(e.value||'')+']«'+(e.innerText||'').trim().slice(0,25)+'»').join(' | ').slice(0,1500) : 'cap popup'; }")
            note(tag + ": " + h)
            pg.keyboard.press("Escape"); pg.wait_for_timeout(800)
            for sel in [".popup .btn-close", ".btn-close", "[class*=close]"]:
                c = pg.locator(sel + ":visible").first
                if c.count():
                    try:
                        c.click(timeout=2000)
                    except Exception:
                        pass
                    break
            pg.wait_for_timeout(800)
        pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        pg.locator("button.btn-popup:has-text('Gestionar')").first.click(); popup("GESTIONAR")
        pg.locator("button.lineup-player").first.click(); popup("LINEUP-CLICK")
        note("TEAM sel/tactic: " + pg.evaluate("() => [...document.querySelectorAll('[class*=formation], [class*=tactic], select')].map(e=>e.className+' «'+e.innerText.replace(/\\s+/g,' ').slice(0,80)+'»').slice(0,8).join(' | ')"))
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        pg.locator(".btn-bid").first.click(); popup("BID")
        note("MARKET li attrs: " + pg.evaluate("() => [...document.querySelectorAll('li[data-price]')].slice(0,40).map(li=>[li.dataset.position, li.dataset.price, li.dataset.owner, li.querySelector('.name')?.innerText.trim(), li.querySelector('a.player')?.getAttribute('href')].join(',')).join(' | ')"))
        note("SIDEBAR: " + pg.evaluate("() => [...document.querySelectorAll('a[href*=id_community]')].map(a=>a.innerText.trim()+' -> '+a.getAttribute('href')).join(' | ')"))
    except Exception:
        import traceback
        note("ERR: " + traceback.format_exc()[-1500:])
    note("REQS: " + " | ".join(dict.fromkeys(reqs))[:4000])
    flush()
    b.close()
