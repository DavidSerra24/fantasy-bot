"""Recomanació de cessions per a l'alineació del Mister (decisió del David, 7/11: «que el bot em recomani què fitxar de
cessions perquè li vagi bé per fer l'alineació»). Només lectura: no demana cap cessió (les fa el David).

Mira els cedibles dels altres mànagers (misterclause.main, loan_only), els afegeix a la plantilla i prova totes les
combinacions de fins a MAX["M"] migcampistes, MAX["D"] defenses i MAX["F"] davanters (el que el David pot aconseguir)
amb el mateix motor de l'alineació (misterlineup.best_lineup: franges de %, PS i norma de rivals). Es queda la
combinació amb més punts esperats (PS × % dels onze) i, a igualtat, la de menys cessions; només recomana els que
entrarien a l'onze.
Ús: python -m bot.misterloanrec [Quique] [M=3] [D=1] [F=0] [--send]
"""
import itertools
import sys

from playwright.sync_api import sync_playwright

from bot.mister import login, new_context as mister_context
from bot.misterlineup import best_lineup, match_keys
from bot.misterplan import LEAGUES
from bot.mistermarket import league_data
from bot.notify import telegram
from bot.web import login_sorareinside, new_context, save_session

PN = {1: "G", 2: "D", 3: "M", 4: "F"}
LBL = {"G": "POR", "D": "DEF", "M": "MIG", "F": "DAV"}


def expected(pick):
    return sum(((q.get("si") or {}).get("ps") or 0) * (q.get("pct") or 0) / 100 for q in pick)


def evaluate(squad):
    res = best_lineup(squad)
    if not res:
        return None
    tac, pick, cap = res
    return (len(pick), -sum(1 for q in pick if q.get("rule_skip")), round(expected(pick), 1)), tac, pick, cap


def run(name="Quique", maxn=None, send=False):
    from bot.misterclause import main as scan
    maxn = maxn or {"M": 3, "D": 1, "F": 0}
    loans = scan(name, "TOT", 60, loan_only=True, maxpct=100, send=False)
    report, cache = [], {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        sctx = new_context(b, "sorareinside"); spg = sctx.new_page(); login_sorareinside(spg); save_session(sctx, "sorareinside")
        pg = mister_context(b).new_page()
        login(pg)
        for n, cid, (country, league), minimum in LEAGUES:
            if n != name:
                continue
            bal, squad, market, have, cap = league_data(b, pg, spg, cid, country, league, report, cache)
        b.close()
    sid = cache.get("sid:" + league)
    have = {q["pid"] for q in squad}
    cands = []
    for c in loans:
        P = PN.get(c.get("P"))
        if P not in maxn or not maxn[P] or c["pid"] in have or not c.get("si_e") or c.get("pct") is None:
            continue
        cands.append({"pid": c["pid"], "name": c["name"], "short": f"{c['name']} (cessió de {c['owner']})", "P": P, "pct": c["pct"],
                      "si": c["si_e"], "onsale": False, "loaned": False, "team": c.get("team"), "owner": c["owner"], "loan": c.get("loan"), "new": True})
    allq = squad + cands
    match_keys(allq, sid)
    order = (sid or {}).get("_order", [])
    for q in allq:  # el costat del partit, el mateix per a tots: l'equip de SorareInside
        k = str(((q.get("si") or {}).get("key")) or "")
        if k in order:
            q["side"] = k
    base = evaluate(squad)
    # els millors de cada posició (per punts esperats) per no provar milers de combinacions
    pools = {P: sorted([c for c in cands if c["P"] == P], key=lambda c: -((c["si"].get("ps") or 0) * c["pct"]))[:8] for P in maxn}
    best = (base[0], 0), base, ()
    combos = [[()] + [x for k in range(1, maxn[P] + 1) for x in itertools.combinations(pools[P], k)] for P in maxn if maxn[P]]
    for parts in itertools.product(*combos):
        add = tuple(q for part in parts for q in part)
        if not add:
            continue
        r = evaluate(squad + list(add))
        if not r:
            continue
        used = tuple(q for q in add if q in r[2])
        if len(used) < len(add):
            continue  # la mateixa combinació sense els que no entren ja s'ha provat
        key = (r[0], -len(add))
        if key > best[0]:
            best = key, r, add
    (_, (bkey, tac, pick, capn), add) = best[0], best[1], best[2]
    o = {"G": 0, "D": 1, "M": 2, "F": 3}
    fmt = lambda q: f"{q['short'] if not q.get('new') else q['name']}{' ©' if q is capn else ''} ({q.get('xpct') if q.get('xpct') is not None else '?'}%/{q.get('xps') if q.get('xps') is not None else '-'})"
    lines = [f"🔁 {name} · cessions recomanades per a l'alineació (fins a {', '.join(f'{v} {LBL[k]}' for k, v in maxn.items() if v)}):"]
    if not add:
        lines.append("Cap cessió millora l'onze d'ara." + (f" ({len(cands)} cedibles mirats)" if cands else " No hi ha cedibles amb dades de SorareInside."))
    else:
        for q in sorted(add, key=lambda q: o[q["P"]]):
            ps = q["si"].get("ps")
            lines.append(f"• {LBL[q['P']]} {q['name']} ({q['team']}) · {q['pct']}% · PS {('≈' if q['si'].get('ps_est') else '') + str(ps) if ps is not None else '-'} · de {q['owner']}")
        lines.append(f"Punts esperats de l'onze: {base[0][2]} → {bkey[2]} (+{bkey[2] - base[0][2]:.1f})")
    lines.append(f"Onze ({tac}): " + ", ".join(fmt(q) for q in sorted(pick, key=lambda q: o[q["P"]])))
    lines.append("Aquests no els demano: les cessions les fas tu. Quan els tinguis, l'alineació els tindrà en compte.")
    msg = "\n".join(lines)
    print("::notice title=cessions recomanades::" + msg.replace("\n", " ¶ "))
    print("::notice title=cedibles mirats::" + ", ".join(f"{c['name']} {LBL[c['P']]} {c['pct']}%/{c['si'].get('ps')}" for c in cands)[:3000])
    if send:
        telegram(msg)
    return msg


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    nm = next((x for x in a if "=" not in x), "Quique")
    mx = {"M": 3, "D": 1, "F": 0}
    for x in a:
        if "=" in x:
            k, v = x.split("=")
            mx[k.upper()] = int(v)
    run(nm, mx, send="--send" in sys.argv)
