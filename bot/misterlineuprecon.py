"""Prova (només lectura): com canvia de jornada la quiniela."""
import re

from bot.misterapi import MisterAPI, U

api = MisterAPI().login()
html = api.page("/feed")
code = ""
for s in sorted(set(re.findall(r'<script[^>]+src="([^"]+)"', html))):
    if "mundodeportivo" in s:
        try:
            code += "\n" + api.s.get(s if s.startswith("http") else "https:" + s, timeout=30).text
        except Exception:
            pass
for k in ("pool-gw-selector", "data-pool"):
    for m in list(re.finditer(re.escape(k), code))[:3]:
        print("::notice title=" + k + "::" + re.sub(r"\s+", " ", code[max(0, m.start() - 300):m.start() + 900]))
