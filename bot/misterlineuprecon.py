"""Prova (només lectura): partits de la quiniela del Mister per l'API."""
from bot.misterapi import MisterAPI

api = MisterAPI().login()
for cid, kind in ((2519290, "public"), (2519290, "private"), (2499621, "private")):
    api.community(cid)
    rows, locked = api.pool(kind)
    print(f"::notice title=quiniela {cid} {kind}::locked={locked} " + "; ".join(f"{r['id']} {r['home']}-{r['away']} {r['sel']}{' 🔒' if r['locked'] else ''}" for r in rows))
