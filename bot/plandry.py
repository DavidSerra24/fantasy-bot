"""Simulació (només lectura) de què farà el planificador durant un dia: python -m bot.plandry [AAAA-MM-DD]
No executa res ni llegeix Telegram; fa servir l'estat desat (state/) com el bot de veritat."""
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

os.environ.pop("TELEGRAM_BOT_TOKEN", None)  # no consumir missatges de Telegram
from bot import plan as P  # noqa: E402
from bot.web import load_json  # noqa: E402

M = ZoneInfo("Europe/Madrid")
day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else (dt.datetime.now(M) + dt.timedelta(days=1)).date()
done = list(load_json("done.json", []))
seen, rows, info0 = set(), [], None
t = dt.datetime.combine(day, dt.time(3, 5), M).astimezone(dt.timezone.utc)
end = dt.datetime.combine(day, dt.time(23, 59), M).astimezone(dt.timezone.utc)
while t < end:
    acts, info = P.plan(now=t, done=done)
    info0 = info0 or info
    for a in acts:
        if a["key"] in seen:
            continue
        seen.add(a["key"])
        done.append(a["key"])
        at = dt.datetime.fromisoformat(a["at"]).astimezone(M)
        rows.append((at, a["do"], a["comp"] or "", a["key"]))
    t += dt.timedelta(minutes=30)
rows.sort()
print("::notice title=info::" + " | ".join(info0 or []))
print(f"::notice title=pla {day}::" + " ¶ ".join(f"{at:%H:%M} {do} {comp}" for at, do, comp, k in rows))
