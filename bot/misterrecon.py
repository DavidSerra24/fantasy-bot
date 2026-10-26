"""Reconeixement de Mister (només lectura): què hi ha a la portada i al formulari d'entrada."""
import os
from playwright.sync_api import sync_playwright

U = "https://mister.mundodeportivo.com"
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(locale="es-ES", timezone_id="Europe/Madrid", viewport={"width": 700, "height": 1270},
                        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36")
    pg = ctx.new_page()
    reqs = []
    pg.on("request", lambda r: reqs.append(r.method + " " + r.url) if "mundodeportivo" in r.url and r.resource_type in ("xhr", "fetch", "document") else None)
    for path in ["/", "/login", "/signin"]:
        try:
            r = pg.goto(U + path, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(4000)
            print(f"::notice title=p {path}::{r.status if r else None} {pg.url} | {pg.title()} | {pg.inner_text('body')[:600].replace(chr(10), ' / ')}")
            forms = pg.evaluate("""() => [...document.querySelectorAll('input,button,a')].filter(e => e.offsetParent !== null).slice(0, 60)
                .map(e => e.tagName + '[' + (e.type||'') + '] ' + (e.name||e.id||'') + ' ' + (e.innerText||e.placeholder||e.getAttribute('href')||'').trim().slice(0,40)).join(' | ')""")
            print(f"::notice title=e {path}::{forms[:1800]}")
        except Exception as e:
            print(f"::notice title=err {path}::{type(e).__name__} {str(e)[:200]}")
    print("::notice title=req::" + " | ".join(dict.fromkeys(reqs))[:1800])
    print(f"::notice title=secrets::MISTER_EMAIL={'sí' if os.getenv('MISTER_EMAIL') else 'no'}")
    b.close()
