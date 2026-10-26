"""Reconeixement de Mister (només lectura): flux d'entrada."""
import os
from playwright.sync_api import sync_playwright

U = "https://mister.mundodeportivo.com"


def dump(pg, tag):
    txt = pg.inner_text("body")[:700].replace("\n", " / ")
    els = pg.evaluate("""() => [...document.querySelectorAll('input,button,a,[role=button]')].filter(e => e.offsetParent !== null).slice(0, 50)
        .map(e => e.tagName + '[' + (e.type||'') + '] ' + (e.className||'').toString().slice(0,30) + ' ' + (e.name||e.id||'') + ' «' + (e.innerText||e.placeholder||e.getAttribute('href')||'').trim().slice(0,30) + '»').join(' | ')""")
    print(f"::notice title={tag}::{pg.url} | {txt}")
    print(f"::notice title={tag} els::{els[:2500]}")


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(locale="es-ES", timezone_id="Europe/Madrid", viewport={"width": 700, "height": 1270},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36")
    pg = ctx.new_page()
    pg.goto(U, wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(4000)
    try:
        pg.locator("#didomi-notice-agree-button").click(timeout=8000)
        pg.wait_for_timeout(2000)
    except Exception as e:
        print(f"::notice title=cookies::{e}")
    dump(pg, "1")
    for i in range(4):
        btn = pg.get_by_text("Siguiente", exact=False).first
        if not btn.count() or not btn.is_visible():
            break
        btn.click()
        pg.wait_for_timeout(1500)
    dump(pg, "2")
    for t in ["Ya tengo cuenta", "Iniciar sesión", "Entrar", "Inicia sesión", "Accede", "email", "Email", "correo"]:
        el = pg.get_by_text(t, exact=False).first
        if el.count() and el.is_visible():
            print(f"::notice title=found::{t}")
            el.click()
            pg.wait_for_timeout(2500)
            dump(pg, "3")
            break
    print(f"::notice title=secrets::MISTER_EMAIL={'sí' if os.getenv('MISTER_EMAIL') else 'no'} MISTER_PASSWORD={'sí' if os.getenv('MISTER_PASSWORD') else 'no'}")
    b.close()
