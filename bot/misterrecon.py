"""Reconeixement (només lectura): regles dels jocs Fantasy✨ de FutbolFantasy."""
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
        seen = set()
        for c in cs:
            k = c["label"].split("·")[0].strip()
            if k in seen or not k:
                continue
            seen.add(k)
            info = pg.evaluate("(id) => { const a=document.querySelector('#juego-'+id+' [data-info]'); return a ? a.dataset.info.replace(/<[^>]+>/g,' ').replace(/\\s+/g,' ') : 'cap'; }", c["id"])
            LOG.append(f"{c['label']}: {info[:2500]}")
        pg.goto("https://www.futbolfantasy.com/fantasy", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        LOG.append("FANTASY PAGE: " + pg.inner_text("body")[:3000].replace("\n", " / "))
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 6000), 6000):
        print("::notice title=log" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    b.close()
