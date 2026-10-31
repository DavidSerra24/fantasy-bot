"""Reconeixement (només lectura): plantilles de les finestres (opció de cessió)."""
import re

from bot.misterapi import MisterAPI

api = MisterAPI().login()
out = []
for v in ("sale", "bid", "player", "player-community", "market/sale", "loan-config", "loanable"):
    r = api.s.get(f"https://mister.mundodeportivo.com/views/ajax/{v}.twig", timeout=20)
    t = re.sub(r"\s+", " ", r.text)
    hits = [m.group(0) for m in re.finditer(r".{0,250}(loan|cesi|cedi|préstamo).{0,350}", t, re.I)]
    out.append(f"{v} ({r.status_code}, {len(t)}): " + (" ### ".join(hits)[:3500] if hits else t[:600]))
for k, o in enumerate(out):
    print(f"::notice title=twig {k}::" + o)
