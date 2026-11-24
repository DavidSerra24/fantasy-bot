"""Llista les competicions Classic (LIVE i UPCOMING): nom, raresa, tancament, si es pot fer i quantes alineacions tinc."""
from bot.sorare import gql, token
Q = """query($t: So5State) { so5 { so5Fixture(sport: FOOTBALL, type: $t, eventType: CLASSIC) { slug gameWeek cutOffDate
  so5Leaderboards { slug displayName mainRarityType isArena cutOffDate canCompose { value } } mySo5Lineups { so5Leaderboard { slug } } } } }"""
for t in ("LIVE", "UPCOMING"):
    try:
        fx = gql(Q, {"t": t}, token=token())["so5"]["so5Fixture"]
    except Exception as e:
        print(t, "error", str(e)[:300]); continue
    if not fx:
        print(t, "cap"); continue
    mine = {}
    for l in fx["mySo5Lineups"]:
        mine[l["so5Leaderboard"]["slug"]] = mine.get(l["so5Leaderboard"]["slug"], 0) + 1
    out = [f"{t} GW{fx['gameWeek']} tanca {fx['cutOffDate']}"]
    for l in fx["so5Leaderboards"]:
        if l["isArena"]:
            continue
        out.append(f"{l['slug']} · {l['displayName']} [{l['mainRarityType']}] tanca {l.get('cutOffDate')} pot={(l.get('canCompose') or {}).get('value')} meves={mine.get(l['slug'], 0)}")
    print("::notice title=probe11::" + " ¶ ".join(out)[:3900])
