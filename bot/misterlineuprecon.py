"""Reconeixement (només lectura) de l'alineació i la quiniela del Mister per l'API interna: llegeix el codi JS de la web
i l'HTML de /team per veure quines dades envien ajax/sub-do, ajax/formation, el capità i ajax/pools. No canvia res.
Ús: python -m bot.misterlineuprecon"""
import re

from bot.misterapi import MisterAPI, U

api = MisterAPI().login()
api.community(2499621)
html = api.page("/team")
out = []
srcs = sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', html)))
out.append("scripts: " + ", ".join(s.split("/")[-1][:40] for s in srcs))
inline = "\n".join(re.findall(r"<script[^>]*>([\s\S]*?)</script>", html))
code = inline
for s in srcs:
    if s.startswith("//"):
        s = "https:" + s
    elif s.startswith("/"):
        s = U + s
    if "mundodeportivo" not in s and not s.startswith(U):
        continue
    try:
        code += "\n/*FILE " + s + "*/\n" + api.s.get(s, timeout=30).text
    except Exception as e:
        out.append(f"err {s}: {e}")
for k in ("sub-do", "subs", "substitution", "formation", "captain", "pools", "lineup", "slot_index", "gameweek"):
    hits = [m.start() for m in re.finditer(re.escape(k), code)][:6]
    for h in hits:
        out.append(f"[{k}] " + re.sub(r"\s+", " ", code[max(0, h - 250):h + 350]))
btn = re.findall(r"<button[^>]*lineup-player[^>]*>", html)[:3]
out.append("botons casella: " + " | ".join(btn))
out.append("formació: " + " | ".join(re.findall(r"<[^>]*data-popup=\"formation\"[^>]*>", html)[:2]))
for k in ("id_manager", "manager", "gameweek", "id_gameweek"):
    m = re.search(r'"' + k + r'"\s*:\s*"?([\w-]+)', html)
    if m:
        out.append(f"cfg {k} = {m.group(1)}")
for i in range(0, len(out)):
    print("RECON| " + out[i][:3000])
open("state/misterlineuprecon.txt", "w").write("\n".join(out))
