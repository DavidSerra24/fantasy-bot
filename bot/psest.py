"""PS estimat per als jugadors de Segona sense punts projectats a SorareInside (els que no tenen carta de Sorare).

Decisió del David (6/11): per al Mister (Quique) i FutbolFantasy (LaLiga 2). Els estimats competeixen igual que els reals.
- Cada joc amb els seus punts: Mister → mitjana del Mister (fitxa de l'equip); futbolfantasy.com → mitjana de Fantasy✨
  (analytics, «Puntos por jugador»).
- PS ≈ a + b·mitjana + c·(juga a casa), ajustat cada vegada amb els jugadors que tenen PS real (vegeu fill()).
Les plantilles del Mister es desen a state/mister_rosters.json (es refan si tenen més de 20 h).
Ús (diagnosi): python -m bot.psest
"""
import datetime as dt
import re
import statistics

from bot.web import load_json, save_json

QUIQUE = 2499621  # lliga del Mister de LaLiga 2
TTL_H = 20
_MEMO = {}


def _num(s):
    try:
        return float(str(s).strip().replace(",", "."))
    except ValueError:
        return None


def parse_roster(html):
    """Jugadors de la pestanya «N jugadores» de la fitxa d'un equip del Mister."""
    i = html.find("panel-team")
    part = html[i:] if i >= 0 else html
    out = []
    for li in re.findall(r"<li>\s*<div class=\"player-row\">(.*?)</li>", part, re.S):
        m = re.search(r'href="players/(\d+)/([^"]+)"', li)
        if not m:
            continue
        pos = re.search(r"data-position='(\d)'", li)
        avg = re.search(r'<div class="avg[^"]*">\s*([-\d.,]+)\s*</div>', li)
        st = re.search(r'<div class="streak">(.*?)</div>', li, re.S)
        streak = [_num(x) for x in re.findall(r"<span[^>]*>\s*([^<]*?)\s*</span>", st.group(1))] if st else []
        out.append({"id": m.group(1), "name": m.group(2).replace("-", " "), "pos": int(pos.group(1)) if pos else None,
                    "avg": _num(avg.group(1)) if avg else None, "streak": [x for x in streak if x is not None]})
    return out


def rosters(force=False):
    """{slug de l'equip: [jugadors]} de tots els equips de LaLiga 2 al Mister."""
    st = load_json("mister_rosters.json", {})
    if not force and st.get("at") and dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(st["at"]) < dt.timedelta(hours=TTL_H) \
            and len(st.get("teams") or {}) >= 18:
        return st["teams"]
    from bot.misterapi import MisterAPI
    api = MisterAPI().login()
    api.community(QUIQUE)
    todo, seen, teams = [], set(), {}
    for path in ("/team", "/market", "/standings", "/feed"):
        try:
            todo += re.findall(r'href="(teams/\d+/[a-z0-9-]+)"', api.page(path))
        except Exception:
            pass
    todo += [f"teams/{k}/{v}" for k, v in load_json("mister_teams.json", {}).items()]
    while todo and len(seen) < 40:
        path = todo.pop(0)
        if path in seen:
            continue
        seen.add(path)
        try:
            html = api.page("/" + path)
        except Exception:
            continue
        r = parse_roster(html)
        if r:
            teams[path.split("/")[-1]] = r
        todo += [p for p in re.findall(r'href="(teams/\d+/[a-z0-9-]+)"', html) if p not in seen]
    save_json("mister_rosters.json", {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "teams": teams})
    print(f"::notice title=PS estimat::plantilles del Mister: {len(teams)} equips")
    return teams


def ff_points(comp):
    """Mitjana de punts Fantasy✨ (el joc de futbolfantasy.com) de cada jugador: analytics «Puntos por jugador»."""
    import requests
    H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
    key = f"ff_points_{comp}.json"
    st = load_json(key, {})
    if st.get("at") and dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(st["at"]) < dt.timedelta(hours=TTL_H) and st.get("players"):
        return st["players"]
    url = f"https://www.futbolfantasy.com/analytics/{comp + '/' if comp != 'laliga' else ''}estadisticas-puntos/2027?puntuacion=futbolfantasy-rpg"
    h = requests.get(url, headers=H, timeout=60).text
    out = []
    for m in re.finditer(r'<tr data-name="([^"]+)"\s+data-posicion="([^"]*)"\s+data-equipo="(\d+)"[^>]*>(.*?)</tr>', h, re.S):
        row = m.group(4)
        team = re.search(r'<div class="player-equipo">.*?<span>([^<]+)</span>', row, re.S)
        c = {a: (b, cc, d) for a, b, cc, d in re.findall(
            r'data-value="([^"]+)"[^>]*data-total="([^"]*)"[^>]*data-casa="([^"]*)"[^>]*data-fuera="([^"]*)"', row)}
        f = lambda k, i: _num(c[k][i]) if k in c else None
        # columna 23 = Fantasy✨ (la 24 és LaLiga Fantasy Oficial)
        out.append({"name": m.group(1), "pos": m.group(2), "team": team.group(1) if team else "", "pj": f("partidos", 0), "avg": f("23-totalPorPartido", 0)})
    if out:
        save_json(key, {"at": dt.datetime.now(dt.timezone.utc).isoformat(), "players": out})
    return out


