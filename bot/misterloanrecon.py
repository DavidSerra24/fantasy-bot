"""Reconeixement (només lectura): com es posa un jugador «en cessió» al Mister (finestra i formulari), sense enviar res."""
import json
import re

from bot.misterapi import MisterAPI

api = MisterAPI().login()
api.community(2499621)
team = api.page("/team")
pids = list(dict.fromkeys(re.findall(r'href="players/(\d+)/', team)))[:3]
out = []
for kind in ("loan", "sale", "manage", "loanable"):
    try:
        d = api.ajax("player-community-info", {"id_player": pids[0], "popup": kind})
        out.append(f"{kind}: " + json.dumps(d)[:2500])
    except Exception as e:
        out.append(f"{kind}: ERR {str(e)[:200]}")
for v in ("loan", "player-loan", "market/loan", "sale", "manage"):
    try:
        r = api.s.get(f"https://mister.mundodeportivo.com/views/ajax/{v}.twig", timeout=20)
        out.append(f"twig {v}: {r.status_code} {r.text[:2500]}")
    except Exception as e:
        out.append(f"twig {v}: {e}")
js = [m for m in re.findall(r'src="([^"]+\.js[^"]*)"', team)][:12]
out.append("js: " + ", ".join(js))
for k, o in enumerate(out):
    print(f"::notice title=loan {k}::" + o.replace("\n", " ")[:3900])
