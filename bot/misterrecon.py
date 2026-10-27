"""Reconeixement (només lectura): equip real dels jugadors amb puja meva a Quique."""
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
        mine = pg.evaluate("() => [...document.querySelectorAll('li[data-owner=\"0\"]')].filter(l=>l.querySelector('.btn-bid.btn--accent')).map(l=>[l.querySelector('.name').innerText.trim(), l.querySelector('a.player').getAttribute('href'), (l.querySelector('img.team-logo')||{}).src])")
        LOG.append(f"MINE: {mine}")
        for name, href, logo in mine:
            pg.goto(U + "/" + href, wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            LOG.append(f"{name} {href}: " + pg.inner_text("body")[150:420].replace("\n", " / "))
            LOG.append("  team els: " + pg.evaluate("() => [...document.querySelectorAll('[class*=team], a[href*=teams]')].slice(0,8).map(e=>e.tagName+'.'+e.className+' «'+(e.innerText||e.alt||'').trim().slice(0,40)+'» '+(e.getAttribute('href')||'')).join(' | ')"))
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1200:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
