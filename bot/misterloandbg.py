"""Diagnosi (només lectura): text i HTML de les files «cedit» de la plantilla del Mister."""
from playwright.sync_api import sync_playwright

from bot.mister import U, login, new_context
from bot.misterplan import LEAGUES

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    login(pg)
    for name, cid, _, _ in LEAGUES:
        pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
        pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
        rows = pg.evaluate("""() => [...document.querySelectorAll('.player-row')].map(r => { const box = r.closest('li') || r.parentElement;
            return /cedit|cesi|loan/i.test(box.innerText + box.outerHTML) ? (box.innerText.replace(/\\s+/g, ' ').slice(0, 200) + ' || ' + box.outerHTML.replace(/\\s+/g, ' ').match(/.{0,150}(cedit|cesi|loan).{0,150}/i)?.[0]) : null }).filter(Boolean)""")
        print(f"::notice title={name}::" + " ¶ ".join(rows)[:7000])
    b.close()
