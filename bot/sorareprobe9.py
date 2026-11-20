"""Diagnosi (20/11): Arenes de la jornada (noms, essència, regles)."""
from bot.sorare import gql, token
Q = """query { so5 { so5Fixture(sport: FOOTBALL, type: UPCOMING, eventType: CLASSIC) { gameWeek
  so5Leaderboards { slug displayName isArena mainRarityType rulesSummary format { title entryItem { ... on So5CardShardsEntryItem { quantity rarity } } } } } } }"""
fx = gql(Q, token=token())["so5"]["so5Fixture"]
rows = [f"{l['displayName']} [{l['format']['title']}] {l['slug']} · {(l['format'].get('entryItem') or {}).get('quantity')} {(l['format'].get('entryItem') or {}).get('rarity')} · {(l.get('rulesSummary') or '')[:160]}"
        for l in fx["so5Leaderboards"] if l["isArena"]]
print("::notice title=Arenes GW%s::" % fx["gameWeek"] + " ¶ ".join(rows))
