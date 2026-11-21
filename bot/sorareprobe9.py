"""Diagnosi (21/11): Arenes Beginner i Rare de la jornada en joc i de la propera (nom, essència)."""
from bot.sorare import gql, token
Q = """query($t: So5State!) { so5 { so5Fixture(sport: FOOTBALL, type: $t, eventType: CLASSIC) { gameWeek cutOffDate
  so5Leaderboards { slug displayName isArena mainRarityType cutOffDate format { title entryItem { ... on So5CardShardsEntryItem { quantity rarity } } } } } } }"""
for t in ("LIVE", "UPCOMING"):
    try:
        fx = gql(Q, {"t": t}, token=token())["so5"]["so5Fixture"]
    except Exception as e:
        print(f"::notice title={t}::{str(e)[:300]}"); continue
    rows = sorted({f"{l['format']['title']} · {l['mainRarityType']} · {(l['format'].get('entryItem') or {}).get('quantity')} {(l['format'].get('entryItem') or {}).get('rarity')} · tanca {l['cutOffDate']} · {l['slug'].split('-seasonal-')[-1][:70]}"
                   for l in fx["so5Leaderboards"] if l["isArena"] and ("rare" in (l["mainRarityType"] or "").lower() or "eginner" in l["format"]["title"])})
    print(f"::notice title={t} GW{fx['gameWeek']}::" + " ¶ ".join(rows))
