"""Mister: alineació i capità de la propera jornada.

Criteris (CLAUDE.md): primer els jugadors amb 80–90% (SorareInside) ordenats per PS, després 70% i després 60%;
dins de cada franja, primer els que tenen PS. Tàctica: la gratuïta que millor encaixi. Capità: el titular amb més PS.
Es poden posar jugadors d'equips que s'enfronten. Els jugadors en venda només entren si no n'hi ha d'altres.
Ús: python -m bot.misterlineup [--dry] [--lliga Quique|Fentaniños]
"""
import argparse
import re

from playwright.sync_api import sync_playwright

from bot.mister import U, login, new_context as mister_context
from bot.misterplan import LEAGUES, TACTICS, band
from bot.mistermarket import league_data
from bot.notify import telegram
from bot.web import login_sorareinside, new_context, save_session

POSN = {"G": "1", "D": "2", "M": "3", "F": "4"}


def match_keys(squad, sidata):
    """Posa q['match'] (partit que juga) i q['side'] (equip) quan la font ho diu: SorareInside → parella de l'_order,
    FutbolFantasy/Jornada Perfecta → URL del partit."""
    order = [t for t in (sidata or {}).get("_order", [])]
    for q in squad:
        src = q.get("si") or q.get("ff") or q.get("jp") or {}
        k = str(src.get("key") or "")
        if "/" in k:
            q["match"] = k
        elif k in order:
            q["match"] = "si:" + str(order.index(k) // 2)
        else:
            q["match"] = None
        q["side"] = q.get("team")


def clash(q, pick):
    """Norma de rivals al Mister (Sofascore): un porter o defensa no va amb cap jugador de l'equip rival."""
    if not q.get("match"):
        return False
    for o in pick:
        if o.get("match") == q["match"] and o.get("side") != q.get("side") and (q["P"] in "GD" or o["P"] in "GD"):
            return True
    return False


def lband(q):
    """Franja de % per a l'alineació. Fentaniños (% de futbolfantasy.com): del 70 al 95% és tot la mateixa franja
    i mana el PS (decisió del David, 30/10). Quique: 80–90% → 70% → 60%."""
    p = q.get("xpct")
    if q.get("bmode") == "ff" and p is not None:
        return 0 if p >= 70 else 2 if p >= 60 else 3
    return band(p)


def best_lineup(squad):
    """(tàctica, onze, capità). Ordre: no en venda, franja de %, amb PS, més PS."""
    for q in squad:
        q.pop("rule_skip", None)
        si = q.get("si") or {}
        q["xpct"] = q.get("pct")  # el % de la font de la lliga: FutbolFantasy (Fentaniños) o SorareInside/Jornada Perfecta (Quique)
        q["xps"] = si.get("ps")
    order = sorted([q for q in squad if not q.get("loaned")],
                   key=lambda q: (q["onsale"], lband(q), q["xps"] is None, -(q["xps"] or 0)))
    best = None
    for tac in TACTICS:
        d, m, f = map(int, tac.split("-"))
        need = {"G": 1, "D": d, "M": m, "F": f}
        pick = []
        for q in order:  # primer per ordre (franja i PS), saltant els que xocarien amb un rival
            if need.get(q["P"], 0) and not clash(q, pick):
                pick.append(q); need[q["P"]] -= 1
        for q in order:  # si no hi ha prou jugadors per completar l'onze, es salta la norma
            if need.get(q["P"], 0) and q not in pick:
                pick.append(q); need[q["P"]] -= 1; q["rule_skip"] = True
        key = (-sum(need.values()), -sum(q["onsale"] for q in pick), -sum(lband(q) for q in pick), sum(q["xps"] or 0 for q in pick))
        if best is None or key > best[0]:
            best = (key, tac, pick)
    if not best:
        return None
    if any(q.get("rule_skip") for q in best[2]):  # l'ordre «golafre» no ha trobat cap onze sense rivals: es busquen tots
        alt = exhaustive(order)
        if alt and alt[0][0] >= best[0][0]:  # un onze complet que compleix la norma (decisió del David, 30/10)
            for q in squad:
                q.pop("rule_skip", None)
            best = alt
    _, tac, pick = best
    cap = max(pick, key=lambda q: (q["xps"] or -1, q["xpct"] or 0))
    return tac, pick, cap


def exhaustive(order):
    """Tots els onzes possibles (per tàctica) que compleixen la norma de rivals; torna el millor amb la mateixa
    clau que l'ordre normal (complet, no en venda, franja de %, PS). None si no n'hi ha cap."""
    from itertools import combinations
    byp = {P: [q for q in order if q["P"] == P] for P in "GDMF"}
    bad = {(id(a), id(b)) for a in order for b in order if a is not b and clash(a, [b])}

    def ok(group, base):
        return all((id(a), id(b)) not in bad for a in group for b in base) and all((id(a), id(b)) not in bad for a, b in combinations(group, 2))
    best = None
    for tac in TACTICS:
        d, m, f = map(int, tac.split("-"))
        if len(byp["G"]) < 1 or len(byp["D"]) < d or len(byp["M"]) < m or len(byp["F"]) < f:
            continue
        for g in byp["G"]:
            for D in combinations(byp["D"], d):
                if not ok(D, [g]):
                    continue
                base = [g, *D]
                for F in combinations(byp["F"], f):
                    if not ok(F, base):
                        continue
                    base2 = base + list(F)
                    for M in combinations(byp["M"], m):
                        if not ok(M, base2):
                            continue
                        pick = base2 + list(M)
                        key = (0, -sum(q["onsale"] for q in pick), -sum(lband(q) for q in pick), sum(q["xps"] or 0 for q in pick))
                        if best is None or key > best[0]:
                            best = (key, tac, pick)
    return best


def open_next(pg):
    """Obre la propera jornada (la que encara no ha començat). Retorna l'URL o None."""
    pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    href = pg.evaluate("""() => { const a = [...document.querySelectorAll('a.nav__item.gameweek')].find(a => /Comen[çc]a|Empieza|Comienza/i.test(a.innerText));
        return a ? a.getAttribute('href') : null; }""")
    if not href:
        return None
    url = href if href.startswith("http") else U + "/" + href.lstrip("/")
    pg.goto(url, wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    return url


def slots(pg):
    return pg.evaluate("""() => [...document.querySelectorAll('.lineup-starting button.lineup-player')].map(b => ({
        slot: b.dataset.slot, pos: b.dataset.position, pid: b.dataset.id_player, cap: !!b.querySelector('.captain-badge'), off: b.disabled }))""")


def formation(pg):
    t = pg.locator("button[data-popup=formation]").first
    return t.inner_text().strip() if t.count() else None


def set_formation(pg, url, tac):
    pg.evaluate("() => document.querySelector('button[data-popup=formation]').click()")
    pg.locator(f'button.btn-free[data-formation="{tac}"]').first.wait_for(state="visible", timeout=10000)
    pg.locator(f'button.btn-free[data-formation="{tac}"]').first.click()
    pg.wait_for_timeout(3000)
    pg.goto(url, wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    return formation(pg) == tac


def put(pg, url, slot, pid):
    """Posa el jugador pid a la casella slot (clic a la casella → clic al jugador de la llista)."""
    pg.locator(f'.lineup-starting button.lineup-player[data-slot="{slot}"]').first.click()
    cand = pg.locator(f'.sw-content .player[data-id_player="{pid}"][data-slot="{slot}"]').first
    cand.wait_for(state="visible", timeout=10000)
    cand.click()
    pg.wait_for_timeout(2500)
    pg.goto(url, wait_until="domcontentloaded"); pg.wait_for_timeout(3000)


def set_captain(pg, url, slot):
    pg.locator(f'.lineup-starting button.lineup-player[data-slot="{slot}"]').first.click()
    tog = pg.locator(".sw-content input[data-captain-toggle]").first
    tog.wait_for(state="attached", timeout=10000)
    pg.wait_for_timeout(500)
    if not tog.is_checked():
        tog.evaluate("e => e.click()")
        pg.wait_for_timeout(2500)
    pg.goto(url, wait_until="domcontentloaded"); pg.wait_for_timeout(3000)


def apply(pg, squad, dry=False):
    """Posa l'onze i el capità. Retorna una línia de resum."""
    res = best_lineup(squad)
    tac, pick, cap = res
    gaps = 11 - len(pick)
    o = {"G": 0, "D": 1, "M": 2, "F": 3}
    desc = f"{tac}: " + ", ".join(f"{q['short']}{' ©' if q is cap else ''} ({q['xpct'] if q['xpct'] is not None else '?'}%/{q['xps'] if q['xps'] is not None else '-'})"
                                  for q in sorted(pick, key=lambda q: o[q["P"]]))
    skips = [q["short"] for q in pick if q.get("rule_skip")]
    if skips:
        desc += " | ℹ️ sense alternativa, salto la norma de rivals amb: " + ", ".join(skips)
    if gaps:
        desc += f" | ⚠️ falten {gaps} jugadors per completar l'onze"
    url = open_next(pg)
    if not url:
        return "⏸️ la jornada ja ha començat (no es pot canviar) · volia " + desc
    cur = slots(pg)
    if any(s["off"] for s in cur):
        return "⏸️ l'alineació està bloquejada · volia " + desc
    if dry:
        now = {s["pid"] for s in cur}
        return f"posaria {desc} (ara {formation(pg)}; canvis: {sum(1 for q in pick if q['pid'] not in now)})"
    problems = []
    if formation(pg) != tac and not set_formation(pg, url, tac):
        return f"❌ no he pogut posar la tàctica {tac}"
    for P, code in POSN.items():
        cur = slots(pg)
        want = [q["pid"] for q in pick if q["P"] == P]
        here = [s for s in cur if s["pos"] == code]
        todo = [pid for pid in want if pid not in {s["pid"] for s in here}]
        free = [s["slot"] for s in here if s["pid"] not in want]
        for pid, slot in zip(todo, free):
            try:
                put(pg, url, slot, pid)
            except Exception as e:
                problems.append(f"{next(q['short'] for q in pick if q['pid'] == pid)} ({type(e).__name__})")
                pg.goto(url, wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    cur = slots(pg)
    cs = next((s for s in cur if s["pid"] == cap["pid"]), None)
    if cs and not cs["cap"]:
        try:
            set_captain(pg, url, cs["slot"])
        except Exception as e:
            problems.append(f"capità ({type(e).__name__})")
    cur = slots(pg)
    ok = {s["pid"] for s in cur if s["pid"] not in ("0", None)} == {q["pid"] for q in pick} and formation(pg) == tac
    capok = any(s["cap"] and s["pid"] == cap["pid"] for s in cur)
    line = ("✅ " if ok and capok else "⚠️ ") + desc
    if not ok:
        line += " | ❗ l'onze no ha quedat igual, revisa-ho"
    if not capok:
        line += " | ❗ el capità no ha quedat posat"
    if problems:
        line += " | errors: " + ", ".join(problems)
    return line


SLUG = {"Fentaniños": "laliga", "Quique": "laliga2"}


def apply_official(squad, sidata, comp, report, name, wait=True):
    """Revisió final: amb els onzes oficials (ESPN) dels partits del primer horari de la jornada, els jugadors
    d'aquells equips que no surten de titulars passen a 0% (i els titulars a 100%). Espera fins 10 min abans si cal."""
    import datetime as dt
    from bot.ff import name_score, official_lineups
    from bot.web import load_json
    k = load_json("mister_kickoffs.json", {}).get(comp)
    if not k:
        return
    kick = dt.datetime.fromisoformat(k)
    log = []
    off = official_lineups(comp, kick, sidata or {}, wait_until=(kick - dt.timedelta(minutes=10)) if wait else None, log=log)
    out, inn = [], []
    for q in squad:
        team = (q.get("si") or {}).get("key")
        if team not in off:
            continue
        if any(name_score(q["name"], s_) >= 80 or name_score((q.get("si") or {}).get("name") or "", s_) >= 80 for s_ in off[team]):
            q["pct"] = 100; inn.append(q["short"])
        else:
            q["pct"] = 0; out.append(q["short"])
    line = f"📋 {name} · onzes oficials: " + ("; ".join(log) or "cap partit a l'hora del primer")
    if inn or out:
        line += f" | titulars: {', '.join(inn) or 'cap'} | NO titulars: {', '.join(out) or 'cap'}"
    report.append(line)


def loan_bench(squad, name, dry=False):
    """Marca com a cedibles (72 h) els jugadors de la plantilla que no són a l'onze: ni cedits a mi, ni ja cedits a un
    altre, ni en venda. Per l'API del Mister."""
    from bot import misterapi
    res = best_lineup(squad)
    if not res:
        return f"🔁 {name} · cessions: no he pogut calcular l'onze; no marco cap cedible"
    pick_ids = {q["pid"] for q in res[1]}
    bench = [q for q in squad if q["pid"] not in pick_ids and not q.get("loaned") and not q.get("loanin") and not q.get("onsale")]
    done, already, fail = [], [], []
    for q in bench:
        r = misterapi.use("loanable", q["pid"], True, dry)
        (already if r == "ja" else done if r else fail).append(q["short"])
    return (f"🔁 {name} · cedibles{' (prova)' if dry else ''}: " + (", ".join(done) or "cap de nou")
            + (f" · ja ho eren: {', '.join(already)}" if already else "") + (f" · ❌ no he pogut: {', '.join(fail)}" if fail else ""))


def run(dry=False, only=None, final=False, loans_only=False):
    report, cache = [], {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        sctx = new_context(b, "sorareinside"); spg = sctx.new_page(); login_sorareinside(spg); save_session(sctx, "sorareinside")
        pg = mister_context(b).new_page()
        login(pg)
        for name, cid, (country, league), minimum in LEAGUES:
            if only and only not in (name, league):
                continue
            try:
                bal, squad, market, have, cap = league_data(b, pg, spg, cid, country, league, report, cache)
                match_keys(squad, cache.get("sid:" + league))
                if loans_only:
                    report.append(loan_bench(squad, name, dry))
                    continue
                if final:
                    apply_official(squad, cache.get("sid:" + league), SLUG[name], report, name, wait=not dry)
                report.append(f"🧢 {name} · alineació: " + apply(pg, squad, dry))
                if final:  # després de la revisió final, els que sobren es posen com a cedibles (decisió del David, 31/10)
                    report.append(loan_bench(squad, name, dry))
            except Exception as e:
                report.append(f"❌ Mister · alineació · {name}: {type(e).__name__}: {str(e)[:200]}")
        b.close()
    for l in report:
        print("::notice title=mister::" + l)
    telegram("Mister · alineació" + (" (prova)" if dry else "") + "\n" + "\n".join(report))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--lliga", default=None)
    ap.add_argument("--final", action="store_true", help="revisió final amb els onzes oficials del primer partit")
    ap.add_argument("--cessions", action="store_true", help="només marcar com a cedibles els que no són a l'onze")
    a = ap.parse_args()
    run(a.dry, a.lliga, a.final, a.cessions)
