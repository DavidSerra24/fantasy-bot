"""Prova (només lectura): text i HTML de la pàgina d'un equip de Predicted11 (onze probable de FutbolFantasy)."""
import sys

from playwright.sync_api import sync_playwright

from bot.web import login_predicted11, new_context

comp, slug = (sys.argv[1:3] + ["champions", "bodo-glimt"])[0:2] if len(sys.argv) > 2 else ("champions", "bodo-glimt")
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = new_context(b, "predicted11")
    pg = ctx.new_page()
    login_predicted11(pg)
    pg.goto(f"https://www.predicted11.com/es/{comp}/equipo/{slug}", wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)
    t = pg.inner_text("body")
    i = t.lower().find("futbolfantasy")
    print("::notice title=text::" + t[max(0, i - 1500):i + 2500].replace("\n", " ¶ ")[:3900])
    h = pg.evaluate("""() => { const el = [...document.querySelectorAll('*')].filter(e => /futbolfantasy/i.test(e.textContent) && e.children.length < 40).pop();
        let x = el; for (let k = 0; k < 4 && x && x.parentElement; k++) x = x.parentElement; return x ? x.outerHTML : 'cap'; }""")
    for k in range(0, min(len(h), 15000), 3800):
        print(f"::notice title=html{k}::" + h[k:k + 3800])
    reqs = []
    pg.on("response", lambda r: reqs.append(r) if r.request.resource_type in ("xhr", "fetch") else None)
    pg.locator('a.ranking-link-block[data-username="FutbolFantasy"]').first.click()
    pg.wait_for_timeout(4000)
    for r in reqs[:6]:
        try:
            body = r.text()
        except Exception:
            body = "?"
        print(f"::notice title=xhr {r.request.method} {r.url[:200]}::" + (r.request.post_data or "")[:300] + " → " + body[:3000].replace("\n", " "))
    m = pg.evaluate("() => { const d = [...document.querySelectorAll('.modal.show, .modal[style*=block], [role=dialog]')].pop(); return d ? d.innerText + ' ||| ' + d.outerHTML.slice(0, 6000) : 'sense modal'; }")
    for k in range(0, min(len(m), 11000), 3800):
        print(f"::notice title=modal{k}::" + m[k:k + 3800].replace("\n", " ¶ "))
    b.close()
