"""Sorare: es pot fer alguna alineació In Season o del tauler Pro? (decisió del David, 20/11)

Un cop per Gameweek (3 h abans del tancament) es mira, per a cada competició In Season Limited de la jornada i cada
tauler Pro (Hot Streak per lliga), si hi ha 5 jugadors del 80–90% (filtre `starterOddsBasisPointsRange` ≥ 8000) que
facin una alineació vàlida: POR, DEF, MIG, DAV i Extra (jugador de camp), amb com a mínim 4 cartes In Season.
Només avisa per Telegram quan n'hi ha alguna de possible.

`play` (decisió del David, 20/11: «no ha de preguntar, la prioritat és fer primer el tauler Pro, després In Season i
després la resta»): es crida al principi de cada passada de Sorare Pro (sorarelineup.run) i fa les alineacions del tauler
Pro i de les competicions In Season que es puguin fer; les seves cartes ja no van a les Classic."""
import itertools
import sys

from bot.sorare import gql, token
from bot.web import load_json, save_json

FIX = """query { so5 { so5Fixture(sport: FOOTBALL, type: UPCOMING, eventType: CLASSIC) { slug gameWeek cutOffDate
  so5Leaderboards { slug displayName isArena seasonality mainRarityType format { title } } } } }"""
LB_BENCH = """query($slug: String!, $r: RangeInput, $pos: [Position!], $after: String) { so5 { so5Leaderboard(slug: $slug) {
  myBench(first: 50, after: $after, includeUsed: true, starterOddsBasisPointsRange: $r, positions: $pos) {
    pageInfo { hasNextPage endCursor } nodes { ... on ComposeTeamBenchCard { position
      anyCard { slug inSeasonEligible } anyPlayer { slug displayName } } } } } } }"""
BOARDS = """query { currentUser { boards(mode: CAREER, sport: FOOTBALL) { title description
  myCurrentStep { __typename id ... on CareerProStep { level target state } } } } }"""
STEP_BENCH = """query($st: String!, $f: BenchFilterInput!, $after: String) { currentUser { step(id: $st) {
  myFilteredBench(filters: $f, first: 50, after: $after) { pageInfo { hasNextPage endCursor } nodes {
    ... on ComposeTeamBenchCard { position anyCard { slug inSeasonEligible } anyPlayer { slug displayName } } } } } } }"""
R80 = {"min": 8000, "max": 10000}
if len(sys.argv) > 2 and sys.argv[1] == "inseason" and sys.argv[2].isdigit():  # prova: «inseason 3000» (llindar més baix)
    R80 = {"min": int(sys.argv[2]), "max": 10000}


def _pages(fetch):
    out, after = [], None
    for _ in range(10):
        d = fetch(after)
        out += [n for n in d["nodes"] if n]
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    return out


def lb_cards(slug):
    tk = token()
    ns = []
    for pos in (None, ["Goalkeeper"]):  # sense filtre de posició surten només els de camp
        ns += _pages(lambda a: gql(LB_BENCH, {"slug": slug, "r": R80, "pos": pos, "after": a}, token=tk)["so5"]["so5Leaderboard"]["myBench"])
    return ns


def step_cards(step_id):
    tk = token()
    ns = []
    for pos in (None, ["Goalkeeper"]):
        f = {"includeUsed": True, "starterOddsBasisPointsRange": R80}
        if pos:
            f["positions"] = pos
        ns += _pages(lambda a: gql(STEP_BENCH, {"st": step_id, "f": f, "after": a}, token=tk)["currentUser"]["step"]["myFilteredBench"])
    return ns


