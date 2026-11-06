"""Diagnosi (6/11): què hi ha a eduardolosilla.es → Ayudas jornada → Análisis (Quinielista, Probables, LAE, Técnicos)."""
import json

from playwright.sync_api import sync_playwright

calls = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(locale="es-ES")

    def on_resp(r):
        if "api.eduardolosilla" in r.url or r.request.resource_type in ("xhr", "fetch"):
            try:
                body = r.text()
            except Exception:
                body = ""
            calls.append((r.request.method, r.url, r.request.post_data, body[:2500]))
    pg.on("response", on_resp)
    pg.goto("https://www.eduardolosilla.es/", wait_until="networkidle", timeout=60000)
    links = pg.evaluate("() => [...document.querySelectorAll('a')].map(a => a.textContent.trim().slice(0,40) + ' -> ' + a.href).filter(x => /ayuda|analisis|análisis|jornada|quiniela/i.test(x)).slice(0,60)")
    print("::notice title=enllaços::" + " | ".join(links)[:3900])
    for url in ("https://www.eduardolosilla.es/quiniela/ayudas/analisis", "https://www.eduardolosilla.es/ayudas-jornada/analisis"):
        try:
            pg.goto(url, wait_until="networkidle", timeout=60000)
            pg.wait_for_timeout(3000)
            print(f"::notice title=pàgina {url}::" + pg.inner_text("body")[:3500].replace("\n", " | "))
        except Exception as e:
            print(f"::notice title=err {url}::{e}")
    b.close()
for m, u, pd, body in calls:
    if "google" in u or "analytics" in u or "doubleclick" in u:
        continue
    print(f"::notice title=xhr {m} {u[:150]}::" + (f"POST {pd[:300]} ¶ " if pd else "") + body.replace("\n", " ")[:2500])
