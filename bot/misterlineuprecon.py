"""Reconeixement (només lectura) de la quiniela del Mister per l'API interna. No canvia res."""
import json
import re

from bot.misterapi import MisterAPI, U

api = MisterAPI().login()
for cid in (2519290, 2499621):
    api.community(cid)
    for post in ("pool-public", "pool-private"):
        d = (api.ajax("sw/" + post, {"post": post}) or {}).get("data") or {}
        res = d.get("results")
        print("RECON| " + f"{cid} {post} keys={list(d.keys())} id_gw={d.get('id_gameweek')} results_type={type(res).__name__} " + json.dumps(res)[:2500])
r = api.s.get(f"{U}/views/ajax/../components/pool/games.twig", timeout=20)
print("RECON| games.twig " + re.sub(r"\s+", " ", r.text)[:2500])
