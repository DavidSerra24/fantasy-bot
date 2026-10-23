"""Consulta: % de titularitat i punts projectats (SorareInside) d'una llista de jugadors.

Ús: python -m bot.consulta --lliga laliga2 --jugadors "Matos, Alemañ, Tomeo"
Ordre (com el Mister): per % de titularitat (de més a menys) i, dins de cada %, per punts projectats.
Els jugadors sense punts van al final del seu grup; els que no surten a l'onze previst, al final de tot.
"""
import argparse
import datetime as dt

from playwright.sync_api import sync_playwright

from bot import si
from bot.ff import name_score, norm
from bot.notify import telegram
from bot.web import login_sorareinside, new_context, save_session

LEAGUES = {"laliga": ("Spain", "Primera División"), "laliga2": ("Spain", "Segunda División"),
           "premier-league": ("England", "Premier League"), "serie-a": ("Italy", "Serie A"),
           "champions": ("Europe", "UEFA Champions League"), "europa-league": ("Europe", "UEFA Europa League")}


def find(data, q):
    best, bs = None, 0
    for t in data.get("_order", []):
        rows = data.get(t)
        if not isinstance(rows, list):
            continue
        for r in rows:
            for p in r:
                sc = name_score(q, p["name"])
                if sc > bs:
                    best, bs = {**p, "team": t, "starter": True}, sc
                for sub in p.get("subs") or []:
                    sc2 = name_score(q, sub.get("name") or "")
                    if sc2 > bs:
                        best, bs = {"name": sub["name"], "pct": sub.get("pct"), "ps": None, "team": t, "starter": False}, sc2
    return best if bs >= 60 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lliga", default="laliga2")
    ap.add_argument("--jugadors", required=True)
    ap.add_argument("--dia", default=None, help="AAAA-MM-DD (per defecte, avui)")
    a = ap.parse_args()
    names = [x.strip() for x in a.jugadors.replace("\n", ",").split(",") if x.strip()]
    day = dt.date.fromisoformat(a.dia) if a.dia else dt.date.today()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = new_context(b, "sorareinside")
        pg = ctx.new_page()
        login_sorareinside(pg)
        save_session(ctx, "sorareinside")
        country, league = LEAGUES[a.lliga]
        data = si.extract_league(pg, country, league, day)
        b.close()
    rows = []
    for n in names:
        f = find(data, n)
        if f:
            rows.append((n, f))
        else:
            rows.append((n, None))
    found = [(n, f) for n, f in rows if f]
    missing = [n for n, f in rows if not f]
    found.sort(key=lambda x: (-(x[1]["pct"] or 0), x[1]["ps"] is None, -(x[1]["ps"] or 0)))
    lines = [f"📋 {league} ({data.get('_gw')}) — % titular · punts projectats"]
    for n, f in found:
        tag = "" if f["starter"] else " (suplent a l'onze previst)"
        lines.append(f"{f['pct'] if f['pct'] is not None else '-'}% · {f['ps'] if f['ps'] is not None else '-'} · {f['name']} ({f['team']}){tag}")
    if missing:
        lines.append("❓ Sense dades a SorareInside: " + ", ".join(missing))
    msg = "\n".join(lines)
    print(msg)
    for l in lines:
        print("::notice title=c::" + l)
    telegram(msg)


if __name__ == "__main__":
    main()
