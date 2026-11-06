"""Diagnosi (6/11): Análisis de eduardolosilla.es amb cada filtre (Quinielista, Probables, LAE, Técnicos)."""
from playwright.sync_api import sync_playwright

calls = []
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(locale="es-ES")

    def on_resp(r):
        if "eduardolosilla" in r.url and r.request.resource_type in ("xhr", "fetch"):
            try:
                body = r.text()
            except Exception:
                body = ""
            calls.append((r.url, body[:1800]))
    pg.on("response", on_resp)
    pg.goto("https://www.eduardolosilla.es/quiniela/ayudas/analisis", wait_until="networkidle", timeout=60000)
    pg.wait_for_timeout(2000)
    n0 = len(calls)
    for tab in ("QUINIELISTA", "PROBABLES", "LAE", "TÉCNICOS"):
        try:
            el = pg.get_by_text(tab, exact=True).last
            print(f"::notice title=tab {tab}::html " + el.evaluate("e => e.outerHTML.slice(0,300)"))
            el.click()
            pg.wait_for_timeout(2500)
            txt = pg.inner_text("body")
            i = txt.find("BASE")
            print(f"::notice title=filtre {tab}::" + txt[i:i + 1500].replace("\n", " | ").replace("\t", " ; "))
        except Exception as e:
            print(f"::notice title=err {tab}::{str(e)[:300]}")
    tbl = pg.evaluate("() => { const t=[...document.querySelectorAll('table')].map(x=>x.outerHTML.length+' '+x.className); return t.join(' / ') }")
    print("::notice title=taules::" + tbl[:1000])
    b.close()
for u, body in calls:
    print(f"::notice title=xhr {u[:160]}::" + body.replace("\n", " ")[:1800])
