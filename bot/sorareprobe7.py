"""Diagnosi (20/11): alineacions del tauler personal del Set NBA amb els punts de cada carta."""
import json
from bot.sorare import gql, token
from bot.sorareset import STEP
for m in ("CAREER", "SQUAD"):
    d = gql(STEP, {"sp": "NBA", "m": m}, token=token())["currentUser"]["setBoard"]
    st = (d or {}).get("myCurrentStep") or {}
    out = [f"{m} nivell {st.get('level')} {st.get('state')} objectiu {st.get('target')}"]
    for l in st.get("myLineups") or []:
        out.append(f"alineació {l.get('aasmState')} {l.get('score')}: " + ", ".join(
            f"{a['anyPlayer']['displayName']} {a.get('score')} ({(a.get('game') or {}).get('date')}, {(a.get('game') or {}).get('id')})"
            for a in l.get("taskAppearances") or [] if a))
    print("::notice title=Set NBA " + m + "::" + " ¶ ".join(out))
from bot.sorareset import bench
st = gql(STEP, {"sp": "NBA", "m": "CAREER"}, token=token())["currentUser"]["setBoard"]["myCurrentStep"]
names = {a["anyPlayer"]["slug"] for l in st.get("myLineups") or [] for a in l.get("taskAppearances") or [] if a}
rows = []
for n in bench(st["id"], used=True):
    p = n["anyPlayer"]
    if p["slug"] in names:
        g = (n.get("eligiblePlayerGameScores") or [{}])[0] or {}
        rows.append(f"{p['displayName']} prev {g.get('projectedScore')} lesions {len(p.get('activeInjuries') or [])} {p.get('gameplayTierStars')}★ {(g.get('anyGame') or {}).get('date')}")
print("::notice title=previsions::" + " ¶ ".join(sorted(rows)))
