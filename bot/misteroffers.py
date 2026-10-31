"""Mister: ofertes per als jugadors posats en venda (arriben a les 17:00 i a les 5:00).

Per a cada jugador meu en venda torna a mirar el % de titularitat:
- si ara arriba al mínim de la lliga, el treu de la venda;
- si continua per sota, accepta l'oferta del Mister (si n'hi ha).
Mentre no tinguem vist com és la pantalla de l'oferta, el bot desa el que veu (anotacions del job) i, si no
troba un botó «Acceptar» clarament lligat al jugador, no fa res i avisa per Telegram.
Ús: python -m bot.misteroffers [--dry]
"""
import argparse
import re

from playwright.sync_api import sync_playwright

from bot.mister import U, login, new_context as mister_context
from bot.misterplan import LEAGUES
from bot.mistermarket import league_data
from bot.notify import telegram
from bot.web import load_json, login_sorareinside, new_context, save_session

ACCEPT = re.compile(r"^\s*(acceptar|aceptar)(\s+oferta)?\s*$", re.I)
REMOVE = re.compile(r"^\s*(eliminar|retirar)\s*$", re.I)  # finestra de venda: «Eliminar» (#btn-send)
LOG = []

BUTTONS = """(root) => [...(root || document).querySelectorAll('button, a.btn')].filter(e => e.offsetParent !== null).map(e => ({
    t: (e.innerText || '').trim().replace(/\\s+/g, ' ').slice(0, 40), cls: e.className.toString(), id: e.id,
    data: Object.keys(e.dataset).map(k => k + '=' + e.dataset[k]).join(',') }))"""


def snap(pg, tag):
    """Desa el text i els botons visibles de la finestra oberta (per afinar el bot)."""
    txt = pg.evaluate("""() => { const f = [...document.querySelectorAll('form, .popup, .modal, [class*=popup]')].filter(e => e.offsetParent !== null).pop();
        return f ? (f.closest('[class*=popup]') || f).innerText.replace(/\\s+/g, ' ').slice(0, 900) : ''; }""")
    LOG.append(f"{tag} TEXT: {txt}")
    LOG.append(f"{tag} BUTTONS: " + " | ".join(f"{b['t']}#{b['id']}.{b['cls'][:40]} {b['data'][:80]}" for b in pg.evaluate(BUTTONS, None)[-15:]))
    return txt


def open_sale(pg, pid):
    pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    pg.locator(f'button.btn-popup[data-popup="sale"][data-id_player="{pid}"]').first.click()
    pg.wait_for_timeout(3000)


def click_text(pg, rx, near=None):
    """Clica l'únic botó visible el text del qual compleix rx (i, si cal, dins d'un bloc que conté `near`)."""
    loc = pg.locator("button:visible, a.btn:visible")
    hits = []
    for i in range(loc.count()):
        el = loc.nth(i)
        if not rx.search(el.inner_text() or ""):
            continue
        if near and near.lower() not in (el.evaluate("e => { let c = e; for (let i = 0; i < 6 && c; i++) c = c.parentElement; return c ? c.innerText : ''; }") or "").lower():
            continue
        hits.append(el)
    if len(hits) != 1:
        return len(hits)
    hits[0].click(); pg.wait_for_timeout(2500)
    return 1


OFFERS_JS = """() => { const c = document.querySelector('.sw-content'); if (!c) return [];
    return [...c.querySelectorAll('button[data-popup="market/offers-received/direct-transfer-confirmation"]')].map(b => {
        let box = b; while (box && !box.querySelector('.player-avatar[data-id_player]')) box = box.parentElement;
        return { pid: box ? box.querySelector('.player-avatar[data-id_player]').dataset.id_player : null, bid: +b.dataset.bid,
                 id_bid: b.dataset.id_bid, user: b.dataset.username }; }); }"""


def offers(pg):
    """Ofertes rebudes (Mercat → «N ofertas recibidas»): {id_jugador: {bid, id_bid, user}} (la millor de cada jugador)."""
    pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    btn = pg.locator(".offers-received[data-sw]").first
    if not btn.count():
        return {}
    btn.click()
    pg.locator(".sw-content").first.wait_for(state="visible", timeout=10000)
    pg.wait_for_timeout(2500)
    out = {}
    for o in pg.evaluate(OFFERS_JS):
        if o["pid"] and (o["pid"] not in out or o["bid"] > out[o["pid"]]["bid"]):
            out[o["pid"]] = o
    return out


