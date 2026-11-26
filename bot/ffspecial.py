"""FutbolFantasy · jocs especials d'un partit («Puntos en el X - Y»), decisió del David (26/11, Getafe):
els N jugadors amb més PS de SorareInside (≥80%, o titulars oficials a la revisió final) dels dos equips del partit.

Ús: python -m bot.ffspecial [--dry] [--final] [--joc ID]
"""
import argparse
import datetime as dt
import re

from playwright.sync_api import sync_playwright

from bot import ff
from bot import si
from bot.ff import COMPS, FF, MADRID, name_score
from bot.notify import telegram
from bot.web import inject, login_futbolfantasy, login_sorareinside, new_context, save_session

EXTRA_COMPS = [("Conference League", "conference-league", ("Europe", "UEFA Conference League"))]


def teams_of(card):
    txt = f"{card.get('title') or ''} {card.get('label') or ''}"
    m = re.search(r"(?:en el|en|del)\s+(.+?)\s*[-–]\s*(.+?)(?:\s*\(|\s*·|$)", txt, re.I)
    return (m.group(1).strip(), m.group(2).strip()) if m else None


def specials(cards):
    out = []
    for c in cards:
        if any((c["label"] or "").startswith(x[0] + " ·") for x in COMPS):
            continue
        if re.search(r"revulsivo|antagonista|resiliencia|copa", (c["label"] or "") + " " + (c["title"] or ""), re.I):
            continue
        if c["hours"] is None or c["hours"] <= 0:
            continue
        t = teams_of(c)
        if t:
            out.append((c, t))
    return out


def team_match(a, b):
    return name_score(a, b) >= 70 or ff.plain(a).lower() in ff.plain(b).lower() or ff.plain(b).lower() in ff.plain(a).lower()


def match_links(pg, ta, tb):
    """Pàgines de partit de futbolfantasy.com (/partidos/…) dels dos equips."""
    keys = [ff.plain(t).lower().split()[0] for t in (ta, tb)]
    seen = []
    for url in (FF, f"{FF}/conference-league", f"{FF}/conference-league/posibles-alineaciones", f"{FF}/europa-league/posibles-alineaciones",
                f"{FF}/champions/posibles-alineaciones", f"{FF}/laliga/posibles-alineaciones"):
        try:
            pg.goto(url, wait_until="domcontentloaded", timeout=45000); pg.wait_for_timeout(2000)
            links = pg.evaluate("() => [...new Set([...document.querySelectorAll('a[href*=\"/partidos/\"]')].map(a => a.href.split('#')[0]))]")
        except Exception:
            continue
        for u in links:
            low = u.lower()
            if all(k in low for k in keys) and u not in seen:
                seen.append(u)
        if seen:
            break
    print("::notice title=FF especials::pàgines del partit: " + (" | ".join(seen) or "cap"))
    return seen


def ff_fallback(pg, spg, card, ta, tb, dry, report, label, deadline):
    from bot.copa import PLAYERS_JS
    links = match_links(pg, ta, tb)
    if not links:
        return None
    pg.goto(links[0], wait_until="domcontentloaded", timeout=60000); pg.wait_for_timeout(3000)
    rows = pg.evaluate(PLAYERS_JS, links[0]) or []
    oficial = bool(re.search(r"alineaci[oó]n (oficial|confirmada)", pg.inner_text("body")[:4000], re.I))
    ok = [r for r in rows if not r["suplente"] and str(r["lesion"]) in ("-1", "", "None") and (oficial or r["pct"] >= 80)]
    # (26/11) la pàgina de la Conference no té punts: per ordenar, el PS de SorareInside de la propera jornada de lliga
    # (el Getafe sí; l'Iberia no hi és i va després); a igualtat, el %
    ps = {}
    for name, slug, (country, league) in [c for c in COMPS if c[2][0] != "Europe"]:
        for add in (3, 2, 4):
            try:
                d = si.extract_league(spg, country, league, (deadline + dt.timedelta(days=add)).date(), use_cache=True)
            except Exception:
                continue
            order = d.get("_order") or []
            if not any(team_match(ta, t) or team_match(tb, t) for t in order):
                break
            for t in order:
                if not (team_match(ta, t) or team_match(tb, t)) or not isinstance(d.get(t), list):
                    continue
                for row in d[t]:
                    for p_ in row:
                        if p_.get("ps") is not None:
                            ps[p_["name"]] = p_["ps"]
            break
        if ps:
            break
    for r in ok:
        r["ps"] = max((v for k, v in ps.items() if name_score(r["name"], k) >= 80), default=None)
    ok.sort(key=lambda r: (r["ps"] is None, -(r["ps"] or 0), -r["pct"]))
    print("::notice title=FF especials::" + f"{len(rows)} jugadors, {len(ok)} titulars ≥80%{' (onze oficial)' if oficial else ''}: "
          + ", ".join(f"{r['name']} {r['pct']}% PS {r['ps']}" for r in ok)[:1500])
    pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    inject(pg, "ff")
    cur = next((c for c in ff.cards(pg) if c["id"] == card["id"]), card)
    if cur["empty"] == 0:
        report.append(f"✅ {label}: ja és ple; no el toco")
        return True
    ff.open_picker(pg, card["id"])
    pick = []
    for r in ok:
        if len(pick) >= cur["empty"]:
            break
        res = [x for x in (pg.evaluate("(s) => __ff.search(s)", r["name"]) or []) if name_score(r["name"], x["n"]) >= 80]
        if len(res) == 1 and str(res[0]["id"]) not in set(cur["ids"]) and str(res[0].get("u")) != "0":
            pick.append({"ff": res[0]["n"], "ffid": str(res[0]["id"]), "pct": r["pct"], "ps": r["ps"]})
    ff.close_modal(pg)
    names = ", ".join(f"{c['ff']} ({c['pct']}%, PS lliga {c['ps'] if c['ps'] is not None else '?'})" for c in pick)
    if dry:
        report.append(f"🧪 {label} (futbolfantasy.com, {cur['empty']} buides): posaria {names or 'ningú'}")
        return True
    pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    inject(pg, "ff")
    ff.fill(pg, card["id"], pick)
    after = next((c for c in ff.cards(pg) if c["id"] == card["id"]), {"empty": "?"})
    report.append(f"{'✅' if after['empty'] == 0 else '⚠️'} {label} (futbolfantasy.com, SorareInside no té el partit): {names} · buides: {after['empty']}")
    return True


