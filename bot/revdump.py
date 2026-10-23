"""Busca com marca FutbolFantasy els possibles revulsius a les alineacions probables (no canvia res)."""
from playwright.sync_api import sync_playwright
from bot.web import new_context

def note(m):
    for i in range(0, len(m), 900):
        print("::notice title=rv::" + m[i:i+900])

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = new_context(b, "anon")
    pg = ctx.new_page()
    pg.goto("https://www.futbolfantasy.com/laliga", wait_until="domcontentloaded")
    pg.wait_for_timeout(3000)
    links = pg.evaluate("() => [...new Set([...document.querySelectorAll('a')].map(a=>a.href).filter(h=>/alinea/i.test(h)))].slice(0,15)")
    note("enllaços: " + " ; ".join(links))
    target = next((l for l in links if "posibles" in l or "probables" in l), links[0] if links else None)
    if target:
        pg.goto(target, wait_until="domcontentloaded")
        pg.wait_for_timeout(4000)
        note("pàgina: " + pg.url)
        info = pg.evaluate("""() => { const el=[...document.querySelectorAll('*')].find(e=>e.childElementCount===0 && /Puado/.test(e.textContent));
          if(!el) return 'Puado no trobat. Text: ' + document.body.innerText.slice(0,500);
          let c=el; for(let i=0;i<4;i++) c=c.parentElement;
          const legend=[...document.querySelectorAll('[title],[data-original-title],[alt]')].map(e=>(e.getAttribute('title')||e.getAttribute('data-original-title')||e.getAttribute('alt'))).filter(t=>t&&/revuls|banquillo|suplent|sale|entra/i.test(t));
          return 'context: ' + c.outerHTML.slice(0,2500) + ' || llegenda: ' + [...new Set(legend)].slice(0,20).join(' / '); }""")
        note(info)
    b.close()