def accept(pg, pid):
    """Accepta la millor oferta pel jugador (botó de l'oferta → finestra «El traspaso se efectuará…» → «Vendre»)."""
    o = offers(pg).get(pid)
    if not o:
        return False
    from bot import misterapi
    if misterapi.use("accept_offer", o["id_bid"], o["bid"]):
        pass  # acceptada per l'API: es comprova igual que amb la finestra
    else:
        _accept_window(pg, o)
    # El Mister triga una mica a actualitzar-ho: es comprova fins a 4 vegades (≈40 s) abans de dir que ha fallat
    for i in range(4):
        pg.wait_for_timeout(5000 + 5000 * i)
        pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        if not pg.locator(f'a.player[href^="players/{pid}/"]').count():  # ja no és a la plantilla = venut
            return True
        if pid not in offers(pg):
            return True
    return False


def _accept_window(pg, o):
    """Pla B: accepta l'oferta amb la finestra de la web."""
    pg.locator(f'.sw-content button[data-popup="market/offers-received/direct-transfer-confirmation"][data-id_bid="{o["id_bid"]}"]').first.click()
    pop = pg.locator("#popup-content")
    pop.locator("input[name=type][value=accept]").wait_for(state="attached", timeout=10000)
    pg.wait_for_timeout(800)
    btn = pop.locator("#btn-send")
    if not btn.count():
        btn = pop.locator("button").filter(has_text=re.compile(r"^\s*(Vendre|Vender)\s*$"))
    btn.first.click()


LOANS_JS = """() => { const c = document.querySelector('.sw-content'); if (!c) return [];
    return [...c.querySelectorAll('button[data-popup="loan-confirm"]')].map(b => {
        let li = b.closest('li[data-id-offer]'); let user = li ? (li.querySelector('.user-name strong') || {}).innerText : null;
        return { id_bid: b.dataset.id, name: b.dataset.name, amount: +b.dataset.amount, days: +b.dataset.days, user }; }); }"""


def loan_offers(pg):
    """Peticions de cessió rebudes (Mercat → «N ofertas recibidas», botó «loan-confirm»)."""
    pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    btn = pg.locator(".offers-received[data-sw]").first
    if not btn.count():
        return []
    btn.click()
    pg.locator(".sw-content").first.wait_for(state="visible", timeout=10000)
    pg.wait_for_timeout(2500)
    return pg.evaluate(LOANS_JS)


def accept_loans(pg, name, dry=False):
    """Accepta les peticions de cessió dels jugadors que el bot ha marcat com a cedibles (els que no són a l'onze;
    decisió del David, 31/10). Primer per l'API (ajax/loan-confirm), si no amb la finestra."""
    from bot import misterapi
    out = []
    for o in loan_offers(pg):
        txt = f"{o['name']} → {o.get('user') or '?'} ({o['days']} dies, {o['amount'] / 1e6:.2f}M)"
        if dry:
            out.append(f"acceptaria {txt}")
            continue
        ok = False
        if misterapi.API is not None:
            try:
                d = misterapi.API.ajax("loan-confirm", {"id_bid": o["id_bid"]})
                ok = isinstance(d, dict) and d.get("status") == "ok"
            except Exception as e:
                print(f"::warning title=Mister API cessió::{str(e)[:200]} → finestra")
        if not ok:
            try:
                pg.locator(f'.sw-content button[data-popup="loan-confirm"][data-id="{o["id_bid"]}"]').first.click()
                pg.locator("#popup-content #btn-send").first.wait_for(timeout=10000)
                pg.locator("#popup-content #btn-send").first.click()
                pg.wait_for_timeout(3000)
                ok = not any(x["id_bid"] == o["id_bid"] for x in loan_offers(pg))
            except Exception as e:
                print(f"::warning title=cessió finestra::{str(e)[:200]}")
        out.append(("✅ cedit " if ok else "⚠️ no he pogut acceptar ") + txt)
    return f"🔁 {name} · cessions: " + "; ".join(out) if out else None


