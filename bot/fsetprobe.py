"""Diagnosi (6/11): estat del pas actual dels taulers del Set de futbol (per què no es reclama)."""
import json

from bot.sorare import gql, token

Q = """query($m: BoardMode!) { currentUser { setBoard(mode: $m, sport: FOOTBALL) { id title
  myCurrentStep { __typename id level state target
    ... on CareerStep { maxLineupsCount remainingLineupsCount pendingLineupsCount lockedLineupsCount
      myTask { id aasmState progress completedAt claimableAt } }
    myLineups { ... on TaskLineup { id aasmState score hasLiveGames } } } } } }"""
for m in ("CAREER", "SQUAD"):
    try:
        d = gql(Q, {"m": m}, token=token())
        print(f"::notice title=fset {m}::" + json.dumps(d, ensure_ascii=False)[:3000])
    except Exception as e:
        print(f"::notice title=fset {m} err::{str(e)[:1500]}")
