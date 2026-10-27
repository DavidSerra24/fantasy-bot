"""Executa les accions decidides pel planificador, a l'hora exacta (espera com a molt 30 min)."""
import datetime as dt
import json
import time
import traceback

from bot import ff, p11
from bot.notify import telegram
from bot.web import STATE, load_json, save_json

acts = json.loads((STATE / "actions.json").read_text(encoding="utf-8"))
acts.sort(key=lambda a: (a["at"], a.get("deadline", "")))  # a la mateixa hora, primer el que tanca abans
import sys
only = sys.argv[1] if len(sys.argv) > 1 else None  # executar només una acció (clau)
if only:
    acts = [a for a in acts if a["key"] == only]
done = set()
for a in acts:
    key = (a["do"], a["comp"])
    if key in done:
        continue
    wait = (dt.datetime.fromisoformat(a["at"]) - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if wait > 0:
        time.sleep(min(wait, 3600))
    names = {"laliga": "LaLiga", "laliga2": "LaLiga 2", "premier-league": "Premier", "serie-a": "Serie A",
             "champions": "Champions", "europa-league": "Europa League", None: ""}
    what = {"p11": f"Predicted11 {names.get(a['comp'], a['comp'])}" + (" (última revisió)" if "final" in a.get("key", "") else " (matí)"),
            "ff": "Fantasy de FutbolFantasy (matí: omplir i revisar els jocs oberts, ítems i extres del dia)",
            "mister": "Mister: pujes al mercat",
            "misteroff": "Mister: ofertes dels jugadors en venda",
            "misterxi": "Mister: alineació i capità" + (f" ({names.get(a['comp'], a['comp'])}, revisió final)" if a["comp"] else ""),
            "fffinal": f"revisió final del Fantasy {names.get(a['comp'], a['comp'])} (onzes oficials)"}[a["do"]]
    telegram(f"▶️ Començo: {what}")
    try:
        if a["do"] == "p11":
            p11.run([a["comp"]], force=False, max_hours=99)
        elif a["do"] == "ff":
            ff.run(max_hours=24 * 8, extras_hours=20)
        elif a["do"] == "misterxi":
            from bot import misterlineup
            misterlineup.run(only={"laliga": "Fentaniños", "laliga2": "Quique"}.get(a["comp"]))
        elif a["do"] == "misteroff":
            from bot import misteroffers
            misteroffers.run()
        elif a["do"] == "mister":
            from bot import mistermarket
            mistermarket.run()
        elif a["do"] == "fffinal":
            ff.run(max_hours=3, only=[a["comp"]], final=True)
    except Exception as e:
        traceback.print_exc()
        telegram(f"❌ Error a {a['do']} {a['comp'] or ''}: {type(e).__name__}: {str(e)[:300]}")
    done.add(key)
    d = load_json("done.json", [])
    d.append(a["key"])
    save_json("done.json", d[-300:])
