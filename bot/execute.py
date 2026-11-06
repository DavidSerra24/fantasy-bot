"""Executa les accions decidides pel planificador, a l'hora exacta (espera com a molt 90 min).

Dos carrils en paral·lel (decisió del David, 6/11: el 6/11 la revisió del Set de 2 min abans del partit de les 20:45
va arribar tard perquè el bot encara feia les revisions finals del Fantasy):
- lent: Fantasy, Predicted11, Mister, quinieles (navegador);
- ràpid: Sorare i Collectibol (només API). Mentre el carril lent treballa, el ràpid torna a planificar cada 3 min les
  seves accions (plan.plan(fast_only=True)), perquè la següent execució de GitHub no arrenca fins que acaba aquesta."""
import datetime as dt
import json
import sys
import threading
import time
import traceback

from bot import ff, p11
from bot.notify import telegram
from bot.plan import is_fast
from bot.web import STATE, STATE_LOCK as LOCK, load_json, save_json  # done.json, tries.json i dyn_actions.json: tots dos carrils
REPLAN_S = 180


def _done_list():
    with LOCK:
        return load_json("done.json", [])


def _mark_done(key):
    with LOCK:
        d = load_json("done.json", [])
        d.append(key)
        save_json("done.json", d[-400:])


def _take_dyn(fast):
    """Accions afegides durant l'execució (p. ex. l'Arena d'un porter titular) que són d'aquest carril."""
    with LOCK:
        dyn = load_json("dyn_actions.json", [])
        mine = [d for d in dyn if is_fast(d) == fast]
        if mine:
            save_json("dyn_actions.json", [d for d in dyn if is_fast(d) != fast])
    done = set(_done_list())
    return [d for d in mine if d["key"] not in done]


def run_action(a):
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
            "sorarexi": "Sorare: porters", "sorarearena": "Sorare: Arena amb porter", "sorarearenas": "Sorare: Arenes", "soraremission": "Sorare: Decisive Picker", "misterloan": "Mister: cessions", "soraresetscan": "Sorare Set: partits", "soraresetgo": "Sorare Set: alineacions", "soraresetrev": "Sorare Set: revisió", "misterloanoff": "Mister: peticions de cessió", "misterloanend": "Mister: fi de les cessions", "collectibol": "Collectibol: resultat", "sorarefset": "Sorare Set futbol"}[a["do"]]
    if a["do"] not in ("quinrem", "sorarexi", "sorarearena", "sorarearenas", "soraremission", "misterloan", "soraresetscan", "soraresetgo", "soraresetrev", "misterloanoff", "misterloanend", "collectibol", "sorarefset"):  # el recordatori ja envia el seu missatge (només si cal)
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
        elif a["do"] in ("soraresetscan", "soraresetgo"):
            from bot import sorareset
            sorareset.run(dry=False, scan=a["do"] == "soraresetscan")
        elif a["do"] == "soraresetrev":
            from bot import sorareset
            sorareset.review(dry=False)
        elif a["do"] in ("misterloanoff", "misterloanend"):
            from bot import misteroffers
            misteroffers.run_loans(only=(a["comp"] or "").split("|")[0] or None, end=a["do"] == "misterloanend")
        elif a["do"] == "misterloan":
            from bot import misterloanwatch
            misterloanwatch.run()
        elif a["do"] == "sorarefset":
            from bot import sorarefset
            c = a["comp"] or ""
            sorarefset.run(focus=c.rsplit(":", 1)[0] if "Z:" in c else None)  # revisió final d'unes alineacions concretes
        elif a["do"] == "collectibol":
            from bot import collectibol
            collectibol.check(a["comp"].split("|")[0])
        elif a["do"] == "soraremission":
            from bot import soraremissions
            soraremissions.run()
        elif a["do"] == "sorarearenas":
            from bot import sorarelineup
            kind, _, at = a["comp"].partition("|")
            sorarelineup.late_arenas(kind, at or None)
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
        traceback.print_exc()
        print("::error title=" + a["do"] + "::" + traceback.format_exc().replace("\n", " | ")[-1500:])
        with LOCK:
            tries = load_json("tries.json", {})
            tries[a["key"]] = tries.get(a["key"], 0) + 1
            save_json("tries.json", tries)
        retry = (a["do"].startswith("mister") or a["do"] == "sorare") and tries[a["key"]] < 3  # Mister: es torna a provar a la propera execució
        telegram(f"❌ Error a {a['do']} {a['comp'] or ''}: {type(e).__name__}: {str(e)[:300]}" + (" · ho torno a provar d'aquí a una estona" if retry else ""))
        if retry:
            return False  # es torna a provar a la propera execució
    return True


def lane(queue, fast, slow_alive=lambda: False):
    done = set()
    queue = list(queue)
    last_plan = time.time()
    while True:
        queue += _take_dyn(fast)
        if fast and slow_alive() and time.time() - last_plan >= REPLAN_S:
            last_plan = time.time()
            try:
                from bot.plan import plan
                have = {q["key"] for q in queue}
                new, _ = plan(done=_done_list(), fast_only=True)
                new = [n for n in new if n["key"] not in have and (n["do"], n["comp"]) not in done]
                if new:
                    print("::notice title=carril ràpid::noves accions: " + " | ".join(f"{n['do']} {n['comp'] or ''} {n['at'][11:16]}Z" for n in new))
                    queue += new
            except Exception as e:
                print(f"::warning title=carril ràpid::no he pogut planificar: {str(e)[:300]}")
        queue.sort(key=lambda a: (a["at"], a.get("deadline", "")))  # a la mateixa hora, primer el que tanca abans
        if not queue:
            if fast and slow_alive():
                time.sleep(20)
                continue
            break
        a = queue[0]
        wait = (dt.datetime.fromisoformat(a["at"]) - dt.datetime.now(dt.timezone.utc)).total_seconds()
        if wait > 0:
            # el carril ràpid no s'adorm més de 20 s seguits: així veu les accions noves (dinàmiques o replanificades)
            time.sleep(min(wait, 20 if fast else 5400))
            if fast:
                continue
        queue.pop(0)
        key = (a["do"], a["comp"])
        if key in done:
            continue
        ok = run_action(a)
        done.add(key)
        if ok:
            _mark_done(a["key"])


def main():
    acts = json.loads((STATE / "actions.json").read_text(encoding="utf-8"))
    only = sys.argv[1] if len(sys.argv) > 1 else None  # executar només una acció (clau)
    if only:
        acts = [a for a in acts if a["key"] == only]
    with LOCK:
        save_json("dyn_actions.json", [])
    slow = [a for a in acts if not is_fast(a)]
    fast = [a for a in acts if is_fast(a)]
    t = threading.Thread(target=lane, args=(slow, False), name="lent")
    t.start()
    lane(fast, True, slow_alive=t.is_alive)
    t.join()
    lane([], True)  # accions dinàmiques ràpides que hagi deixat el carril lent al final


if __name__ == "__main__":
    main()
