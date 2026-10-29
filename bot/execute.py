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
            "mister": "Mister: " + ("revisió abans de les 5:00 (pujes i vendes)" if a["comp"] == "pre" else "pujes al mercat"),
            "quinrem": f"recordatori de la Quiniela {names.get(a['comp'], a['comp'])}",
            "quiniela": f"Quiniela {names.get(a['comp'], a['comp'])} (la que m'has enviat)",
            "copa": "revisió final de l'extra de la Copa del Rey (onzes oficials)",
            "misteroff": "Mister: ofertes dels jugadors en venda",
            "misterxi": "Mister: alineació i capità" + (f" ({names.get(a['comp'], a['comp'])}, revisió final)" if a["comp"] else ""),
            "fffinal": f"revisió final del Fantasy {names.get(a['comp'], a['comp'])} (onzes oficials)",
            "sorare": "Sorare: " + ("revisió final de les alineacions + Arenes" if a["comp"] == "final" else "omplir/revisar les alineacions"),
            "sorarexi": "Sorare: porters", "sorarearena": "Sorare: Arena amb porter"}[a["do"]]
    if a["do"] not in ("quinrem", "sorarexi", "sorarearena"):  # el recordatori ja envia el seu missatge (només si cal)
        telegram(f"▶️ Començo: {what}")
    try:
        if a["do"] == "p11":
            p11.run([a["comp"]], force=False, max_hours=99)
        elif a["do"] == "ff":
            ff.run(max_hours=24 * 8, extras_hours=24 * 8)
        elif a["do"] == "misterxi":
            from bot import misterlineup
            misterlineup.run(only={"laliga": "Fentaniños", "laliga2": "Quique"}.get(a["comp"]), final=bool(a["comp"]))
        elif a["do"] == "quinrem":
            from bot import quiniela
            save_json("quinrem_last.json", {"comp": a["comp"]})
            quiniela.run(a["comp"], remind=a.get("text", ""))
        elif a["do"] == "quiniela":
            from bot import quiniela, misterpool
            quiniela.run(a["comp"], a.get("text", ""))
            if a["comp"] in misterpool.POOLS:  # mateixos resultats a la quiniela del Mister (1 X 2)
                lines = misterpool.run(a["comp"], quiniela.parse(a.get("text", "")))
                for l in lines:
                    print("::notice title=pool::" + l)
                if lines:
                    telegram("\n".join(lines))
        elif a["do"] == "copa":
            from bot import copa
            copa.run()
        elif a["do"] == "misteroff":
            from bot import misteroffers
            misteroffers.run()
        elif a["do"] == "mister":
            from bot import mistermarket
            mistermarket.run()
        elif a["do"] == "sorare":
            from bot import sorarelineup
            sorarelineup.run(a["comp"])
        elif a["do"] == "sorarearena":
            from bot import sorarelineup
            sorarelineup.gk_arena_final(a["comp"])
        elif a["do"] == "sorarexi":
            from bot import sorarelineup
            gid, mins = a["comp"].split("|")
            sorarelineup.gk_check(gid, int(mins))
        elif a["do"] == "fffinal":
            ff.run(max_hours=3, only=[a["comp"]], final=True)
    except Exception as e:
        failed = True
        traceback.print_exc()
        print("::error title=" + a["do"] + "::" + traceback.format_exc().replace("\n", " | ")[-1500:])
        tries = load_json("tries.json", {})
        tries[a["key"]] = tries.get(a["key"], 0) + 1
        save_json("tries.json", tries)
        retry = (a["do"].startswith("mister") or a["do"] == "sorare") and tries[a["key"]] < 3  # Mister: es torna a provar a la propera execució
        telegram(f"❌ Error a {a['do']} {a['comp'] or ''}: {type(e).__name__}: {str(e)[:300]}" + (" · ho torno a provar d'aquí a una estona" if retry else ""))
        if retry:
            done.add(key)
            continue
    done.add(key)
    d = load_json("done.json", [])
    d.append(a["key"])
    save_json("done.json", d[-300:])
