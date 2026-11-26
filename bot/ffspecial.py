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
            for name, slug, (country, league) in COMPS + EXTRA_COMPS:
                try:
                    d = si.extract_league(spg, country, league, deadline.date(), use_cache=False)
                except Exception as e:
                    print(f"::notice title=FF especials::{name}: {type(e).__name__} {str(e)[:100]}")
                    continue
                order = d.get("_order") or []
                A = next((t for t in order if team_match(ta, t)), None)
                B = next((t for t in order if team_match(tb, t)), None)
                if A and B:
                    sidata, teams, comp_slug = d, (A, B), slug
                    break
            if not sidata:
                report.append(f"⚠️ {label}: no trobo {ta} – {tb} a SorareInside")
                continue
            official, olog = {}, []
            if final:
                official = ff.official_lineups(comp_slug, deadline, sidata, wait_until=deadline.astimezone(dt.timezone.utc) - dt.timedelta(minutes=20), log=olog)
            cands = [c for c in ff.candidates(sidata, official) if c["team"] in teams]
            pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            inject(pg, "ff")
            cur = next((c for c in ff.cards(pg) if c["id"] == card["id"]), card)
            n = len(cur["slots"]) if cur.get("slots") else (cur["empty"] + len(cur["ids"]))
            if cur["empty"] == 0:
                report.append(f"✅ {label}: ja és ple ({n} jugadors); no el toco")
                continue
            found, missing = ff.lookup(pg, card["id"], cands)
            found.sort(key=lambda c: (-c["ps"], c["idx"]))
            have = set(cur["ids"])
            pick = [c for c in found if c["ffid"] not in have][:cur["empty"]]
            names = ", ".join(f"{c['ff']} ({c['team']}, {c['ps']} PS, {c['pct']}%)" for c in pick)
            if dry:
                report.append(f"🧪 {label} ({teams[0]} – {teams[1]}, {n} places, {cur['empty']} buides): posaria {names or 'ningú'}"
                              + (f" · no trobats: {', '.join(missing[:5])}" if missing else ""))
                continue
            pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            inject(pg, "ff")
            ff.fill(pg, card["id"], pick)
            after = next((c for c in ff.cards(pg) if c["id"] == card["id"]), {"empty": "?"})
            report.append(f"{'✅' if after['empty'] == 0 else '⚠️'} {label} ({teams[0]} – {teams[1]}): {names} · buides: {after['empty']}")
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
