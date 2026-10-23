"""Mira com marca FutbolFantasy els possibles revulsius al selector (no canvia res)."""
from playwright.sync_api import sync_playwright
from bot import ff
from bot.web import new_context, login_futbolfantasy

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = new_context(b, "futbolfantasy")
    pg = ctx.new_page()
    login_futbolfantasy(pg)
    cs = ff.cards(pg)
    g = next(c for c in cs if "revulsivo" in c["title"].lower())
    pg.locator(f'#juego-{g["id"]} a.fantasy-add').first.click()
    pg.locator(".modal.show").wait_for(timeout=10000)
    pg.wait_for_timeout(2500)
    info = pg.evaluate("""() => { const m=document.querySelector('.modal.show');
      const items=[...m.querySelectorAll('.sel-item')];
      const withImg=items.filter(e=>e.querySelectorAll('img, svg, i, [class*=icon], [class*=badge]').length>2);
      const cls=new Set(); items.forEach(e=>e.querySelectorAll('*').forEach(x=>String(x.className).split(' ').forEach(c=>c&&cls.add(c))));
      return JSON.stringify({n:items.length, filters:m.innerText.slice(0,400), classes:[...cls].slice(0,80),
        sample:items.slice(0,2).map(e=>e.outerHTML.slice(0,900))}); }""")
    for i in range(0, len(info), 900):
        print("::notice title=rv::" + info[i:i+900])
    ff.close_modal(pg)
    b.close()