def best(nodes):
    """Millor alineació possible (POR, DEF, MIG, DAV, Extra) amb jugadors diferents i ≥4 In Season; None si no n'hi ha."""
    per = {}
    for n in nodes:  # un per jugador: millor la carta In Season
        p = n["anyPlayer"]["slug"]
        if p not in per or (n["anyCard"]["inSeasonEligible"] and not per[p]["anyCard"]["inSeasonEligible"]):
            per[p] = n
    ps = list(per.values())
    pos = lambda n, k: (n.get("position") or "")[:3].lower() == k
    gk = [n for n in ps if pos(n, "goa")]
    de = [n for n in ps if pos(n, "def")]
    mi = [n for n in ps if pos(n, "mid")]
    fo = [n for n in ps if pos(n, "for")]
    field = de + mi + fo
    top = None
    for g, d, m, f in itertools.product(gk, de, mi, fo):
        for e in field:
            team = [g, d, m, f, e]
            if len({x["anyPlayer"]["slug"] for x in team}) < 5:
                continue
            ins = sum(1 for x in team if x["anyCard"]["inSeasonEligible"])
            if ins >= 4 and (top is None or ins > top[0]):
                top = (ins, team)
                if ins == 5:
                    return top
    return top


def summary(nodes):
    ins = sorted({n["anyPlayer"]["displayName"] + f" ({(n.get('position') or '')[:3]})" for n in nodes if n["anyCard"]["inSeasonEligible"]})
    return f"{len(ins)} In Season del 80–90%" + (": " + ", ".join(ins) if ins else "")


def run(dry=False):
    fx = gql(FIX, token=token())["so5"]["so5Fixture"]
    st = load_json("sorare_inseason.json", {})
    if not dry and st.get("gw") == fx["slug"]:
        print("::notice title=In Season / Pro::ja revisat aquesta jornada"); return
    found, lines = [], []
    leagues = set()
    for l in fx["so5Leaderboards"]:
        if l["isArena"] or l["seasonality"] != "IN_SEASON" or l["mainRarityType"] != "limited":
            continue
        try:
            ns = lb_cards(l["slug"])
        except Exception as e:
            lines.append(f"{l['displayName']}: error {type(e).__name__}"); continue
        leagues.add(l["displayName"].split(" – ")[0].lower())
        b = best(ns)
        lines.append(f"{l['format']['title']} {l['displayName']}: {summary(ns)}")
        if b:
            found.append(f"🟣 {l['format']['title']} {l['displayName']}: " + ", ".join(x["anyPlayer"]["displayName"] for x in b[1]) + f" ({b[0]} In Season)")
    try:
        boards = gql(BOARDS, token=token())["currentUser"]["boards"] or []
    except Exception as e:
        boards = []
        lines.append(f"taulers Pro: error {type(e).__name__}")
    for bd in boards:
        s = bd.get("myCurrentStep") or {}
        if s.get("__typename") != "CareerProStep" or s.get("state") not in ("PLAYABLE", None):
            continue
        try:
            ns = step_cards(s["id"])
        except Exception as e:
            lines.append(f"Pro {bd['title']}: error {type(e).__name__}"); continue
        b = best(ns)
        lines.append(f"Pro {bd['title']} (nivell {s.get('level')}, objectiu {s.get('target')}): {summary(ns)}")
        if b:
            found.append(f"🔥 Pro {bd['title']} (nivell {s.get('level')}, objectiu {s.get('target')}): "
                         + ", ".join(x["anyPlayer"]["displayName"] for x in b[1]) + f" ({b[0]} In Season)")
    print(f"::notice title=In Season / Pro GW{fx['gameWeek']}::" + " ¶ ".join(lines))
    if found and not dry:
        from bot.notify import telegram
        telegram(f"🟣 Sorare GW{fx['gameWeek']}: ja pots fer alineacions In Season / Pro amb 5 jugadors del 80–90% "
                 "(mínim 4 In Season):\n" + "\n".join(found) + "\nVols que el bot les faci?")
    elif found:
        print("::notice title=possibles::" + " ¶ ".join(found))
    if not dry:
        save_json("sorare_inseason.json", {"gw": fx["slug"], "found": found})


if __name__ == "__main__":
    run(dry="--dry" in sys.argv)