def apply_pick(pg, card, label, ranked, dry, src="SorareInside"):
    """ranked: candidats ja ordenats (name, ps, pct). Deixa al joc els N primers: treu els posats que ja no hi
    són i hi posa els que falten (també si el joc ja era ple; 26/11, Gudelj → Djené)."""
    pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    inject(pg, "ff")
    cur = next((c for c in ff.cards(pg) if c["id"] == card["id"]), card)
    slots = [x for x in (pg.evaluate("(id) => __ff.slots(id)", card["id"]) or [])]
    n = len(slots) or (cur["empty"] + len(cur["ids"]))
    placed = [x for x in slots if x["name"] and x["name"] not in ("+",) and len(x["name"]) > 1][:len(cur["ids"])]
    want, keep = [], []
    for c in ranked:
        if len(want) >= n:
            break
        hit = next((x for x in placed if x not in keep and (name_score(c["name"], x["name"]) >= 60
                    or ff.plain(x["name"]).lower() in ff.plain(c["name"]).lower().split())), None)  # «Djené» = «Djené Dakonam»
        if hit:
            keep.append(hit)
        want.append((c, hit))
    out = [x for x in placed if x not in keep]
    new = [c for c, hit in want if not hit]
    desc = ", ".join(f"{c['name']} ({c.get('ps') if c.get('ps') is not None else '?'} PS, {c.get('pct')}%)" for c, _ in want)
    if not new and not out:
        return f"✅ {label}: sense canvis ({desc})"
    print("::notice title=FF especial::" + f"posats: {[x['name'] for x in placed]} · vull: {desc} · surten: {[x['name'] for x in out]}")
    if len(new) > len(out) + (n - len(placed)):  # (26/11) no hi ha lloc: un nom no s'ha reconegut; no es toca res
        return f"⚠️ {label}: no reconec algun dels posats ({', '.join(x['name'] for x in placed)}); no toco res · ara: {desc}"
    if dry:
        return (f"🧪 {label} ({src}): quedaria {desc} · surten {', '.join(x['name'] for x in out) or 'cap'}"
                f" · entren {', '.join(c['name'] for c in new) or 'cap'}")
    for x in out:
        ff.remove_slot(pg, card["id"], x["slot"])
    pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    inject(pg, "ff")
    # nom de FutbolFantasy de cada nou (mateix cercador que la resta del bot); si un no es troba, el següent de la llista
    ff.open_picker(pg, card["id"])
    have = {x["name"] for x in keep}
    rest = [c for c in ranked if not any(name_score(c["name"], h) >= 60 for h in have)]
    pick = []
    for c in rest:
        if len(pick) >= n - len(keep):
            break
        res = [x for x in (pg.evaluate("(s) => __ff.search(s)", c["name"]) or []) if name_score(c["name"], x["n"]) >= 80]
        if not res:
            res = [x for x in (pg.evaluate("(s) => __ff.search(s)", ff.plain(c["name"]).split()[-1]) or []) if name_score(c["name"], x["n"]) >= 80]
        if len(res) == 1 and str(res[0].get("u")) != "0":
            pick.append(dict(c, ff=res[0]["n"], ffid=str(res[0]["id"])))
    ff.close_modal(pg)
    pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    inject(pg, "ff")
    ff.fill(pg, card["id"], pick)
    after = next((c for c in ff.cards(pg) if c["id"] == card["id"]), {"empty": "?"})
    return (f"{'✅' if after['empty'] == 0 else '⚠️'} {label} ({src}): {', '.join(x['name'] for x in keep) + (', ' if keep and pick else '')}"
            f"{', '.join(c['ff'] + ' (' + str(c.get('ps')) + ' PS)' for c in pick)} · surten {', '.join(x['name'] for x in out) or 'cap'} · buides: {after['empty']}")


