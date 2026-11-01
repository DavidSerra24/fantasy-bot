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
out.append("inline twigs: " + ", ".join(re.findall(r'id="twig-([\w-]+)"', html)))
for m in re.finditer(r'id="twig-(formation|substitution|pool[\w-]*|subs)"[^>]*>([\s\S]*?)</script>', html):
    out.append(f"INLINE {m.group(1)}: " + sq(m.group(2))[:2800])
for t in ("formation", "substitution", "pool-public", "pool-private", "pools", "subs"):
    r = api.s.get(f"{U}/views/ajax/{t}.twig", timeout=20)
    out.append(f"TWIG {t} {r.status_code}: " + (sq(r.text)[:2800] if r.status_code == 200 else ""))
for k in ("select_slot", "sw_open('substitution", 'sw_open("substitution', "lineup-player"):
    for m in list(re.finditer(re.escape(k), code))[:2]:
        out.append(f"[{k}] " + sq(code[max(0, m.start() - 200):m.start() + 600]))
for o in out:
    print("RECON| " + o[:3000])
