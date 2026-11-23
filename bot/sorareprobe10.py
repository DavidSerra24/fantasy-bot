"""Diagnosi (23/11): on s'està fent servir una carta (activeTaskAppearances, usedIn)."""
import json, sys
from bot.sorare import gql, token
from bot.sorarefset import gql_step
slug = sys.argv[2] if len(sys.argv) > 2 else "senne-lammens-2026-common-eeb20461-c2f1-4269-b873-4c723eeeafb4"
st = gql_step({"m": "CAREER"})["currentUser"]["setBoard"]["myCurrentStep"]
Q = """query($s: String!, $t: ID) { anyCard(slug: $s) { slug activeTaskAppearances { __typename locked task { __typename id } }
  u0: usedIn { __typename slug } u1: usedIn(taskId: $t) { __typename slug } } }"""
print("::notice title=carta::" + json.dumps(gql(Q, {"s": slug, "t": st["id"]}, token=token()), ensure_ascii=False)[:2500])