def _lsq(X, y):
    n = len(X[0])
    A = [[sum(r[i] * r[j] for r in X) for j in range(n)] for i in range(n)]
    b = [sum(r[i] * t for r, t in zip(X, y)) for i in range(n)]
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(A[k][i]))
        A[i], A[p], b[i], b[p] = A[p], A[i], b[p], b[i]
        if abs(A[i][i]) < 1e-9:
            return None
        for k in range(i + 1, n):
            f = A[k][i] / A[i][i]
            for j in range(i, n):
                A[k][j] -= f * A[i][j]
            b[k] -= f * b[i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (b[i] - sum(A[i][j] * x[j] for j in range(i + 1, n))) / A[i][i]
    return x


def fill(sidata, source="mister", comp="laliga2", log=print):
    """Posa un PS estimat (p["ps"], p["ps_est"] = True) als jugadors de SorareInside sense PS. Retorna sidata.
    source = "mister" (mitjana de punts del Mister, per al Mister) o "ff" (mitjana de Fantasy✨, per a futbolfantasy.com):
    cada joc amb els seus punts, perquè puntuen diferent (el David, 6/11).
    Model (provat el 6/11 amb 94–109 jugadors de Segona que tenen totes dues dades): el PS de SorareInside gairebé no
    depèn del % de titular (correlació 0,16: és el que faria si juga), sí de la mitjana de la temporada i de si juga a
    casa (+4,7). PS ≈ a + b·mitjana + c·casa, ajustat cada vegada amb els jugadors que tenen PS real. La ratxa dels
    últims partits i un factor per equip no milloraven la previsió."""
    from bot.ff import name_score, team_score
    try:
        if source == "ff":
            P = _MEMO.get("ff" + comp) or ff_points(comp)
            _MEMO["ff" + comp] = P
            pool = lambda t: [q for q in P if team_score(q["team"], t) > 0]
        else:
            R = _MEMO.get("r") or rosters()
            _MEMO["r"] = R

            def pool(t):
                slug = max(R, key=lambda s_: team_score(s_.replace("-", " "), t), default=None)
                return R[slug] if slug and team_score(slug.replace("-", " "), t) > 0 else []
    except Exception as e:
        print(f"::warning title=PS estimat::sense punts ({source}): {str(e)[:200]}")
        return sidata
    items = []
    for idx, t in enumerate(sidata.get("_order", [])):
        rows = sidata.get(t)
        if not isinstance(rows, list):
            continue
        home = 1 if idx % 2 == 0 else 0  # l'ordre de SorareInside és local, visitant, local, visitant…
        cand = pool(t)
        for r in rows:
            for p in r:
                best = max(cand, key=lambda q: name_score(p.get("name") or "", q["name"]), default=None)
                if best and name_score(p.get("name") or "", best["name"]) >= 75 and best.get("avg") is not None:
                    items.append((p, best["avg"], home, t))
    known = [(x, h, p["ps"]) for p, x, h, _ in items if p.get("ps") is not None and not p.get("ps_est")]
    if len(known) < 20:
        log(f"PS estimat ({source}): només {len(known)} jugadors amb les dues dades, no estimo")
        return sidata
    co = _lsq([[1, x, h] for x, h, _ in known], [y for _, _, y in known])
    if not co:
        return sidata
    a, b, c = co
    b = max(0.0, b)
    ys = [y for _, _, y in known]
    pred = [a + b * x + c * h for x, h, _ in known]
    my = statistics.mean(ys)
    r2 = 1 - sum((p_ - y) ** 2 for p_, y in zip(pred, ys)) / (sum((y - my) ** 2 for y in ys) or 1)
    lo, hi = min(ys), max(ys)
    done = []
    for p, x, h, t in items:
        if p.get("ps") is None:
            p["ps"] = int(round(min(hi, max(lo, a + b * x + c * h))))
            p["ps_est"] = True
            done.append(f"{p['name']} ({t}) ≈{p['ps']}")
    msg = (f"PS estimat ({'Mister' if source == 'mister' else 'Fantasy✨'}, {comp}): PS = {a:.1f} + {b:.2f}·mitjana + {c:.1f} a casa "
           f"(amb {len(known)} jugadors, R² {r2:.2f}); {len(done)} estimats: " + ", ".join(done[:60]))
    print("::notice title=PS estimat::" + msg[:3500])
    return sidata


if __name__ == "__main__":
    r = rosters(force=True)
    for k, v in list(r.items())[:3]:
        print(f"::notice title=plantilla {k}::" + ", ".join(f"{p['name']} {p['avg']} {p['streak']}" for p in v[:12]))
