"""Diagnosi (23/11): on s'està fent servir una carta (activeTaskAppearances)."""
import json, sys
from bot.sorare import gql, token
slug = sys.argv[2] if len(sys.argv) > 2 else "senne-lammens-2026-common-eeb20461-c2f1-4269-b873-4c723eeeafb4"
Q = """query($s: String!) { anyCard(slug: $s) { slug activeTaskAppearances { __typename locked game { date }
  task { __typename id ... on TaskInterface { aasmState } } } } }"""
print("::notice title=carta::" + json.dumps(gql(Q, {"s": slug}, token=token()), ensure_ascii=False)[:2500])
