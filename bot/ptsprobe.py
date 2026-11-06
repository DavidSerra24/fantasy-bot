"""Diagnosi (només lectura): pàgina d'equip del Mister (jugadors amb punts/mitjana?)."""
import re

from bot.misterapi import MisterAPI

api = MisterAPI().login()
api.community(2499621)
html = api.page("/teams/103/oviedo")
ids = re.findall(r'players/(\d+)/', html)
print(f"::notice title=ids::{len(ids)} únics {len(set(ids))}")
titles = re.findall(r'<h4>([^<]+)</h4>', html)
print("::notice title=seccions::" + " | ".join(titles))
for kw in ('class="points', "class='points", "avg", "Mitjana", "Punts"):
    for m in list(re.finditer(re.escape(kw), html))[:2]:
        print(f"::notice title=kw {kw}::" + re.sub(r"\s+", " ", html[max(0, m.start() - 700):m.start() + 300]))
p = api.page("/players/48275/aaron-escandell")
t2 = re.findall(r'<h4>([^<]+)</h4>', p)
print("::notice title=seccions jugador::" + " | ".join(t2))
for kw in ('class="points', "box-points", "gw", "Jornada"):
    for m in list(re.finditer(re.escape(kw), p))[:2]:
        print(f"::notice title=pj {kw}::" + re.sub(r"\s+", " ", p[max(0, m.start() - 300):m.start() + 900]))
