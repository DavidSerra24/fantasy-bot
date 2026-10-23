import json
from playwright.sync_api import sync_playwright
from bot.web import new_context
def note(m):
    m = m.replace("<", "‹").replace(">", "›")
    for i in range(0, len(m), 900):
        print("::notice title=rv::" + m[i:i+900])
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_context(b, "anon"); pg = ctx.new_page()
    pg.goto("https://www.futbolfantasy.com/partidos/22519-racing-espanyol", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(6000)
    r = pg.evaluate("""() => {
      const leg = document.querySelector('.revulsivo-modal'); 
      const legend = leg ? [...leg.querySelectorAll('li, .row, p, div')].filter(e=>e.childElementCount<6).map(e=>e.innerText.replace(/\\s+/g,' ').trim() + ' [' + [...e.querySelectorAll('.ff-revulsivo')].map(x=>x.className).join(',') + ']').filter(t=>t.length>3).slice(0,20) : [];
      const pls = [...document.querySelectorAll('[class*="jugador_"]')].filter(e=>e.querySelector('.ff-revulsivo')).map(e => {
        const a = e.querySelector('a[data-probabilidad]') || e.querySelector('a');
        const rv = e.querySelector('.ff-revulsivo');
        const d = a ? Object.fromEntries([...a.attributes].filter(x=>x.name.startsWith('data-') && !/toggle|target/.test(x.name)).map(x=>[x.name.slice(5), x.value.slice(0,40)])) : {};
        return JSON.stringify({rv: rv.className.replace('ff-revulsivo','').replace('mx-auto','').trim(), pct: rv.innerText.trim(), href: a?.getAttribute('href'), d, img: e.querySelector('img[alt]')?.alt, txt: e.innerText.replace(/\s+/g,' ').trim().slice(0,80)});
      });
      return JSON.stringify({legend: [...new Set(legend)], players: pls.slice(0,3), nameattrs: [...document.querySelectorAll('[class*="jugador_"] [data-nombre]')].slice(0,3).map(x=>x.getAttribute('data-nombre'))});
    }""")
    note(r)
    b.close()
