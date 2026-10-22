"""Executa les accions decidides pel planificador, a l'hora exacta (espera com a molt 30 min)."""
import datetime as dt
import json
import time
import traceback

from bot import ff, p11
from bot.notify import telegram
from bot.web import STATE

acts = json.loads((STATE / "actions.json").read_text(encoding="utf-8"))
acts.sort(key=lambda a: a["at"])
done = set()
for a in acts:
    key = (a["do"], a["comp"])
    if key in done:
        continue
    wait = (dt.datetime.fromisoformat(a["at"]) - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if wait > 0:
        time.sleep(min(wait, 1800))
    try:
        if a["do"] == "p11":
            p11.run([a["comp"]], force=False, max_hours=99)
        elif a["do"] == "ff":
            ff.run(max_hours=20)
        elif a["do"] == "fffinal":
            ff.run(max_hours=3, only=[a["comp"]], final=True)
    except Exception as e:
        traceback.print_exc()
        telegram(f"❌ Error a {a['do']} {a['comp'] or ''}: {type(e).__name__}: {str(e)[:300]}")
    done.add(key)
