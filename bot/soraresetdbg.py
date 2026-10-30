"""Diagnosi (només lectura): jugadors del banc del Set d'NBA amb partit avui i per què entren o no."""
import datetime as dt

from bot.sorare import gql, token
from bot.sorareset import STEP, bench

now = dt.datetime.now(dt.timezone.utc)
st = gql(STEP, {"sp": "NBA", "m": "CAREER"}, token=token())["currentUser"]["setBoard"]["myCurrentStep"]
rows = []
for n in bench(st["id"]):
    p = n["anyPlayer"]
    gs = [(g["anyGame"]["date"], g.get("projectedScore")) for g in n.get("eligiblePlayerGameScores") or [] if g and g.get("anyGame")]
    rows.append(f"{p['displayName']} · {p.get('gameplayTierStars')}★ · lesió {bool(p.get('activeInjuries'))} · " + "; ".join(f"{d[5:16]} {s}" for d, s in sorted(gs)))
print("::notice title=banc NBA::" + " ¶ ".join(sorted(rows)))
