"""Diagnosi (20/11): per què un jugador del Set NBA va fer 0 punts (estat i últims partits)."""
import json, re, sys
from bot.sorare import gql, token
from bot.web import load_json
who = [w.lower() for w in (sys.argv[2:] or ["kuzma", "edey"])]
txt = json.dumps(load_json("digest.json", {}), ensure_ascii=False)
slugs = set()
for w in who:
    slugs |= set(re.findall(r'"([a-z0-9-]*' + w + r'[a-z0-9-]*)"', txt))
for w in who:  # fragment del resum
    i = txt.lower().find(w)
    if i >= 0:
        print(f"::notice title=resum {w}::" + txt[max(0, i - 700):i + 300])
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