def run_loans(dry=False, only=None, end=False):
    """Revisió de peticions de cessió (cada 5 min des de l'alineació final fins a l'inici de la jornada).
    end=True: la jornada ja ha començat → es desmarquen els cedibles que havia posat el bot."""
    from bot.mister import login, new_context as mctx
    report = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = mctx(b).new_page()
        login(pg)
        for name, cid, _, _ in LEAGUES:
            if only and name != only:
                continue
            try:
                pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
                from bot import misterapi
                if misterapi.API is not None:
                    misterapi.API.community(cid)
                if end:
                    st = load_json("mister_loanables.json", {})
                    gone = [pid for pid in st.get(name, []) if misterapi.use("loanable", pid, False, dry)]
                    st[name] = []
                    from bot.web import save_json as _sj
                    _sj("mister_loanables.json", st)
                    if gone:
                        print(f"::notice title=cessions::{name}: desmarcats {len(gone)} cedibles (comença la jornada)")
                    continue
                r = accept_loans(pg, name, dry)
                if r:
                    report.append(r)
            except Exception as e:
                report.append(f"❌ Mister · cessions · {name}: {type(e).__name__}: {str(e)[:200]}")
        b.close()
    for l in report:
        print("::notice title=cessions::" + l)
    if report:
        telegram("Mister · cessions" + (" (prova)" if dry else "") + "\n" + "\n".join(report))


def run(dry=False):
    report = []
    cache = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        sctx = new_context(b, "sorareinside"); spg = sctx.new_page(); login_sorareinside(spg); save_session(sctx, "sorareinside")
        pg = mister_context(b).new_page()
        login(pg)
        for name, cid, (country, league), minimum in LEAGUES:
            try:
                bal, squad, market, have, cap = league_data(b, pg, spg, cid, country, league, report, cache)
                onsale = [q for q in squad if q["onsale"]]
                if not onsale:
                    continue
                done = []
                for q in onsale:
                    label = f"{q['short']} ({q['pct'] if q['pct'] is not None else '?'}%)"
                    open_sale(pg, q["pid"])
                    txt = snap(pg, f"[{name}] {q['short']}")
                    debt = f"{cid}:{q['pid']}" in load_json("mister_debt_sales.json", {})  # venda per saldar el deute: sempre
                    if q["pct"] is not None and q["pct"] >= minimum and not debt:  # ha tornat a ser titular: es queda
                        if dry:
                            done.append(f"{label}: el trauria de la venda"); continue
                        from bot import misterapi
                        n = 1 if misterapi.use("unsell", q["pid"]) else click_text(pg, REMOVE)
                        done.append(f"{label}: tret de la venda" if n == 1 else f"{label}: ⚠️ volia treure'l de la venda però no he trobat el botó ({n})")
                        continue
                    pg.keyboard.press("Escape")
                    offer = offers(pg).get(q["pid"])
                    if not offer:
                        done.append(f"{label}: encara sense oferta"); continue
                    if dry:
                        done.append(f"{label}: acceptaria l'oferta del {offer['user']} de {offer['bid']/1e6:.2f}M"); continue
                    ok = accept(pg, q["pid"])
                    done.append(f"{label}: venut al {offer['user']} per {offer['bid']/1e6:.2f}M ✅" if ok else f"{label}: ⚠️ no he pogut acceptar l'oferta; fes-ho tu")
                report.append(f"💰 {name}: " + "; ".join(done))
            except Exception as e:
                report.append(f"❌ Mister · ofertes · {name}: {type(e).__name__}: {str(e)[:200]}")
        b.close()
    txt = "\n".join(LOG)
    for i in range(0, min(len(txt), 6 * 6000), 6000):
        print("::notice title=snap" + str(i // 6000) + "::" + txt[i:i + 6000].replace("\n", " ¶ "))
    for l in report:
        print("::notice title=mister::" + l)
    if report:
        telegram("Mister · ofertes" + (" (prova)" if dry else "") + "\n" + "\n".join(report))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--cessions", action="store_true")
    a = ap.parse_args()
    run_loans(a.dry) if a.cessions else run(a.dry)
