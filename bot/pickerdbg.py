"""Diagnosi del selector obert des d'un jugador (Europa League J4, tanca d'aquí a setmanes)."""
import json
from playwright.sync_api import sync_playwright
from bot import ff
from bot.web import new_context, login_futbolfantasy, inject

def note(m):
    m = m.replace("<", "‹").replace(">", "›")
    for i in range(0, len(m), 900):
        print("::notice title=p::" + m[i:i+900])

def modal_info(pg):
    return pg.evaluate("""() => { const m=document.querySelector('.modal.show'); if(!m) return 'nomodal';
      const chips=[...m.querySelectorAll('.fantasy-filtro, [class*=filtro]')].filter(e=>!e.classList.contains('fantasy-filtro-equipo')).map(e=>e.textContent.trim()+':'+e.className.replace(/\\s+/g,' ')).slice(0,12);
      const items=[...m.querySelectorAll('.sel-item')].filter(e=>e.offsetParent!==null);
      const pos={}; items.forEach(e=>{const p=e.querySelector('.sel-pos')?.textContent.trim(); pos[p]=(pos[p]||0)+1;});
      return JSON.stringify({chips, n: items.length, pos, extra: m.innerText.slice(0,200)}); }""")

with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_context(b, "futbolfantasy"); pg = ctx.new_page()
    login_futbolfantasy(pg)
    g = next(c for c in ff.cards(pg) if c["label"].startswith("Europa League") and c["empty"] == 11)
    ff.fill(pg, g["id"], [{"ff": "Dion Beljo"}])
    ff.cards(pg); inject(pg, "ff")
    ff.click(pg, f'#juego-{g["id"]} a.fantasy-slot')
    pg.locator(".modal.show").wait_for(timeout=10000); pg.wait_for_timeout(1500)
    note("des del jugador: " + modal_info(pg))
    r = pg.evaluate("(q) => __ff.search(q)", "Mbappé")
    note("cerca Mbappé (des del jugador): " + json.dumps(r, ensure_ascii=False)[:400])
    r = pg.evaluate("(q) => __ff.search(q)", "Beljo")
    note("cerca Beljo (ja triat): " + json.dumps(r, ensure_ascii=False)[:300])
    # provar de treure el filtre de posició actiu
    act = pg.evaluate("""() => { const m=document.querySelector('.modal.show'); const a=[...m.querySelectorAll('.fantasy-filtro:not(.fantasy-filtro-equipo)')].filter(e=>/active|selected|on/.test(e.className)); a.forEach(e=>e.click()); return a.map(e=>e.textContent.trim()); }""")
    pg.wait_for_timeout(1500)
    r = pg.evaluate("(q) => __ff.search(q)", "Mbappé")
    note(f"després de treure filtres {act}: cerca Mbappé: " + json.dumps(r, ensure_ascii=False)[:400] + " || " + modal_info(pg))
    ff.close_modal(pg)
    log = []
    ff.remove_players(pg, g["id"], {str(x) for x in next(c for c in ff.cards(pg) if c["id"] == g["id"])["ids"]}, log)
    note("final: " + str(next(c for c in ff.cards(pg) if c["id"] == g["id"])["empty"]) + " buits " + str(log))
    b.close()
