"""Diagnosi (només lectura): porters de SorareInside desats per a un joc de FutbolFantasy (state/si_ff_<slug>.json)."""
import json
import sys

slug = sys.argv[1] if len(sys.argv) > 1 else "champions"
d = json.load(open(f"state/si_ff_{slug}.json", encoding="utf-8"))
out = []
for t in d.get("_order", []):
    rows = d.get(t)
    if isinstance(rows, list) and rows and rows[0]:
        gk = rows[0][0]
        out.append(f"{t}: {gk.get('name')} {gk.get('pct')}% {gk.get('ps')} PS (subs {[s['name'] for s in gk.get('subs') or []]})")
print("::notice title=porters::" + " ¶ ".join(out)[:3900])
