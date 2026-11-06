"""Diagnosi (només lectura): pàgina d'equip del Mister (jugadors amb punts/mitjana?)."""
import re

from bot.misterapi import MisterAPI

api = MisterAPI().login()
api.community(2499621)
html = api.page("/teams/103/oviedo")
print(f"::notice title=len::{len(html)}")
for m in list(re.finditer(r'players/(\d+)/', html))[:3]:
    print("::notice title=ctx::" + re.sub(r"\s+", " ", html[max(0, m.start() - 600):m.start() + 900]))
d = api.ajax("sw/player", {"id_player": "48275"}) if False else None
