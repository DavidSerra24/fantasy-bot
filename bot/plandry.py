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
_now = dt.datetime.now(M)
day = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1][:2] == "20" else (_now.date() if _now.hour < 6 else (_now + dt.timedelta(days=1)).date())  # de matinada, «demà» és avui
t0 = max(dt.datetime.combine(day, dt.time(3, 5), M), _now)
done = list(load_json("done.json", []))
seen, rows, info0 = set(), [], None
t = t0.astimezone(dt.timezone.utc)
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
txt = " ¶ ".join(f"{at:%d %H:%M} {do} {comp}" for at, do, comp, k in rows)
for i in range(0, len(txt), 3800):
    print(f"::notice title=pla {day} ({i // 3800 + 1})::" + txt[i:i + 3800])
