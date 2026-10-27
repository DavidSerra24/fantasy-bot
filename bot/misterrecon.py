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
        pg.goto(f"{U}/action/change?id_community=2519290", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
        r = pg.evaluate("""() => fetch('/ajax/player-community-info', {method:'POST', headers:{'Content-Type':'application/x-www-form-urlencoded; charset=UTF-8','X-Requested-With':'XMLHttpRequest'},
             body:'id_owner=15505527&id_player=58125&popup=sale&style=secondary&preload=player-community-info'}).then(r=>r.text())""")
        note("SALE AJAX: " + compact(r)[:12000])
        note("MARKET nav: " + pg.evaluate("() => [...document.querySelectorAll('a[href], .tab, [data-tab]')].filter(e=>e.offsetParent!==null).map(e=>e.tagName+'.'+e.className+' «'+e.innerText.trim().replace(/\\s+/g,' ').slice(0,25)+'» '+(e.getAttribute('href')||'')+' '+(e.dataset.tab||'')).slice(0,60).join(' | ')"))
        note("MARKET body: " + pg.inner_text("body")[:1500].replace("\n", " / "))
        for path in ("/market/offers", "/market?tab=offers", "/activity", "/notifications"):
            pg.goto(U + path, wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            note(f"PATH {path} -> {pg.url}: " + pg.inner_text("body")[300:900].replace("\n", " / "))
    except Exception:
        import traceback
        note("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
