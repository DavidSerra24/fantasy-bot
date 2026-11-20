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
