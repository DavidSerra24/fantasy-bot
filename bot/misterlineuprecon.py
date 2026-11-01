"""Prova (només lectura): selector de jornada de la quiniela."""
import json
import re

from bot.misterapi import MisterAPI, U

api = MisterAPI().login()
r = api.s.get(f"{U}/views/components/pool/gw-selector.twig", timeout=20)
print("::notice title=gw-selector::" + re.sub(r"\s+", " ", r.text)[:3000])
api.community(2519290)
for extra in ({}, {"id_gameweek": 4054}, {"gw": 4054}, {"gameweek": 4054}):
    d = (api.ajax("sw/pool-private", dict({"post": "pool-private"}, **extra)) or {}).get("data") or {}
    res = d.get("results") or {}
    print(f"::notice title=pool {json.dumps(extra)}::id_gw={d.get('id_gameweek')} locked={res.get('locked')} n={len(res.get('matches') or [])} first={(res.get('matches') or [{}])[0].get('id_gameweek')}")
