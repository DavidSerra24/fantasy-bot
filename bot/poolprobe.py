"""Diagnosi (només lectura): quiniela del Mister tal com la veu l'API."""
import json

from playwright.sync_api import sync_playwright

from bot import misterapi
from bot.mister import login, new_context

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    login(pg)
    api = misterapi.API
    for cid, kind in ((2519290, "public"), (2519290, "private"), (2499621, "private")):
        api.community(cid)
        post = "pool-" + kind
        d = (api.ajax("sw/" + post, {"post": post}) or {})
        dd = d.get("data") or {}
        res = dd.get("results") or {}
        print(f"::notice title=pool {cid} {kind}::keys={list(dd)} status={d.get('status')} popup={d.get('popup')} locked={res.get('locked')} "
              + json.dumps([(m.get('home'), m.get('away'), m.get('prediction'), m.get('status')) for m in res.get('matches') or []], ensure_ascii=False)[:1500]
              + " | " + json.dumps({k: v for k, v in dd.items() if k not in ('results', 'gameweeks')}, ensure_ascii=False)[:800])
    b.close()
