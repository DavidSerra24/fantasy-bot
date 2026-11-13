"""Diagnosi: alineacions enviades a la jornada en joc (LIVE) i a la propera (UPCOMING)."""
from bot.sorare import gql, token
from bot.sorarelineup import FIXTURE, FIXTURE_LIVE
for name, q in (("LIVE", FIXTURE_LIVE), ("UPCOMING", FIXTURE)):
    try:
        fx = gql(q, token=token())["so5"]["so5Fixture"]
    except Exception as e:
        print(f"::warning title=now {name}::{e}"); continue
    if not fx:
        continue
    for l in fx.get("mySo5Lineups") or []:
        lb = l["so5Leaderboard"]
        print(f"::notice title=GW{fx.get('gameWeek')} {name}::{lb['displayName']} ({lb.get('mainRarityType')}{', Arena' if lb['isArena'] else ''}): "
              + ", ".join(a["anyPlayer"]["displayName"] + (" ©" if a["captain"] else "") for a in l["so5Appearances"]))
