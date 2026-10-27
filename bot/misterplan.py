"""Mister, fase 1 (només lectura): per a cada lliga llegeix la plantilla i el mercat, hi creua les dades de
SorareInside i envia per Telegram l'onze que posaria, el capità i les compres/vendes que faria. No toca res."""
import datetime as dt
import re

from playwright.sync_api import sync_playwright

from bot import si
from bot.ff import name_score, norm
from bot.mister import U, login, new_context as mister_context
from bot.notify import telegram
from bot.web import login_sorareinside, new_context, save_session

LEAGUES = [  # (nom al Mister, id_community, lliga SorareInside, mínim per fitxar)
    ("Quique", 2499621, ("Spain", "Segunda División"), 60),
    ("Fentaniños", 2519290, ("Spain", "Primera División"), 70),
]
POS = {"1": "G", "2": "D", "3": "M", "4": "F"}
TACTICS = ["3-4-3", "3-5-2", "4-3-3", "4-4-2", "4-5-1", "5-3-2", "5-4-1"]


def full_name(href):
    slug = (href or "").rstrip("/").split("/")[-1]
    return " ".join(w.capitalize() for w in slug.split("-"))


def read_squad(pg):
    pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    return pg.evaluate("""() => [...document.querySelectorAll('.player-row')].map(r => { const a = r.querySelector('a.player');
        const box = r.closest('li') || r.parentElement;
        return { href: a?.getAttribute('href'), short: r.querySelector('.name')?.innerText.trim(), pos: r.querySelector('.player-position')?.dataset.position,
                 pid: (a?.getAttribute('href') || '').split('/')[1],
                 tid: ((r.querySelector('img.team-logo')?.getAttribute('src') || '').match(/teams[/]([0-9]+)/) || [])[1],
                 value: +(r.querySelector('.underName')?.innerText.replace(/[^0-9]/g, '') || 0),
                 onsale: /en venda|en venta|a la venda/i.test(box?.innerText || ''),
                 loaned: /cedit/i.test(box?.innerText || '') }; }).filter(p => p.href)""")


def read_market(pg):
    pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    return pg.evaluate("""() => [...document.querySelectorAll('li[data-price]')].map(li => ({ pos: li.dataset.position, price: +li.dataset.price,
        owner: li.dataset.owner, href: li.querySelector('a.player')?.getAttribute('href'), short: li.querySelector('.name')?.innerText.trim() }))""")


def balance(pg):
    t = pg.locator(".btn-balance").first.inner_text() if pg.locator(".btn-balance").count() else ""
    m = re.search(r"(-?[\d.,]+)\s*M", t)
    return float(m.group(1).replace(".", "").replace(",", ".")) * 1e6 if m else None


def match(sidata, full):
    """Jugador de SorareInside (onze previst o suplents) amb el mateix nom. Exigeix nom complet o, si només
    coincideix el cognom, la mateixa inicial del nom (evita confondre David Soria amb Mario Soriano)."""
    best, bs = None, 0
    nf = norm(full)
    for t in sidata.get("_order", []):
        rows = sidata.get(t)
        if not isinstance(rows, list):
            continue
        for r in rows:
            for q in r:
                for cand, starter in [(q, True)] + [(x, False) for x in (q.get("subs") or [])]:
                    nm = cand.get("name") or ""
                    sc = name_score(full, nm)
                    if sc == 60 and not (norm(nm) and nf and norm(nm)[0][0] == nf[0][0] and norm(nm)[-1] == nf[-1]):
                        sc = 0
                    if sc > bs:
                        best, bs = {"name": nm, "pct": cand.get("pct"), "ps": cand.get("ps") if starter else None, "team": t}, sc
    return best if bs >= 60 else None


