from playwright.sync_api import sync_playwright
from bot.web import new_context, login_predicted11
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = new_context(b, "predicted11"); pg = ctx.new_page()
    login_predicted11(pg)
    pg.goto("https://www.predicted11.com/es/premier-league/equipo/tottenham", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    r = pg.evaluate("""() => ({defs: [...document.querySelectorAll('#playerList .player-item')].filter(e=>e.dataset.posicion==='Defensa').map(e=>e.dataset.nombre),
        rob: [...document.querySelectorAll('#playerList .player-item')].filter(e=>/robert/i.test(e.dataset.nombre)).map(e=>e.dataset.nombre),
        field: [...document.querySelectorAll('#campoAlineacion .player-on-field')].filter(e=>e.offsetParent!==null).map(e=>e.querySelector('.player-on-field-name')?.textContent)})""")
    print("::notice title=t::" + str(r))
    b.close()