# ---------------------------------------------------------------- jugar (20/11)
GRADE = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0}
GAMES_LB = """query($slug: String!, $r: RangeInput, $pos: [Position!], $after: String) { so5 { so5Leaderboard(slug: $slug) {
  myBench(first: 50, after: $after, includeUsed: true, starterOddsBasisPointsRange: $r, positions: $pos) {
    pageInfo { hasNextPage endCursor } nodes { ... on ComposeTeamBenchCard { position
      anyCard { slug inSeasonEligible xp } anyPlayer { slug displayName activeClub { name } }
      eligiblePlayerGameScores(so5LeaderboardSlug: $slug) { projection { grade score } anyGame { id date homeTeam { name } awayTeam { name } } } } } } } } }"""
GAMES_STEP = """query($st: String!, $f: BenchFilterInput!, $after: String) { currentUser { step(id: $st) {
  myFilteredBench(filters: $f, first: 50, after: $after) { pageInfo { hasNextPage endCursor } nodes {
    ... on ComposeTeamBenchCard { position anyCard { slug inSeasonEligible xp } anyPlayer { slug displayName activeClub { name } }
      eligiblePlayerGameScores(stepId: $st) { projection { grade score } anyGame { id date homeTeam { name } awayTeam { name } } } } } } } } }"""
BOARDS_FULL = """query { currentUser { boards(mode: CAREER, sport: FOOTBALL) { title description
  myCurrentStep { __typename id ... on CareerProStep { level target state
    myLineups { __typename id ... on TaskLineup { taskAppearances { anyCard { slug } } } } } } } } }"""
FIX_FULL = """query { so5 { so5Fixture(sport: FOOTBALL, type: UPCOMING, eventType: CLASSIC) { slug gameWeek cutOffDate
  so5Leaderboards { id slug displayName isArena seasonality mainRarityType format { title } }
  mySo5Lineups { id so5Leaderboard { slug format { title } isArena } so5Appearances { anyCard { slug } } } } } }"""


def _cands(nodes, now):
    """Una entrada per carta: jugador, posició, In Season, partit (no començat), impacte i punts previstos."""
    import datetime as dt
    out = []
    for n in nodes:
        gs = [g for g in n.get("eligiblePlayerGameScores") or [] if g and g.get("anyGame")
              and dt.datetime.fromisoformat(g["anyGame"]["date"].replace("Z", "+00:00")) > now]
        if not gs:
            continue
        g = gs[0]
        gm = g["anyGame"]
        pr = g.get("projection") or {}
        out.append({"card": n["anyCard"]["slug"], "xp": n["anyCard"].get("xp") or 0, "ins": n["anyCard"]["inSeasonEligible"],
                    "player": n["anyPlayer"]["slug"], "name": n["anyPlayer"]["displayName"],
                    "club": (n["anyPlayer"].get("activeClub") or {}).get("name"), "pos": (n.get("position") or "")[:3].lower(),
                    "game": gm["id"], "teams": {(gm.get("homeTeam") or {}).get("name"), (gm.get("awayTeam") or {}).get("name")},
                    "grade": pr.get("grade"), "proj": pr.get("score") or 0})
    return out


def pick5(cands, taken):
    """Millor alineació POR, DEF, MIG, DAV, Extra amb ≥4 In Season: primer sense rivals, després per punts previstos."""
    per = {}
    for q in cands:
        if q["card"] in taken:
            continue
        k = (q["player"], q["ins"])
        if k not in per or q["xp"] > per[k]["xp"]:
            per[k] = q
    ps = sorted(per.values(), key=lambda q: (-GRADE.get(q["grade"], -1), -q["proj"]))[:40]
    by = {k: [q for q in ps if q["pos"] == k] for k in ("goa", "def", "mid", "for")}
    field = by["def"] + by["mid"] + by["for"]
    best_ = None
    for g, d, m, f in itertools.product(by["goa"], by["def"], by["mid"], by["for"]):
        for e in field:
            team = [g, d, m, f, e]
            if len({x["player"] for x in team}) < 5 or sum(x["ins"] for x in team) < 4:
                continue
            riv = sum(1 for a, b in itertools.combinations(team, 2) if a["game"] == b["game"] and a["club"] != b["club"])
            key = (riv == 0, sum(GRADE.get(x["grade"], 0) for x in team), sum(x["proj"] for x in team))
            if best_ is None or key > best_[0]:
                best_ = (key, team)
    if not best_:
        return None
    team = best_[1]
    cap = max(range(5), key=lambda i: (GRADE.get(team[i]["grade"], -1), team[i]["proj"], team[i]["pos"] != "goa", -i))
    return team, cap, not best_[0][0]


