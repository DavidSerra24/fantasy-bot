"""Diagnosi: els punts Fantasy✨ de LaLiga 2 a analytics estan al dia?"""
from collections import Counter

from bot import psest

psest.TTL_H = 0
P = psest.ff_points("laliga2")
pj = Counter(int(p["pj"] or 0) for p in P)
print("::notice title=partits jugats::" + ", ".join(f"{k}: {v}" for k, v in sorted(pj.items(), reverse=True)))
top = sorted(P, key=lambda p: -(p["pj"] or 0))[:10]
print("::notice title=mes partits::" + ", ".join(f"{p['name']} ({p['team']}) {p['pj']:.0f} pj, {p['avg']}" for p in top))
