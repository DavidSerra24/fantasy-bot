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
    pg.on("request", lambda r: reqs.append(r.method + " " + r.url + " " + (r.post_data or "")[:300]) if "mundodeportivo.com/ajax" in r.url or "mundodeportivo.com/api" in r.url else None)
    try:
        login(pg)
        note("login ok")
        def popup(tag):
            pg.wait_for_timeout(3000)
            h = pg.evaluate("""() => { const vis=[...document.querySelectorAll('body *')].filter(e=>{const st=getComputedStyle(e); return (st.position==='fixed'||st.position==='absolute') && e.offsetParent!==null && e.innerText && e.innerText.trim().length>20 && e.getBoundingClientRect().height>200;});
                const m = vis.sort((a,b)=>b.innerText.length-a.innerText.length)[0];
                return m ? m.tagName+'.'+m.className+' #'+m.id+' :: ' + m.innerText.replace(/\\s+/g,' ').slice(0,900) + ' :: ' + [...m.querySelectorAll('button,input,select,a')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className.toString().split(' ').slice(0,4).join('.')+'['+(e.name||'')+'='+(e.value||'')+(e.dataset.id?' did='+e.dataset.id:'')+']«'+(e.innerText||'').trim().replace(/\\s+/g,' ').slice(0,30)+'»').join(' | ').slice(0,2500) : 'cap'; }""")
            note(tag + ": " + h)
            pg.keyboard.press("Escape"); pg.wait_for_timeout(1000)
        pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        pg.locator("button.btn-popup:has-text('Gestionar')").nth(2).click(); popup("GESTIONAR")
        pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        pg.locator("button.lineup-player").nth(3).click(); popup("LINEUP-CLICK")
        pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        pg.locator(".lineup-formation-subs, [class*=formation]").first.click(); popup("FORMATION")
        note("TEAM sel/tactic: " + pg.evaluate("() => [...document.querySelectorAll('[class*=formation], [class*=tactic], select')].map(e=>e.className+' «'+e.innerText.replace(/\\s+/g,' ').slice(0,80)+'»').slice(0,8).join(' | ')"))
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
        pg.locator("li[data-owner='0'] .btn-bid").first.click(); popup("BID")
        note("MARKET li attrs: " + pg.evaluate("() => [...document.querySelectorAll('li[data-price]')].slice(0,40).map(li=>[li.dataset.position, li.dataset.price, li.dataset.owner, li.querySelector('.name')?.innerText.trim(), li.querySelector('a.player')?.getAttribute('href')].join(',')).join(' | ')"))
        note("SIDEBAR: " + pg.evaluate("() => [...document.querySelectorAll('a[href*=id_community]')].map(a=>a.innerText.trim()+' -> '+a.getAttribute('href')).join(' | ')"))
    except Exception:
        import traceback
        note("ERR: " + traceback.format_exc()[-1500:])
    note("REQS: " + " | ".join(dict.fromkeys(reqs))[:4000])
    flush()
    b.close()
