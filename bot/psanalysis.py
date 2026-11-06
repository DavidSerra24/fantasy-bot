"""Diagnosi: quines dades milloren el PS estimat de Segona (validació deixant-ne un fora).
Variables: mitjana de la temporada, casa/fora, partits jugats (encongiment cap a la mitjana de la posició) i força
del rival (taula de FotMob: punts per partit i gols encaixats per partit)."""
import statistics

import requests

from bot import psest
from bot.ff import name_score, team_score
from bot.fotmob import H
from bot.web import load_json


def table():
    """{equip: {ppg, ga, gf}} de LaLiga 2 (FotMob)."""
    for url in ("https://www.fotmob.com/api/data/tables?leagueId=140", "https://www.fotmob.com/api/data/leagues?id=140&ccode3=ESP"):
        try:
            d = requests.get(url, headers=H, timeout=30).json()
        except Exception as e:
            print(f"::notice title=taula err::{url} {e}")
            continue
        blobs = d if isinstance(d, list) else (d.get("table") or [])
        rows = []
        for b in blobs if isinstance(blobs, list) else [blobs]:
            t = ((b.get("data") or {}).get("table") or {}).get("all") or []
            rows += t
        if rows:
            out = {}
            for r in rows:
                pl = r.get("played") or 1
                sc = str(r.get("scoresStr") or "0-0").split("-")
                out[r["name"]] = {"ppg": (r.get("pts") or 0) / pl, "gf": int(sc[0]) / pl, "ga": int(sc[1]) / pl}
            print(f"::notice title=taula::{url}: {len(out)} equips")
            return out
    return {}


def loo(X, y):
    """Error mitjà absolut deixant cada jugador fora (es reajusta el model sense ell)."""
    errs = []
    for i in range(len(y)):
        Xi, yi = X[:i] + X[i + 1:], y[:i] + y[i + 1:]
        c = psest._lsq(Xi, yi)
        if not c:
            return None
        errs.append(abs(sum(a * b for a, b in zip(c, X[i])) - y[i]))
    return statistics.mean(errs)


T = table()
sid = load_json("si_ff_laliga2.json", {})
order = sid.get("_order", [])
for source in ("mister", "ff"):
    if source == "ff":
        P = psest.ff_points("laliga2")
        pool = lambda t: [q for q in P if team_score(q["team"], t) > 0]
    else:
        R = psest.rosters(force=True)

        def pool(t):
            slug = max(R, key=lambda s_: team_score(s_.replace("-", " "), t), default=None)
            return R[slug] if slug and team_score(slug.replace("-", " "), t) > 0 else []
    rows = []
    for idx, t in enumerate(order):
        lst = sid.get(t)
        if not isinstance(lst, list):
            continue
        opp = order[idx + 1] if idx % 2 == 0 else order[idx - 1]
        to = max(T, key=lambda k: team_score(k, opp), default=None) if T else None
        to = T[to] if to and team_score(to, opp) > 0 else None
        cand = pool(t)
        for r in lst:
            for p in r:
                if p.get("ps") is None or p.get("ps_est"):
                    continue
                q = max(cand, key=lambda q: name_score(p["name"], q["name"]), default=None)
                if not q or name_score(p["name"], q["name"]) < 75 or q.get("avg") is None:
                    continue
                pj = q.get("pj")
                rows.append({"ps": p["ps"], "avg": q["avg"], "home": 1 if idx % 2 == 0 else 0, "pos": q.get("pos"), "pj": pj,
                             "oppg": to and to["ppg"], "oga": to and to["ga"], "ogf": to and to["gf"]})
    rows = [r for r in rows if r["oppg"] is not None] if T else rows
    y = [r["ps"] for r in rows]
    print(f"::notice title={source}::{len(rows)} jugadors; amb partits jugats {sum(1 for r in rows if r['pj'] is not None)}")
    base = [[1, r["avg"], r["home"]] for r in rows]
    res = {"mitjana + casa (ara)": loo(base, y)}
    pm = {}
    for r in rows:
        pm.setdefault(r["pos"], []).append(r["avg"])
    pm = {k: statistics.mean(v) for k, v in pm.items()}
    for k in (1, 2, 3, 5, 8):
        if sum(r["pj"] is not None for r in rows) >= len(rows) * 0.9:
            rows_k = rows
            sh = [[1, ((r["pj"] or 0) * r["avg"] + k * pm[r["pos"]]) / ((r["pj"] or 0) + k), r["home"]] for r in rows]
            res[f"+ encongiment k={k}"] = loo(sh, y)
    if T:
        res["+ rival punts/partit"] = loo([b + [r["oppg"]] for b, r in zip(base, rows)], y)
        res["+ rival gols encaixats"] = loo([b + [r["oga"]] for b, r in zip(base, rows)], y)
        res["+ rival gols fets"] = loo([b + [r["ogf"]] for b, r in zip(base, rows)], y)
        res["+ rival tot"] = loo([b + [r["oppg"], r["oga"], r["ogf"]] for b, r in zip(base, rows)], y)
    res["sense res (mitjana PS)"] = statistics.mean(abs(v - statistics.mean(y)) for v in y)
    print(f"::notice title=error {source}::" + " | ".join(f"{k}: {v:.2f}" for k, v in res.items() if v is not None))
