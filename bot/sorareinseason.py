"""Sorare: es pot fer alguna alineació In Season o del tauler Pro? (decisió del David, 20/11)

Un cop per Gameweek (3 h abans del tancament) es mira, per a cada competició In Season Limited de la jornada i cada
tauler Pro (Hot Streak per lliga), si hi ha 5 jugadors del 80–90% (filtre `starterOddsBasisPointsRange` ≥ 8000) que
facin una alineació vàlida: POR, DEF, MIG, DAV i Extra (jugador de camp), amb com a mínim 4 cartes In Season.
Només avisa per Telegram quan n'hi ha alguna de possible; no juga res."""
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
