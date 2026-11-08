"""Diagnosi (8/11): estat de les missions diàries del Set (NBA i futbol)."""
import json
from bot.sorare import gql, token
Q = """query($sp: Sport!) { currentUser { setPlayTasks(first: 30, sport: $sp) { __typename ... on TaskInterface { id title rarity aasmState expired completedAt claimableAt progress } } } }"""
for sp in ("NBA", "FOOTBALL"):
    try:
        d = gql(Q, {"sp": sp}, token=token())
        print(f"::notice title=set tasks {sp}::" + json.dumps(d, ensure_ascii=False)[:3500])
    except Exception as e:
        print(f"::notice title=set tasks {sp} err::{str(e)[:1500]}")
