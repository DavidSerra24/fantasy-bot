"""Diagnosi (26/11): missions i recompenses (tipus) sense reclamar res."""
from bot.sorare import gql, token
from bot.soraremissions import CLAIMQ, SAFE_REWARDS
out = []
for sp in ("FOOTBALL", "NBA"):
    d = gql(CLAIMQ, {"sp": sp}, token=token())["currentUser"]
    for t in (d["taskGroup"]["myTasks"] or []) + (d["setPlayTasks"] or []):
        k = {r.get("__typename") for r in t.get("rewardConfigs") or []}
        out.append(f"{sp} {t.get('title')} [{t.get('aasmState')}] {sorted(k)} {'OK' if k and not k - SAFE_REWARDS else 'NO'}")
print("::notice title=missions::" + " ¶ ".join(out)[:3900])
