"""Diagnosi: què veu el bot a la pàgina d'un equip de Predicted11 (sense canviar res)."""
from playwright.sync_api import sync_playwright
from bot.web import new_context, login_predicted11, save_session

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = new_context(b, "predicted11")
    pg = ctx.new_page()
    print("::notice title=dbg::login " + login_predicted11(pg))
    save_session(ctx, "predicted11")
    pg.goto("https://www.predicted11.com/es/serie-a/equipo/inter", wait_until="domcontentloaded")
    pg.wait_for_timeout(3500)
    info = pg.evaluate("""() => {
      const on=[...document.querySelectorAll('#campoAlineacion .player-on-field')].filter(e=>e.offsetParent!==null);
      const t=document.querySelector('main').innerText;
      return JSON.stringify({w:innerWidth, banner:/Inicia sesión o regístrate/.test(t), pron:(t.match(/PRON[ÓO]STICO DE[^\\n]*/i)||[])[0], tactic:document.getElementById('tacticaSelector')?.value,
        n:on.length, slots:document.querySelectorAll('.choose-slot-btn[data-slot]').length,
        ids:[...document.querySelectorAll('[id]')].map(e=>e.id).filter(i=>/reset|clear|field|campo|confirm|save|guardar|limpi/i.test(i)),
        btns:[...document.querySelectorAll('button, a.btn, [role=button]')].filter(b=>b.offsetParent!==null).map(b=>(b.id||'')+'|'+(b.title||b.getAttribute('aria-label')||b.textContent.trim()).slice(0,30)+'|'+String(b.className).slice(0,40)).slice(0,40)});
    }""")
    for i in range(0, len(info), 900):
        print("::notice title=dbg::" + info[i:i+900])
    pg.screenshot(path="out_p11.png", full_page=True)
    b.close()
