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
    ROWS = """() => [...document.querySelectorAll('.c-porcentajes-analisis tr.c-porcentajes-analisis__partido')].map(tr =>
        [...tr.querySelectorAll('td')].map(td => td.textContent.trim() || '-').join(' ')).join(' | ')"""
    for v, tab in ((0, "QUINIELISTA"), (1, "PROBABLES"), (2, "LAE"), (3, "TÉCNICOS")):
        n0 = len(calls)
        pg.select_option("select[aria-label=SelectorQUINIELISTA], select.c-selector__select >> nth=0", str(v))
        pg.wait_for_timeout(3000)
        print(f"::notice title=filtre {tab}::" + pg.evaluate(ROWS) + " ¶ xhr: " + " ; ".join(u[:150] for u, _ in calls[n0:]))
    tbl = pg.evaluate("() => { const t=[...document.querySelectorAll('table')].map(x=>x.outerHTML.length+' '+x.className); return t.join(' / ') }")
    print("::notice title=taules::" + tbl[:1000])
    b.close()
for u, body in calls:
    print(f"::notice title=xhr {u[:160]}::" + body.replace("\n", " ")[:1800])
