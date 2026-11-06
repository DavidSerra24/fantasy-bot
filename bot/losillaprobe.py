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
    h = pg.evaluate("""() => { const h=document.body.innerHTML; let out=[]; let i=0;
        for (const k of ['PROBABLES','Probables','probables','TÉCNICOS','Técnicos','tecnicos']) { let j=h.indexOf(k); while(j>=0 && out.length<12){ out.push(k+'@'+j+': '+h.slice(Math.max(0,j-400), j+150).replace(/\\s+/g,' ')); j=h.indexOf(k,j+1);} }
        return out.join(' ##### '); }""")
    print("::notice title=html::" + h[:3900])
    h2 = pg.evaluate("() => document.querySelector('.c-porcentajes-analisis') ? document.querySelector('.c-porcentajes-analisis').outerHTML.slice(0,3500) : 'cap'")
    print("::notice title=taula::" + h2.replace("\n", " ")[:3900])
    tbl = pg.evaluate("() => { const t=[...document.querySelectorAll('table')].map(x=>x.outerHTML.length+' '+x.className); return t.join(' / ') }")
    print("::notice title=taules::" + tbl[:1000])
    b.close()
for u, body in calls:
    print(f"::notice title=xhr {u[:160]}::" + body.replace("\n", " ")[:1800])
