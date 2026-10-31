"""Reconeixement (només lectura): on surten les peticions de cessió rebudes i com s'accepten."""
import re

from bot.misterapi import MisterAPI

api = MisterAPI().login()
out = []
for cid in (2499621, 2519290):
    api.community(cid)
    m = re.sub(r"\s+", " ", api.page("/market"))
    out.append(f"{cid} market data-sw/popups: " + ", ".join(sorted(set(re.findall(r'data-(?:sw|popup)="([^"]+)"', m))))[:1500])
    out.append(f"{cid} offers: " + " ### ".join(x.group(0) for x in re.finditer(r".{0,200}(offers-received|loan|cesi|cedi).{0,250}", m, re.I))[:2500])
out = []
for v in ("loan-confirm", "market/offers-received/direct-transfer-confirmation"):
    r = api.s.get(f"https://mister.mundodeportivo.com/views/ajax/{v}.twig", timeout=20)
    t = re.sub(r"\s+", " ", r.text)
    out.append(f"twig {v} ({r.status_code}): " + (t[:3000] if r.status_code == 200 else ""))
for k, o in enumerate(out):
    print(f"::notice title=r{k}::" + o[:3900])
