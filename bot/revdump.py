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
      const attrs = e => Object.fromEntries([...e.attributes].filter(a=>!/^(style|onerror|onload|src|data-src)$/.test(a.name)).map(a=>[a.name, a.value.slice(0,80)]));
      const pl = [...document.querySelectorAll('[class*="jugador_"]')].filter(e => /Puado/.test(e.innerText + ' ' + e.getAttribute('data-nombre') + ' ' + e.outerHTML.slice(0,3000)));
      const rev = [...document.querySelectorAll('*')].filter(e => [...e.attributes].some(a => /revuls/i.test(a.value)) || (e.childElementCount===0 && /revuls/i.test(e.textContent)));
      return JSON.stringify({
        puado: pl.slice(0,2).map(e => ({attrs: attrs(e), text: e.innerText.slice(0,120), kids: [...e.querySelectorAll('*')].map(k => k.tagName + ':' + JSON.stringify(attrs(k))).filter(s=>s.length<300).slice(0,25)})),
        rev: rev.slice(0,10).map(e => e.tagName + ':' + JSON.stringify(attrs(e)) + ':' + e.textContent.trim().slice(0,60))
      }); }""")
    note(r)
    b.close()
