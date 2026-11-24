"""Regles i cartes de les competicions European Contenders (24/11)."""
import json
from bot.sorare import gql, token
from bot import sorarelineup as L
Q = """query($s: String!) { so5 { so5Leaderboard(slug: $s) { slug displayName mainRarityType
  engineConfiguration { lineup positions averageScores sameActiveClub captain scarcity activeClubs player season }
  displayedTypedRules { key } eligibleCardsCountByPosition { position totalCount usedCardsCount } } } }"""
out = []
for s in ("football-24-27-nov-2026-special-weekly-european-contenders-division-1",
          "football-24-27-nov-2026-special-weekly-european-contenders-division-2"):
    lb = gql(Q, {"s": s}, token=token())["so5"]["so5Leaderboard"]
    out.append(json.dumps(lb, ensure_ascii=False)[:1800])
    try:
        cs = L.cards(lb, floor=2000, rarities=L.ARENA_RAR if lb["mainRarityType"].lower() == "limited" else None)
        out.append("cartes: " + ", ".join(f"{q['name']} ({q['pos'][:3]}, {80 - 10 * q['tier']}%, {q['grade']}, {q['club']})" for q in cs)[:1800])
    except Exception as e:
        out.append("cards error " + str(e)[:300])
    out.append(" | ".join(L.LOG[-3:]))
print("::notice title=probe12::" + " ¶ ".join(out)[:4000])
