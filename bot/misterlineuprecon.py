"""Reconeixement (només lectura) de l'alineació i la quiniela del Mister per l'API interna. No canvia res.
Ús: python -m bot.misterlineuprecon"""
import json
import re

from bot.misterapi import MisterAPI, U

api = MisterAPI().login()
out = []
sq = lambda x: re.sub(r"\s+", " ", x)
api.community(2499621)
html = api.page("/team?gameweek=13")
code = ""
for s in sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', html))):
    if "mundodeportivo" in s and any(k in s for k in ("functions", "global", "listeners", "common", "team")):
        code += "\n" + api.s.get(s if s.startswith("http") else "https:" + s, timeout=30).text
for k in ("function popup_twig", "function sw_twig", "function sw_open", "select_slot", "'.player'", "sw-content .player", "data-captain-toggle"):
    for m in list(re.finditer(re.escape(k), code))[:3]:
        out.append(f"[{k}] " + sq(code[max(0, m.start() - 150):m.start() + 900]))
base = re.search(r'"base"\s*:\s*"([^"]+)"', html)
out.append("base: " + (base.group(1) if base else "?") + " | twig: " + str(re.search(r'"twig"\s*:\s*"?(\w+)', html).group(1)))
for t in ("views/popups/formation.twig", "views/popup/formation.twig", "views/formation.twig", "views/sw/substitution.twig", "views/substitution.twig",
          "views/popups/substitution.twig", "views/sw/pool-public.twig", "views/pool-public.twig", "views/ajax/pools.twig", "views/sw/pools.twig"):
    for root in (U + "/", "https://app-mister.mundodeportivo.com/file/forge-app/786c6e4f/app/"):
        try:
            r = api.s.get(root + t, timeout=20)
        except Exception as e:
            continue
        if r.status_code == 200 and "{%" in r.text:
            out.append(f"TWIG {root}{t}: " + sq(r.text)[:2800])
            break
    else:
        out.append(f"TWIG {t}: no")
for o in out:
    print("RECON| " + o[:3000])
