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
for t in ("team/substitution", "../components/pool/games", "../components/lineup/player"):
    r = api.s.get(f"{U}/views/ajax/{t}.twig", timeout=20)
    txt = sq(r.text)
    keep = " ## ".join(x for x in re.findall(r"<(?:button|input|div|li|a)\b[^>]*>", txt) if "data-" in x)
    out.append(f"TWIG {t} {r.status_code}: " + keep[:2900])
    if "captain" in txt:
        i = txt.find("captain")
        out.append(f"TWIG {t} captain: " + txt[max(0, i - 600):i + 900])
m = re.search(r"_FG_data\s*=\s*(\{.*?\});\s*\n", html, re.S)
if m:
    try:
        d = json.loads(m.group(1))
        out.append("_FG_data keys: " + ", ".join(d.keys()))
        for k in ("formations", "gameWeekId", "lineup", "manager", "managerId", "memberId", "id_uc", "captain"):
            if k in d:
                out.append(f"_FG_data.{k} = " + json.dumps(d[k])[:1500])
    except Exception as e:
        out.append(f"_FG_data parse: {e} {m.group(1)[:300]}")
else:
    out.append("sense _FG_data; " + " | ".join(sq(x)[:200] for x in re.findall(r"_FG_data[^;]{0,200}", html)[:5]))
for mm in re.finditer(r"(managerId|manager_id|memberId|member_id|id_uc)['\"]?\s*[:=]\s*['\"]?(\w+)", html):
    out.append(f"{mm.group(1)} = {mm.group(2)}")
b = [dict(re.findall(r'data-([\w-]+)="([^"]*)"', x)) for x in re.findall(r"<button[^>]*?lineup-player[\s\S]*?>", html)]
d2 = next((x for x in b if x.get("position") == "2"), None)
if d2:
    r = api.ajax("sw/substitution", dict(d2, post="substitution"))
    data = r.get("data") or {}
    out.append("sw/substitution DEF: list=" + json.dumps(data.get("list"))[:1500] + " | keys " + ", ".join(data.keys()))
for o in out:
    print("RECON| " + o[:3000])
