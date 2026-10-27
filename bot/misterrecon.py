"""Reconeixement (només lectura): joc de la Copa del Rey a FutbolFantasy i competicions de SorareInside."""
from playwright.sync_api import sync_playwright
from bot.web import new_context, login_futbolfantasy, inject
from bot import ff

LOG = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "futbolfantasy").new_page()
    try:
        login_futbolfantasy(pg)
        cs = ff.cards(pg)
        LOG.append("CARDS: " + " | ".join(f"{c['id']}:{c['label']}:{c['title']}:{c['end']}:buides={c['empty']}" for c in cs))
        for c in cs:
            if c["id"] == "1051":
                LOG.append("COPA TEXT: " + pg.evaluate("(id) => document.getElementById('juego-'+id).innerText.replace(/\\s+/g,' ').slice(0,1500)", c["id"]))
                LOG.append("COPA LINKS: " + pg.evaluate("(id) => [...document.getElementById('juego-'+id).querySelectorAll('a,button')].map(e=>(e.innerText||'').trim().slice(0,30)+' '+(e.getAttribute('href')||'')+' '+Object.keys(e.dataset).map(k=>k+'='+e.dataset[k]).join(',').slice(0,100)).slice(0,25).join(' | ')", c["id"]))
                # regles: botó d'informació del joc
                try:
                    pg.locator(f"#juego-{c['id']}").get_by_text("Reglas", exact=False).first.click(timeout=5000); pg.wait_for_timeout(2000)
                    LOG.append("COPA RULES: " + (pg.evaluate("() => { const m=document.querySelector('.modal.show'); return m ? m.innerText.replace(/\\s+/g,' ').slice(0,2500) : 'cap'; }")))
                    pg.keyboard.press("Escape")
                except Exception as e:
                    LOG.append(f"rules err {e}"[:200])
                ff.open_picker(pg, c["id"])
                inject(pg, "ff")
                LOG.append("PICKER sample: " + str(pg.evaluate("(q) => __ff.search(q)", "a"))[:2500])
                ff.close_modal(pg)
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
