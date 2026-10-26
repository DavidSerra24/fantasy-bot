"""Mister: pujes automàtiques al mercat (jugadors lliures, owner 0) pel preu mínim.

Criteris (CLAUDE.md): jugadors amb % de titularitat ≥ mínim de la lliga; primer la franja més alta
(80–90%, després 70%, després 60%) i, dins de cada franja, del més barat al més car. Sense passar del màxim
que permet el Mister (saldo + negatiu permès) ni de les places lliures de la plantilla.
Ús: python -m bot.mistermarket [--dry]
"""
import argparse
import datetime as dt
import re

from playwright.sync_api import sync_playwright

from bot import si
from bot.mister import U, login, new_context as mister_context
from bot.misterplan import LEAGUES, TACTICS, band, balance, enrich, read_squad
from bot.notify import telegram
from bot.web import load_json, login_sorareinside, new_context, save_json, save_session


def si_next(spg, country, league):
    for days in (4, 5, 6, 3, 7, 2, 1, 0):
        try:
            return si.extract_league(spg, country, league, dt.date.today() + dt.timedelta(days=days), log=lambda *_: None)
        except RuntimeError:
            continue
    raise RuntimeError("SorareInside encara no té la propera jornada")


def read_free_market(pg):
    pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    return pg.evaluate("""() => [...document.querySelectorAll('li[data-owner="0"]')].map(li => ({
        pos: li.dataset.position, price: +li.dataset.price, pid: li.querySelector('[data-id_player]')?.dataset.id_player,
        href: li.querySelector('a.player')?.getAttribute('href'), short: li.querySelector('.name')?.innerText.trim(),
        mine: /(la teva|tu puja|has pujat|teva oferta)/i.test(li.innerText) }))""")


def squad_slots(pg):
    t = pg.inner_text("body")
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*jugador", t, re.I)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def bid(pg, pid):
    """Obre la finestra de puja i envia el preu mínim. Retorna (ok, màxim permès)."""
    pg.locator(f'li[data-owner="0"] button.btn-bid[data-id_player="{pid}"]').first.click()
    pg.locator("#form-bid").wait_for(timeout=10000)
    mx = pg.evaluate("() => +document.getElementById('input-range')?.max || null")
    pg.locator("#btn-send").click()
    pg.wait_for_timeout(2500)
    ok = not pg.locator("#form-bid").is_visible()
    if not ok:
        pg.keyboard.press("Escape")
    return ok, mx


def can_field(squad):
    """Hi ha alguna tàctica del Mister que es pugui completar amb aquesta plantilla?"""
    n = {k: sum(1 for p in squad if p["P"] == k) for k in "GDMF"}
    return n["G"] >= 1 and any(n["D"] >= d and n["M"] >= m and n["F"] >= f
                               for d, m, f in (map(int, t.split("-")) for t in TACTICS))


def sell(pg, pid):
    """Posa el jugador en venda pel preu mínim (el seu valor). Retorna True si la finestra es tanca bé."""
    pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    pg.locator(f'button.btn-popup[data-popup="sale"][data-id_player="{pid}"]').first.click()
    pg.locator("form input[name=action][value=sale]").first.wait_for(state="attached", timeout=10000)
    pg.wait_for_timeout(800)
    pg.locator("#btn-send").click()
    pg.wait_for_timeout(2500)
    ok = not pg.locator("#btn-send").is_visible()
    if not ok:
        pg.keyboard.press("Escape")
    return ok


def run(dry=False):
    report = []
    done = load_json("mister_bids.json", {})
    sold = load_json("mister_sales.json", {})
    with sync_playwright() as p:
        b = p.chromium.launch()
        sctx = new_context(b, "sorareinside"); spg = sctx.new_page(); login_sorareinside(spg); save_session(sctx, "sorareinside")
        pg = mister_context(b).new_page()
        login(pg)
        for name, cid, (country, league), minimum in LEAGUES:
            try:
                pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
                bal = balance(pg) or 0
                sidata = si_next(spg, country, league)
                squad = enrich(read_squad(pg), sidata)
                have, cap = squad_slots(pg)
                # Vendes: per sota del mínim de titularitat, sense deixar la plantilla sense onze possible
                keep = [q for q in squad if not q["onsale"] and f"{cid}:{q['pid']}" not in sold]
                sales, nosale = [], []
                for q in sorted([q for q in keep if q["pct"] is not None and q["pct"] < minimum and not q["loaned"]],
                                key=lambda q: (q["pct"], q["ps"] or 0)):
                    rest = [x for x in keep if x is not q]
                    if not can_field(rest):
                        nosale.append(f"{q['short']} (cal per fer l'onze)")
                        continue
                    if dry or sell(pg, q["pid"]):
                        sales.append(q); keep = rest
                        if not dry:
                            sold[f"{cid}:{q['pid']}"] = dt.date.today().isoformat()
                    else:
                        nosale.append(f"{q['short']} (error en posar-lo a la venda)")
                free = (cap - have) if have is not None else 3
                market = enrich([m for m in read_free_market(pg) if m["href"] and m["pid"]], sidata)
                cands = sorted([m for m in market if m["pct"] is not None and m["pct"] >= minimum and not m["mine"]
                                and f"{cid}:{m['pid']}" not in done], key=lambda m: (band(m["pct"]), m["price"]))
                placed, skipped, limit, spent = [], [], None, 0
                for m in cands:
                    if len(placed) >= free:
                        skipped.append(f"{m['short']} (plantilla plena)")
                        continue
                    if limit is not None and spent + m["price"] > limit:
                        skipped.append(f"{m['short']} (sense diners)")
                        continue
                    if dry:
                        placed.append(m); spent += m["price"]
                        continue
                    pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
                    ok, mx = bid(pg, m["pid"])
                    if mx and limit is None:
                        limit = mx
                    if ok:
                        placed.append(m); spent += m["price"]
                        done[f"{cid}:{m['pid']}"] = dt.date.today().isoformat()
                    else:
                        skipped.append(f"{m['short']} (error en pujar)")
                line = f"🧢 {name} (saldo {bal/1e6:.1f}M, plantilla {have}/{cap}): "
                line += ("pujaria per " if dry else "pujes: ") + (", ".join(f"{m['short']} ({m['P']}, {m['pct']}%, {m['price']/1e6:.2f}M)" for m in placed) or "cap")
                if skipped:
                    line += " | no: " + ", ".join(skipped[:6])
                line += " | " + ("vendria: " if dry else "en venda: ") + (", ".join(f"{q['short']} ({q['pct']}%)" for q in sales) or "cap")
                if nosale:
                    line += " | no venc: " + ", ".join(nosale)
                report.append(line)
            except Exception as e:
                report.append(f"❌ Mister · {name}: {type(e).__name__}: {str(e)[:200]}")
        save_json("mister_sales.json", {k: v for k, v in sold.items() if v >= (dt.date.today() - dt.timedelta(days=2)).isoformat()})
        save_json("mister_bids.json", {k: v for k, v in done.items() if v >= (dt.date.today() - dt.timedelta(days=3)).isoformat()})
        b.close()
    msg = "Mister · mercat" + (" (prova, sense pujar)" if dry else "") + "\n" + "\n".join(report)
    print(msg)
    for l in report:
        print("::notice title=mister::" + l)
    telegram(msg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    run(ap.parse_args().dry)
