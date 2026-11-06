"""Diagnosi: com es relaciona el PS de SorareInside amb el % de titular, la posició i els punts (Mister / Fantasy✨)."""
import re
import statistics

import requests

from bot.ff import name_score, team_score
from bot.web import load_json

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}


def ff_points(comp="laliga2"):
    url = f"https://www.futbolfantasy.com/analytics/{comp + '/' if comp != 'laliga' else ''}estadisticas-puntos/2027?puntuacion=futbolfantasy-rpg"
    h = requests.get(url, headers=H, timeout=60).text
    out = []
    for m in re.finditer(r'<tr data-name="([^"]+)" data-posicion="([^"]*)" data-equipo="(\d+)">(.*?)</tr>', h, re.S):
        row = m.group(4)
        team = re.search(r'<div class="player-equipo">.*?<span>([^<]+)</span>', row, re.S)
        c = dict((a, (b, cc, d)) for a, b, cc, d in re.findall(r'data-value="([^"]+)"[^>]*data-total="([^"]*)"[^>]*data-casa="([^"]*)"[^>]*data-fuera="([^"]*)"', row))
        f = lambda k, i: float(c[k][i]) if k in c and c[k][i] not in ("", None) else None
        out.append({"name": m.group(1), "pos": m.group(2), "team": team.group(1) if team else "", "pj": f("partidos", 0),
                    "avg": f("23-totalPorPartido", 0), "home": f("23-totalPorPartido", 1), "away": f("23-totalPorPartido", 2)})
    return out


def corr(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    vx = sum((x - mx) ** 2 for x in xs); vy = sum((y - my) ** 2 for y in ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (vx * vy) ** 0.5 if vx and vy else 0


def lsq(X, y):
    """Mínims quadrats (sense numpy): X llista de files."""
    n = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) for j in range(n)] for i in range(n)]
    b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(n)]
    for i in range(n):  # Gauss
        p = max(range(i, n), key=lambda k: abs(A[k][i]))
        A[i], A[p], b[i], b[p] = A[p], A[i], b[p], b[i]
        for k in range(i + 1, n):
            f = A[k][i] / A[i][i]
            for j in range(i, n):
                A[k][j] -= f * A[i][j]
            b[k] -= f * b[i]
    x = [0] * n
    for i in reversed(range(n)):
        x[i] = (b[i] - sum(A[i][j] * x[j] for j in range(i + 1, n))) / A[i][i]
    pred = [sum(a * c for a, c in zip(r, x)) for r in X]
    my = statistics.mean(y)
    r2 = 1 - sum((p - t) ** 2 for p, t in zip(pred, y)) / sum((t - my) ** 2 for t in y)
    return x, r2


for comp, key in (("laliga2", "si_ff_laliga2.json"),):
    sid = load_json(key, {})
    fp = ff_points(comp)
    R = load_json("mister_rosters.json", {}).get("teams", {})
    print(f"::notice title=dades {comp}::SI equips {len(sid.get('_order', []))}, Fantasy✨ jugadors {len(fp)}, plantilles Mister {len(R)}")
    rows = []
    order = sid.get("_order", [])
    for idx, t in enumerate(order):
        lst = sid.get(t)
        if not isinstance(lst, list):
            continue
        home = idx % 2 == 0
        slug = max(R, key=lambda s: team_score(s, t), default=None) if R else None
        for li, r in enumerate(lst):
            for p in r:
                if p.get("ps") is None or p.get("ps_est") or p.get("pct") is None:
                    continue
                f = max((q for q in fp if team_score(q["team"], t) > 0), key=lambda q: name_score(p["name"], q["name"]), default=None)
                f = f if f and name_score(p["name"], f["name"]) >= 75 else None
                m = None
                if slug and team_score(slug, t) > 0:
                    m = max(R[slug], key=lambda q: name_score(p["name"], q["name"]), default=None)
                    m = m if m and name_score(p["name"], m["name"]) >= 75 else None
                mb = (statistics.mean(m["streak"]) if m and m["streak"] else (m or {}).get("avg"))
                rows.append({"name": p["name"], "t": t, "line": li, "pct": p["pct"], "ps": p["ps"], "home": home,
                             "ff": f and (f["home"] if home else f["away"]) if f and f.get("pj") else None, "ffavg": f and f["avg"],
                             "mi": mb, "miavg": m and m.get("avg")})
    print(f"::notice title=files {comp}::{len(rows)} jugadors amb PS; amb Fantasy✨ {sum(1 for r in rows if r['ffavg'] is not None)}, amb Mister {sum(1 for r in rows if r['mi'] is not None)}")
    ys = [r["ps"] for r in rows]
    print(f"::notice title=PS vs %::corr {corr([r['pct'] for r in rows], ys):.2f}; per franja: " + ", ".join(
        f"{lo}-{lo + 9}%: {statistics.mean([r['ps'] for r in rows if lo <= r['pct'] < lo + 10]):.1f} (n={sum(1 for r in rows if lo <= r['pct'] < lo + 10)})"
        for lo in range(20, 100, 10) if any(lo <= r['pct'] < lo + 10 for r in rows)))
    print("::notice title=PS per línia::" + ", ".join(f"línia {l}: {statistics.mean([r['ps'] for r in rows if r['line'] == l]):.1f} (n={sum(1 for r in rows if r['line'] == l)})" for l in sorted({r['line'] for r in rows})))
    for src in ("ff", "ffavg", "mi", "miavg"):
        sub = [r for r in rows if r[src] is not None]
        if len(sub) < 10:
            continue
        y = [r["ps"] for r in sub]
        x1, r2a = lsq([[1, r[src]] for r in sub], y)
        x2, r2b = lsq([[1, r[src], r["pct"] / 100, 1 if r["home"] else 0] + [1 if r["line"] == l else 0 for l in (1, 2, 3)] for r in sub], y)
        x3, r2c = lsq([[r["pct"] / 100, r["pct"] / 100 * r[src]] for r in sub], y)
        print(f"::notice title=model {src}::n={len(sub)} corr {corr([r[src] for r in sub], y):.2f} | PS=a+b·x R²={r2a:.2f} ({x1[0]:.1f}+{x1[1]:.2f}x) | "
              f"+%+casa+línia R²={r2b:.2f} coef {[round(v, 2) for v in x2]} | PS=%·(a+b·x) R²={r2c:.2f} {[round(v, 2) for v in x3]}")
    sample = sorted(rows, key=lambda r: -r["ps"])[:12] + sorted(rows, key=lambda r: r["ps"])[:8]
    print("::notice title=mostra::" + " · ".join(f"{r['name']} PS{r['ps']} {r['pct']}% L{r['line']} ff{r['ff']} mi{r['mi'] and round(r['mi'], 1)}" for r in sample))
