"""Prova: porters de l'All Star GW730 (Livaković) amb %, club, partit i lletra."""
from bot.sorare import gql, token
from bot.sorarelineup import FIXTURE, bench

fx = gql(FIXTURE, token=token())["so5"]["so5Fixture"]
for lb in [l for l in fx["so5Leaderboards"] if not l["isArena"] and "all_star" in l["slug"]]:
    hi = {n["anyCard"]["slug"] for n in bench(lb["slug"], {"min": 8000}, ["Goalkeeper"])}
    rows = []
    for n in bench(lb["slug"], None, ["Goalkeeper"]):
        c, p = n["anyCard"], n["anyPlayer"]
        g = (n.get("eligiblePlayerGameScores") or [{}])[0] or {}
        gm = g.get("anyGame") or {}
        rows.append(f"{p['displayName']} ({(p.get('activeClub') or {}).get('name')}) {c['rarityTyped']} ≥80%={c['slug'] in hi} "
                    f"{(g.get('projection') or {}).get('grade')} {gm.get('date')} {(gm.get('homeTeam') or {}).get('name')}-{(gm.get('awayTeam') or {}).get('name')}")
    print(f"::notice title={lb['displayName']}::" + " ¶ ".join(rows)[:3900])
print("::notice title=lineups::" + " ¶ ".join(f"{l['so5Leaderboard']['displayName']}: " + ", ".join(a['anyPlayer']['displayName'] for a in l['so5Appearances']) for l in fx.get("mySo5Lineups") or [])[:3000])
