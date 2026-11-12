"""Diagnosi: cartes repetides d'un jugador al banc del Set de futbol (stackedCardsCount)."""
import sys
from bot.sorare import gql, token
from bot.sorarefset import gql_step
Q = """query($st: String!, $f: BenchFilterInput!) { currentUser { step(id: $st) { myFilteredBench(filters: $f, first: 100) {
  nodes { ... on ComposeTeamBenchCard { stackedCardsCount anyCard { slug xp } anyPlayer { slug displayName } } } } } } }"""
who = (sys.argv[2] if len(sys.argv) > 2 else "livakovic").lower()
st = gql_step({"m": "CAREER"})["currentUser"]["setBoard"]["myCurrentStep"]
for f in ({"includeUsed": True}, {}, {"positions": ["Goalkeeper"], "includeUsed": True}):
    ns = gql(Q, {"st": st["id"], "f": f}, token=token())["currentUser"]["step"]["myFilteredBench"]["nodes"]
    for n in ns:
        if n and who in n["anyPlayer"]["slug"]:
            print(f"::notice title=probe3 {f}::{n['anyPlayer']['displayName']} {n['anyCard']['slug']} xp {n['anyCard']['xp']} stacked {n.get('stackedCardsCount')}")