def _txt(team, cap):
    return ", ".join(f"{q['name']}{' ©' if i == cap else ''} ({q['grade'] or '?'}{', IS' if q['ins'] else ''})" for i, q in enumerate(team))


def play(dry=False):
    """Fa les alineacions del tauler Pro i de les In Season possibles. Torna (cartes fetes servir, línies d'informe)."""
    import datetime as dt
    from bot.sorare import gql as _g
    now = dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=2)
    tk = token()
    used, rep = set(), []
    fx = _g(FIX_FULL, token=tk)["so5"]["so5Fixture"]
    classic = [l for l in fx.get("mySo5Lineups") or [] if l["so5Leaderboard"]["format"]["title"] == "Classic" and not l["so5Leaderboard"]["isArena"]]

    def free_from_classic(cards_):
        """Una carta que encara és en una alineació Classic d'una passada anterior: s'esborra aquella alineació
        (la passada Classic que ve tot seguit la refà sense aquesta carta)."""
        from bot.sorarelineup import delete_lineup
        for l in list(classic):
            if cards_ & {a["anyCard"]["slug"] for a in l["so5Appearances"]}:
                delete_lineup(l["id"]); classic.remove(l)
                rep.append(f"   (he tret una alineació Classic que tenia aquestes cartes; es refà ara mateix)")

    # 1) tauler Pro
    try:
        boards = _g(BOARDS_FULL, token=tk)["currentUser"]["boards"] or []
    except Exception as e:
        boards = []
        rep.append(f"⚠️ Pro: no he pogut llegir els taulers ({type(e).__name__})")
    from bot.sorareset import UPSERT
    for bd in boards:
        st = bd.get("myCurrentStep") or {}
        if st.get("__typename") != "CareerProStep" or st.get("state") != "PLAYABLE":
            continue
        have = [l for l in st.get("myLineups") or [] if l.get("taskAppearances")]
        try:
            ns = []
            for pos in (None, ["Goalkeeper"]):
                f = {"includeUsed": True, "starterOddsBasisPointsRange": R80}
                if pos:
                    f["positions"] = pos
                ns += _pages(lambda a: _g(GAMES_STEP, {"st": st["id"], "f": f, "after": a}, token=tk)["currentUser"]["step"]["myFilteredBench"])
            r = pick5(_cands(ns, now), used)
        except Exception as e:
            rep.append(f"⚠️ Pro {bd['title']}: {type(e).__name__}: {str(e)[:150]}"); continue
        if not r:
            if have:  # ja n'hi ha una (p. ex. partits començats): es deixa
                used |= {a["anyCard"]["slug"] for a in have[0]["taskAppearances"] if a and a.get("anyCard")}
            continue
        team, cap, riv = r
        cards_ = {q["card"] for q in team}
        name = f"🔥 Pro {bd['title']} (nivell {st.get('level')}, objectiu {st.get('target')})"
        if have and {a["anyCard"]["slug"] for a in have[0]["taskAppearances"] if a and a.get("anyCard")} == cards_:
            rep.append(f"{name} sense canvis: {_txt(team, cap)}"); used |= cards_; continue
        if dry:
            rep.append(f"{name} (prova): {_txt(team, cap)}{' ⚔️' if riv else ''}"); used |= cards_; continue
        inp = {"stepId": st["id"], "appearances": [{"index": i, "cardSlug": q["card"], "gameId": q["game"].split(":")[-1], "captain": i == cap}
                                                   for i, q in enumerate(team)]}
        if have:
            inp["lineupId"] = have[0]["id"]
        for attempt in (1, 2):
            try:
                d = _g(UPSERT, {"input": inp}, token=tk)["upsertStepLineup"]
                if d.get("errors"):
                    raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
                rep.append(f"{name}: {_txt(team, cap)}{' ⚔️' if riv else ''}"); used |= cards_
                break
            except Exception as e:
                if attempt == 1 and "used" in str(e).lower():
                    free_from_classic(cards_); continue
                rep.append(f"❌ {name}: {str(e)[:200]}")
                break

    # 2) In Season (i Hot Streak de la jornada), Limited: tantes com es pugui (fins a 4 per competició)
    from bot.sorarelineup import SAVE, delete_lineup
    mine = fx.get("mySo5Lineups") or []
    for lb in fx["so5Leaderboards"]:
        if lb["isArena"] or lb["seasonality"] != "IN_SEASON" or lb["mainRarityType"] != "limited":
            continue
        have = [l for l in mine if l["so5Leaderboard"]["slug"] == lb["slug"]]
        try:
            ns = []
            for pos in (None, ["Goalkeeper"]):
                ns += _pages(lambda a: _g(GAMES_LB, {"slug": lb["slug"], "r": R80, "pos": pos, "after": a}, token=tk)["so5"]["so5Leaderboard"]["myBench"])
            cands = _cands(ns, now)
        except Exception as e:
            rep.append(f"⚠️ {lb['displayName']}: {type(e).__name__}: {str(e)[:150]}"); continue
        picks, players = [], set()
        while len(picks) < 4:
            r = pick5([q for q in cands if q["player"] not in players], used | {c for t, _, _ in picks for c in (q["card"] for q in t)})
            if not r:
                break
            picks.append(r)
            players |= {q["player"] for q in r[0]}
        want = [frozenset(q["card"] for q in t) for t, _, _ in picks]
        haves = [frozenset(a["anyCard"]["slug"] for a in l["so5Appearances"]) for l in have]
        title = f"🟣 {lb['format']['title']} {lb['displayName']}"
        if not picks:
            if have:
                rep.append(f"⚠️ {title}: ja no surt cap alineació amb ≥80% (n'hi ha {len(have)} de feta: la deixo)")
                used |= {c for h in haves for c in h}
            continue
        if dry:
            rep += [f"{title} #{i + 1} (prova): {_txt(t, c)}{' ⚔️' if rv else ''}" for i, (t, c, rv) in enumerate(picks)]
            used |= {c for w in want for c in w}
            continue
        for l, h in zip(have, haves):  # les que ja no són al pla s'esborren (primer, perquè les cartes quedin lliures)
            if h not in want:
                try:
                    delete_lineup(l["id"])
                except Exception as e:
                    rep.append(f"❌ {title}: no he pogut esborrar una alineació ({str(e)[:120]})")
        for i, (t, c, rv) in enumerate(picks):
            cs = frozenset(q["card"] for q in t)
            if cs in haves:
                rep.append(f"{title} #{i + 1} sense canvis: {_txt(t, c)}"); used |= cs; continue
            inp = {"so5LeaderboardId": lb["id"], "so5Appearances": [{"cardSlug": q["card"], "captain": j == c, "index": j} for j, q in enumerate(t)]}
            for attempt in (1, 2):
                try:
                    d = _g(SAVE, {"input": inp}, token=tk)["createOrUpdateSo5Lineup"]
                    if d.get("errors"):
                        raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
                    rep.append(f"{title} #{i + 1}: {_txt(t, c)}{' ⚔️' if rv else ''}"); used |= cs
                    break
                except Exception as e:
                    if attempt == 1 and "used" in str(e).lower():
                        free_from_classic(set(cs)); continue
                    rep.append(f"❌ {title} #{i + 1}: {str(e)[:200]}")
                    break
    return used, rep
