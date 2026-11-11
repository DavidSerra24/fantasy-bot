"""Prova: totes les cartes elegibles de les competicions obertes de la jornada en joc (posició, %, partit)."""
from bot.sorarelineup import bench, live_open

fx, lbs = live_open(save=False)
for lb in lbs:
    hi = {n["anyCard"]["slug"] for n in bench(lb["slug"], {"min": 8000}) + bench(lb["slug"], {"min": 8000}, ["Goalkeeper"])}
    rows = []
    for n in bench(lb["slug"]) + bench(lb["slug"], None, ["Goalkeeper"]):
        c, p = n["anyCard"], n["anyPlayer"]
        g = (n.get("eligiblePlayerGameScores") or [{}])[0] or {}
        gm = g.get("anyGame") or {}
        rows.append(f"{p['displayName']} {n.get('position')} {c['rarityTyped']} ≥80%={c['slug'] in hi} {(g.get('projection') or {}).get('grade')} "
                    f"{(gm.get('date') or '')[:16]} {(gm.get('homeTeam') or {}).get('name')}-{(gm.get('awayTeam') or {}).get('name')}")
    print(f"::notice title={lb['displayName']} (tanca {lb['cutOffDate']})::" + " ¶ ".join(rows)[:3900])