def run(dry=False, final=False, only=None):
    report = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = new_context(b, "futbolfantasy")
        pg = ctx.new_page()
        login_futbolfantasy(pg)
        save_session(ctx, "futbolfantasy")
        allc = ff.cards(pg)
        todo = [(c, t) for c, t in specials(allc) if not only or c["id"] == only]
        from bot.web import save_json
        save_json("ff_specials.json", {c["id"]: c["end"] for c, _ in specials(allc) if c["end"]})
        print("::notice title=FF especials::" + " | ".join(f"{c['id']} {c['label']} / {c['title']} → {t} · buits {c['empty']} · {c['hours']:.1f} h" for c, t in todo)[:3000])
        if not todo:
            print("::notice title=FF especials::cap joc especial de partit obert · cartes: "
                  + " | ".join(f"{c['id']} {c['label']} / {c['title']}" for c in allc)[:3000])
        sctx = spg = None
        for card, (ta, tb) in todo:
            label = f"{card['label'] or card['title']}"
            deadline = dt.datetime.now(MADRID) + dt.timedelta(hours=card["hours"])
            if spg is None:
                sctx = new_context(b, "sorareinside")
                spg = sctx.new_page()
                login_sorareinside(spg)
                save_session(sctx, "sorareinside")
            sidata, teams = None, None
            for name, slug, (country, league) in [c for c in COMPS if c[2][0] == 'Europe'] + EXTRA_COMPS + [c for c in COMPS if c[2][0] != 'Europe']:
                try:
                    d = si.extract_league(spg, country, league, deadline.date(), use_cache=False)
                except Exception as e:
                    print(f"::notice title=FF especials::{name}: {type(e).__name__} {str(e)[:100]}")
                    continue
                order = d.get("_order") or []
                A = next((t for t in order if team_match(ta, t)), None)
                B = next((t for t in order if team_match(tb, t)), None)
                # (26/11) un equip amb un altre nom a SorareInside (Iberia 1999 = «FC Saburtalo Tbilisi»): n'hi ha prou
                # amb un; l'altre és el seu rival (l'ordre de SorareInside va per parelles local–visitant)
                opp = {}
                for i in range(0, len(order) - 1, 2):
                    opp[order[i]], opp[order[i + 1]] = order[i + 1], order[i]
                if A and not B:
                    B = opp.get(A)
                elif B and not A:
                    A = opp.get(B)
                if A and B:
                    sidata, teams, comp_slug = d, (A, B), slug
                    break
            if not sidata:  # (26/11) Conference League: SorareInside no la té → alineació probable de futbolfantasy.com
                r = ff_fallback(pg, spg, card, ta, tb, dry, report, label, deadline)
                if r is not None:
                    continue
                report.append(f"⚠️ {label}: no trobo {ta} – {tb} ni a SorareInside ni a futbolfantasy.com")
                continue
            official, olog = {}, []
            if final:
                official = ff.official_lineups(comp_slug, deadline, sidata, wait_until=deadline.astimezone(dt.timezone.utc) - dt.timedelta(minutes=20), log=olog)
            cands = [c for c in ff.candidates(sidata, official) if c["team"] in teams]
            cands.sort(key=lambda c: (-c["ps"], c["idx"]))
            report.append(apply_pick(pg, card, label + f" ({teams[0]} – {teams[1]})", [dict(c, name=c["si"]) for c in cands], dry))
        b.close()
    for l in report:
        print("::notice title=FF especial::" + l)
    if report and not dry:
        telegram("FutbolFantasy · joc especial\n" + "\n".join(report))
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--joc")
    a = ap.parse_args()
    try:
        run(a.dry, a.final, a.joc)
    except Exception:
        import traceback
        print("::notice title=tb::" + traceback.format_exc().replace("\n", " | ")[-1500:])
        raise
