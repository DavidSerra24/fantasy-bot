"""Diagnosi: estructura d'un jugador en una pàgina de partit de futbolfantasy.com.
Ús: python -m bot.ffpage 22551-racing-real-sociedad Sergio Gómez"""
import json
import sys

from playwright.sync_api import sync_playwright

from bot.web import login_futbolfantasy, new_context

slug, q = sys.argv[1], " ".join(sys.argv[2:])
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "futbolfantasy").new_page(); login_futbolfantasy(pg)
    pg.goto(f"https://www.futbolfantasy.com/partidos/{slug}", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    r = pg.evaluate("""(q) => [...document.querySelectorAll('img[alt]')].filter(i => i.alt === q).map(img => {
        const chain = []; let e = img;
        while (e && chain.length < 12) { chain.push(e.tagName + '.' + (e.className || '').toString().slice(0, 80)
            + (e.getAttribute && e.getAttribute('data-onceff') ? ' onceff=' + e.getAttribute('data-onceff') : '')); e = e.parentElement; }
        const box = img.closest('[class*="jugador_"]');
        const a = box && box.querySelector('a[data-probabilidad]');
        const near = img.closest('div')?.parentElement?.querySelector('[data-probabilidad]');
        return {chain, box: box ? box.className.slice(0, 120) : null, a: a ? [...a.attributes].map(x => x.name + '=' + x.value).join(' ').slice(0, 400) : null,
                near: near ? near.outerHTML.slice(0, 300) : null, text: (img.closest('[class*="jugador"]') || img.parentElement.parentElement).innerText.replace(/\\s+/g, ' ').slice(0, 200)};
    })""", q)
    b.close()
for k, x in enumerate(r):
    print(f"::notice title=ffpage {k}::" + json.dumps(x, ensure_ascii=False)[:3800])
