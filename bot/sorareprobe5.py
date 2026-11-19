"""Diagnosi (19/11): cartes elegibles d'una competició In Season (temporada, % de titular, partit)."""
import sys
from bot.sorare import gql, token
Q = """query($slug: String!, $r: RangeInput, $pos: [Position!], $after: String) { so5 { so5Leaderboard(slug: $slug) {
  myBench(first: 50, after: $after, includeUsed: true, includeNoGame: true, inSeasonEligible: true, starterOddsBasisPointsRange: $r, positions: $pos) { pageInfo { hasNextPage endCursor } nodes {
    ... on ComposeTeamBenchCard { position avg10: averageScore(type: LAST_TEN_PLAYED_SO5_AVERAGE_SCORE)
      anyCard { slug rarityTyped inSeasonEligible } anyPlayer { displayName activeClub { name } }
      eligiblePlayerGameScores(so5LeaderboardSlug: $slug) { projection { grade score } anyGame { date homeTeam { name } awayTeam { name } } } } } } } } }"""
slugs = sys.argv[2:] or ["football-20-24-nov-2026-seasonal-contenders-in_season_contenders_limited"]
for slug in slugs:
    seen = {}
    for lo in (None, 9000, 8000, 7000, 6000, 5000, 4000, 3000, 2000, 1000):
        for pos in (None, ["Goalkeeper"]):
            r = None if lo is None else {"min": lo, "max": 10000 if lo == 9000 else lo + 999}
            after = None
            for _ in range(10):
                d = gql(Q, {"slug": slug, "r": r, "pos": pos, "after": after}, token=token())["so5"]["so5Leaderboard"]["myBench"]
                for n in d["nodes"]:
                    if not n:
                        continue
                    k = n["anyCard"]["slug"]
                    if k not in seen:
                        seen[k] = [n, "?"]
                    if lo is not None and seen[k][1] == "?":
                        seen[k][1] = f"{lo // 100}%"
                if not d["pageInfo"]["hasNextPage"]:
                    break
                after = d["pageInfo"]["endCursor"]
    rows = []
    for k, (n, pct) in seen.items():
        g = (n.get("eligiblePlayerGameScores") or [{}])[0] if n.get("eligiblePlayerGameScores") else {}
        gm = g.get("anyGame") or {}
        pr = g.get("projection") or {}
        rows.append(f"{n['position'][:3]} {n['anyPlayer']['displayName']} ({(n['anyPlayer'].get('activeClub') or {}).get('name')}) "
                    f"{'IN' if n['anyCard']['inSeasonEligible'] else 'classic'} {n['anyCard']['rarityTyped']} {pct} "
                    f"{pr.get('grade') or '-'} L10 {round(n['avg10'] or 0)} · {(gm.get('homeTeam') or {}).get('name')}-{(gm.get('awayTeam') or {}).get('name')} {gm.get('date')}")
    print(f"::notice title={slug}::" + " ¶ ".join(sorted(rows)))
