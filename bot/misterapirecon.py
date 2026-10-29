"""Reconeixement (només lectura) de l'API interna del Mister: quines crides fa la web en llegir la plantilla, el mercat,
el saldo i en obrir (sense confirmar) les finestres de puja, venda, ofertes i alineació.
Ús: python -m bot.misterapirecon   (no envia cap puja, venda ni canvi)"""
import json

from playwright.sync_api import sync_playwright

from bot.mister import U, login, new_context

LOG, seen = [], set()


def on_resp(r):
    u = r.url
    if not any(k in u for k in ("/api", "/ajax", "/action")) or any(k in u for k in ("google", "facebook", "analytics", "doubleclick")):
        return
    key = r.request.method + " " + u.split("?")[0]
    try:
        body = r.text()[:700]
    except Exception:
        body = "?"
    if key in seen and r.request.method == "GET":
        return
    seen.add(key)
    LOG.append(f"{r.request.method} {u.split('mundodeportivo.com')[-1][:200]} ⟵ {(r.request.post_data or '')[:300]} ⟶ {r.status} {body}")


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = new_context(b)
    pg = ctx.new_page()
    pg.on("response", on_resp)
    try:
        login(pg)
        LOG.append("== cookies: " + ", ".join(f"{c['name']}@{c['domain']}" for c in ctx.cookies()))
        LOG.append("== headers de la web: " + json.dumps(pg.evaluate("() => ({ua: navigator.userAgent, csrf: document.querySelector('meta[name=csrf-token]')?.content || null, x: Object.keys(window).filter(k => /token|api|csrf|user/i.test(k)).slice(0, 20)})"))[:600])
        pg.goto(f"{U}/action/change?id_community=2499621", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        for path in ("/feed", "/team", "/market", "/standings"):
            LOG.append(f"== {path}")
            pg.goto(U + path, wait_until="networkidle"); pg.wait_for_timeout(2500)
        # finestres (només obrir i tancar)
        pg.goto(U + "/market", wait_until="networkidle"); pg.wait_for_timeout(2000)
        LOG.append("== obro la finestra de puja (sense pujar)")
        btn = pg.locator(".btn-bid").first
        if btn.count():
            btn.evaluate("e => e.click()"); pg.wait_for_timeout(3000)
            LOG.append("FORM puja: " + pg.evaluate("() => { const f = document.querySelector('#form-bid'); return f ? f.outerHTML.slice(0, 1500) : 'cap'; }"))
            pg.keyboard.press("Escape"); pg.wait_for_timeout(800)
        LOG.append("== obro ofertes rebudes")
        o = pg.locator(".offers-received[data-sw]").first
        if o.count():
            o.evaluate("e => e.click()"); pg.wait_for_timeout(3000); pg.keyboard.press("Escape")
        pg.goto(U + "/team", wait_until="networkidle"); pg.wait_for_timeout(2000)
        LOG.append("== obro la finestra de venda d'un jugador (sense vendre)")
        pl = pg.locator(".player-row a.player").first
        if pl.count():
            href = pl.get_attribute("href") or ""
            pid = href.split("/")[1] if "/" in href else ""
            pg.evaluate("""(pid) => fetch('/ajax/player-community-info', {method: 'POST', headers: {'Content-Type': 'application/x-www-form-urlencoded', 'X-Requested-With': 'XMLHttpRequest'}, body: 'id_player=' + pid + '&popup=sale'}).then(r => r.text())""", pid)
            pg.wait_for_timeout(2000)
        LOG.append("== alineació: obro el selector d'una casella (sense canviar)")
        s = pg.locator(".lineup-starting button.lineup-player").first
        if s.count():
            s.evaluate("e => e.click()"); pg.wait_for_timeout(3000); pg.keyboard.press("Escape")
        LOG.append("== pàgina d'un jugador")
        if pl.count():
            pg.goto(U + "/" + (pl.get_attribute("href") or "").lstrip("/"), wait_until="networkidle"); pg.wait_for_timeout(2000)
    except Exception:
        import traceback
        LOG.append("ERR: " + traceback.format_exc()[-1500:])
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 9 * 7000), 7000):
        print("::notice title=api" + str(i // 7000) + "::" + txt[i:i + 7000].replace("\n", " ¶ "))
    b.close()