def enrich(players, sidata):
    from bot.sources import assign, si_entries
    for p in players:
        p["name"] = full_name(p["href"])
        p["short"] = re.sub(r"[^\w .'-]", "", p.get("short") or "").strip()
        p["P"] = POS.get(str(p["pos"]), "?")
    assign(players, si_entries(sidata), "si")
    for p in players:
        p["pct"] = (p["si"] or {}).get("pct")
        p["ps"] = (p["si"] or {}).get("ps")
        p["src"] = "SI" if p["si"] else None
    return players


def band(pct):
    if pct is None:
        return 9
    return 0 if pct >= 80 else 1 if pct >= 70 else 2 if pct >= 60 else 3


def lineup(squad):
    order = sorted(squad, key=lambda p: (band(p["pct"]), p["ps"] is None, -(p["ps"] or 0)))
    best = None
    for tac in TACTICS:
        d, m, f = map(int, tac.split("-"))
        need = {"G": 1, "D": d, "M": m, "F": f}
        pick = []
        for p in order:
            if need.get(p["P"], 0):
                pick.append(p); need[p["P"]] -= 1
        if any(need.values()):
            continue
        key = (-sum(band(p["pct"]) for p in pick), sum(p["ps"] or 0 for p in pick))
        if best is None or key > best[0]:
            best = (key, tac, pick)
    return best


def main():
    report = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        sctx = new_context(b, "sorareinside"); spg = sctx.new_page(); login_sorareinside(spg); save_session(sctx, "sorareinside")
        pg = mister_context(b).new_page()
        login(pg)
        for name, cid, (country, league), minimum in LEAGUES:
            try:
                pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
                bal = balance(pg)
                sidata = None
                for days in (4, 5, 6, 3, 7, 2, 1, 0):  # la gameweek de la propera jornada
                    try:
                        sidata = si.extract_league(spg, country, league, dt.date.today() + dt.timedelta(days=days), log=lambda *_: None)
                        break
                    except RuntimeError:
                        continue
                if not sidata:
                    raise RuntimeError("SorareInside encara no té la propera jornada")
                squad = enrich(read_squad(pg), sidata)
                market = enrich([m for m in read_market(pg) if m["href"]], sidata)
                lines = [f"🧢 Mister · {name} — saldo {bal/1e6:.1f}M" if bal is not None else f"🧢 Mister · {name}"]
                best = lineup(squad)
                if best:
                    (_, ps), tac, pick = best
                    cap = max(pick, key=lambda p: p["ps"] or -1)
                    o = {"G": 0, "D": 1, "M": 2, "F": 3}
                    lines.append(f"Onze ({tac}): " + ", ".join(f"{p['short']}{' ©' if p is cap else ''} {p['pct'] or '?'}%/{p['ps'] or '-'}" for p in sorted(pick, key=lambda p: o[p['P']])))
                else:
                    lines.append("⚠️ No surt cap onze vàlid amb la plantilla")
                sell = [p for p in squad if p["pct"] is not None and p["pct"] < minimum]
                lines.append("Vendria (<{}%): ".format(minimum) + (", ".join(f"{p['short']} {p['pct']}%" for p in sell) or "cap"))
                buy = sorted([m for m in market if m["pct"] is not None and m["pct"] >= minimum], key=lambda m: (band(m["pct"]), m["price"]))
                lines.append("Compraria: " + (", ".join(f"{m['short']} ({m['P']}, {m['pct']}%, {m['price']/1e6:.2f}M)" for m in buy[:8]) or "cap"))
                nodata = [p["short"] for p in squad if p["pct"] is None]
                if nodata:
                    lines.append("Sense dades a SorareInside: " + ", ".join(nodata))
                report.append("\n".join(lines))
            except Exception as e:
                report.append(f"❌ Mister · {name}: {type(e).__name__}: {str(e)[:200]}")
        b.close()
    msg = "Mister (prova, no he tocat res)\n\n" + "\n\n".join(report)
    print(msg)
    for l in report:
        print("::notice title=mister::" + l.replace("\n", " | "))
    telegram(msg)


if __name__ == "__main__":
    main()
