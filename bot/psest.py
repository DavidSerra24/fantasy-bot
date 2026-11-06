"""PS estimat per als jugadors de Segona sense punts projectats a SorareInside (els que no tenen carta de Sorare).

Decisió del David (6/11): per al Mister (Quique) i FutbolFantasy (LaLiga 2). Els estimats competeixen igual que els reals.
- Base: la mitjana dels últims partits jugats al Mister (la ratxa de 5 de la fitxa de l'equip; si no n'hi ha, la
  mitjana de la temporada).
- Conversió a l'escala de SorareInside: recta PS ≈ a + b·base ajustada amb els jugadors que tenen totes dues dades.
- Ajust del partit: per a cada equip, quant està el PS real dels seus jugadors amb carta per sobre o per sota del que
  dona la recta aquella setmana (rival, casa/fora). Així l'estimat també puja o baixa cada setmana.
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


def _base(p):
    played = [x for x in p["streak"] if x is not None]
    if played:
        return statistics.mean(played)
    return p.get("avg")


def fill(sidata, log=print):
    """Posa un PS estimat (p["ps"], p["ps_est"] = True) als jugadors de SorareInside sense PS. Retorna sidata."""
    from bot.ff import name_score, team_score
    try:
        R = _MEMO.get("r") or rosters()
        _MEMO["r"] = R
    except Exception as e:
        print(f"::warning title=PS estimat::sense plantilles del Mister: {str(e)[:200]}")
        return sidata
    rows_by_team = {}
    for t in sidata.get("_order", []):
        rows = sidata.get(t)
        if not isinstance(rows, list):
            continue
        slug = max(R, key=lambda s: team_score(s, t), default=None)
        if not slug or team_score(slug, t) <= 0:
            continue
        roster = R[slug]
        lst = []
        for r in rows:
            for p in r:
                best = max(roster, key=lambda q: name_score(p.get("name") or "", q["name"]), default=None)
                if best and name_score(p.get("name") or "", best["name"]) >= 75:
                    b = _base(best)
                    if b is not None:
                        lst.append((p, b))
        rows_by_team[t] = lst
    pairs = [(b, p["ps"]) for lst in rows_by_team.values() for p, b in lst if p.get("ps") is not None and not p.get("ps_est")]
    if len(pairs) < 15:
        log(f"PS estimat: només {len(pairs)} jugadors amb les dues dades, no estimo")
        return sidata
    xs, ys = [x for x, _ in pairs], [y for _, y in pairs]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    vx = sum((x - mx) ** 2 for x in xs)
    b = max(0.5, sum((x - mx) * (y - my) for x, y in pairs) / vx) if vx else 1.0
    a = my - b * mx
    done = []
    for t, lst in rows_by_team.items():
        ratios = [p["ps"] / (a + b * x) for p, x in lst if p.get("ps") is not None and not p.get("ps_est") and a + b * x > 5]
        f = min(1.2, max(0.8, statistics.median(ratios))) if len(ratios) >= 2 else 1.0
        for p, x in lst:
            if p.get("ps") is None:
                p["ps"] = int(round(max(5.0, (a + b * x) * f)))
                p["ps_est"] = True
                done.append(f"{p['name']} ({t}) ≈{p['ps']}")
    msg = (f"PS estimat (Segona): recta PS = {a:.1f} + {b:.2f}·mitjana Mister (amb {len(pairs)} jugadors); "
           f"{len(done)} estimats: " + ", ".join(done[:60]))
    print("::notice title=PS estimat::" + msg[:3500])
    return sidata


if __name__ == "__main__":
    r = rosters(force=True)
    for k, v in list(r.items())[:3]:
        print(f"::notice title=plantilla {k}::" + ", ".join(f"{p['name']} {p['avg']} {p['streak']}" for p in v[:12]))
