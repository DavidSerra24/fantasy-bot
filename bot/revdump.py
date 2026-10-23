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
    pg.goto("https://www.futbolfantasy.com/partidos/22519-racing-espanyol", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    for _ in range(8):
        pg.mouse.wheel(0, 3000); pg.wait_for_timeout(700)
    t = pg.inner_text("body")
    note(f"longitud text {len(t)}; conté Puado: {'Puado' in t}; inici: {t[:300]!r}")
    links = pg.evaluate("() => [...new Set([...document.querySelectorAll('a')].map(a=>a.href).filter(h=>/espanyol|partido|alinea/i.test(h)))].slice(0,20)")
    note("enllaços: " + " ; ".join(links))
    info = pg.evaluate("""() => { const el=[...document.querySelectorAll('*')].find(e=>e.childElementCount===0 && /Puado/.test(e.textContent));
      if(!el) return 'Puado no trobat';
      let c=el; for(let i=0;i<3;i++) c=c.parentElement;
      const tips=[...document.querySelectorAll('[title],[data-original-title],[data-bs-original-title],[data-tooltip],[alt]')].map(e=>(e.getAttribute('title')||e.getAttribute('data-original-title')||e.getAttribute('data-bs-original-title')||e.getAttribute('data-tooltip')||e.getAttribute('alt'))).filter(Boolean);
      return c.outerHTML.slice(0,2500) + ' || TIPS: ' + [...new Set(tips)].filter(t=>t.length<80).slice(0,60).join(' / '); }""")
    note("context: " + info)
    b.close()
