"""Prova: competicions de la jornada en joc (LIVE) amb tancament propi (All Star de la GW729)."""
from bot.sorare import gql, token

for typ in ("LIVE", "UPCOMING"):
    try:
        d = gql("""query($t: So5State!) { so5 { so5Fixture(sport: FOOTBALL, type: $t, eventType: CLASSIC) { slug gameWeek cutOffDate
            so5Leaderboards { displayName slug mainRarityType isArena cutOffDate canCompose { value reason } } } } }""", {"t": typ}, token=token())
        fx = d["so5"]["so5Fixture"]
        print(f"::notice title={typ}::{fx['slug']} GW{fx['gameWeek']} {fx['cutOffDate']} ¶ " + " ¶ ".join(
            f"{l['displayName']} {l['mainRarityType']} tanca {l.get('cutOffDate')} compose={l['canCompose']['value']}" for l in fx["so5Leaderboards"] if not l["isArena"])[:3800])
    except Exception as e:
        print(f"::notice title={typ} ERR::" + str(e)[:800])
