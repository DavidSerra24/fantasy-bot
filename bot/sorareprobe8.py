"""Diagnosi (20/11): per què un jugador del Set NBA va fer 0 punts (estat i últims partits)."""
import json, re, sys
from bot.sorare import gql, token
from bot.web import load_json
who = [w.lower() for w in (sys.argv[2:] or ["kuzma", "edey"])]
txt = json.dumps(load_json("digest.json", {}), ensure_ascii=False)
slugs = set()
for w in who:
    slugs |= set(re.findall(r'"([a-z0-9-]*' + w + r'[a-z0-9-]*)"', txt))
try:  # els slugs surten del banc del tauler personal (totes les meves cartes, també sense partit o no disponibles)
    from bot.sorareset import STEP, BENCH
    st = gql(STEP, {"sp": "NBA", "m": "CAREER"}, token=token())["currentUser"]["setBoard"]["myCurrentStep"]
    after, tot = None, 0
    for _ in range(20):
        d = gql(BENCH, {"st": st["id"], "after": after, "f": {"includeUsed": True, "includeNoGame": True, "includeUnavailablePlayers": True}}, token=token())["currentUser"]["step"]["myFilteredBench"]
        for n in d["nodes"]:
            tot += 1
            if n and any(w in n["anyPlayer"]["displayName"].lower() for w in who):
                slugs.add(n["anyPlayer"]["slug"])
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    print(f"::notice title=banc::{tot} cartes")
except Exception as e:
    print("::notice title=banc::" + str(e)[:400])
for w in who:  # fragment del resum
    i = txt.lower().find(w)
    if i >= 0:
        pass
Q = """query($s: String!) { anyPlayer(slug: $s) { displayName ... on NBAPlayer { activeInjuries { id status kind details startDate expectedEndDate }
  activeClub { name } }
  anyGameStats(last: 3) { ... on PlayerGameStatsBasketball { minsPlayed points rebounds assists playedInGame onGameSheet
    projectedPoints projectedMinsPlayed anyGame { date } } } } }"""
for s in sorted(slugs):
    try:
        print(f"::notice title={s}::" + json.dumps(gql(Q, {"s": s}, token=token()), ensure_ascii=False)[:2500])
    except Exception as e:
        print(f"::notice title={s}::{str(e)[:500]}")
if not slugs:
    print("::notice title=slugs::cap slug trobat al resum")
