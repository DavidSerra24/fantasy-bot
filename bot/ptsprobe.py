"""Diagnosi (només lectura): quines dades de punts dona el Mister d'un jugador."""
import json
import re

from bot.misterapi import MisterAPI

api = MisterAPI().login()
api.community(2499621)
team = api.page("/team")
pids = list(dict.fromkeys(re.findall(r'players/(\d+)/', team)))[:2]
for pid in pids:
    d = api.ajax("player-community-info", {"id_player": pid, "popup": "bid"}).get("data") or {}
    print(f"::notice title=info {pid}::" + json.dumps({k: d.get(k) for k in ("name", "points", "avg", "team", "position", "status")}, ensure_ascii=False)[:1500])
    html = api.page(f"/players/{pid}")
    i = html.find("Puntos")
    print(f"::notice title=page {pid}::len={len(html)} " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " | ", html))[:200])
    for kw in ("gameweek", "points", "jornada", "box-points", "player-points", "data-points"):
        j = html.find(kw)
        if j >= 0:
            print(f"::notice title=kw {kw}::" + re.sub(r"\s+", " ", html[max(0, j - 300):j + 900]))
