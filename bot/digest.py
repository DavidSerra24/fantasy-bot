"""Resum del matí (decisió del David, 12/11: «un resum al matí dels Set i les missions, amb fotos, per veure les
alineacions que he guanyat o perdut»).

Durant el dia, cada passada del Set (futbol i NBA) i de les missions anota a `state/digest.json` l'últim estat de cada
alineació (punts de cada carta i total) i de cada pick de missió (estat); quan es reclama o es perd un nivell, també.
A les 9:10 (després de reclamar les missions a les 9:05) s'envia una imatge amb el que es va jugar ahir.
"""
import datetime as dt
from zoneinfo import ZoneInfo

from bot.web import STATE_LOCK, load_json, save_json

MAD = ZoneInfo("Europe/Madrid")
FILE = "digest.json"


def _day(iso):
    try:
        return dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(MAD).date().isoformat()
    except Exception:
        return dt.datetime.now(MAD).date().isoformat()


def note(kind, key, data):
    """kind: setlineup | mission | event. data ha de portar «date» (ISO) per saber a quin dia va."""
    try:
        with STATE_LOCK:
            j = load_json(FILE, {})
            j.setdefault(kind, {})[key] = dict(j.get(kind, {}).get(key, {}), **data, day=_day(data.get("date")))
            cut = (dt.datetime.now(MAD).date() - dt.timedelta(days=4)).isoformat()
            for k in list(j):
                j[k] = {kk: v for kk, v in j[k].items() if v.get("day", "9999") >= cut}
            save_json(FILE, j)
    except Exception as e:
        print(f"::warning title=resum::{str(e)[:150]}")


def set_lineups(sport, board, step, lineups, kind="setlineup"):
    """Anota les alineacions del pas (amb `score` de l'alineació i de cada aparició)."""
    for l in lineups or []:
        apps = [a for a in l.get("taskAppearances") or [] if a]
        dates = [a["game"]["date"] for a in apps if a.get("game")]
        if not apps or not dates:
            continue
        note(kind, l["id"], {"date": min(dates), "sport": sport, "board": (board or {}).get("title") or "",
                             "mode": step.get("__typename") or "", "level": (step.get("level") or 0) + 1, "target": step.get("target"),
                             "score": l.get("score"), "state": l.get("aasmState"),
                             "players": [{"name": a["anyPlayer"]["displayName"], "pic": (a.get("anyCard") or {}).get("pictureUrl"),
                                          "score": a.get("score")} for a in apps]})


def mission(task, sport, rarity, apps):
    dates = [a["game"]["date"] for a in apps if a.get("game")]
    if not dates:
        return
    note("mission", task["id"], {"date": min(dates), "sport": sport, "rarity": rarity, "title": task.get("title"),
                                 "desc": task.get("description"), "state": task.get("aasmState"),
                                 "picks": [{"name": a["anyPlayer"]["displayName"], "pic": (a.get("anyCard") or {}).get("pictureUrl"),
                                            "status": a.get("status")} for a in sorted(apps, key=lambda a: a.get("index", 0))]})


def event(text, date=None):
    now = dt.datetime.now(dt.timezone.utc)
    note("event", f"{now.timestamp():.0f}", {"date": (date or now.isoformat()), "text": text})


def _ok(status):
    s = str(status or "").upper()
    if any(x in s for x in ("SUCC", "WON", "WIN", "COMPLET", "VALID")):
        return True
    if any(x in s for x in ("FAIL", "LOST", "LOSE", "INVALID")):
        return False
    return None


def refresh():
    """Abans del resum, una última lectura dels taulers del Set i de les missions (puntuacions finals de la matinada)."""
    try:
        from bot import sorarefset, sorareset
        for m in ("CAREER", "SQUAD"):
            sorarefset.gql_step({"m": m})
            sorareset.gql_step({"sp": "NBA", "m": m})
    except Exception as e:
        print(f"::warning title=resum taulers::{str(e)[:150]}")
    try:
        from bot import soraremissions as sm
        from bot.sorare import gql, token
        for pri, rarity, t in sm.list_tasks([]):
            task = gql(sm.TASK, {"id": t["id"].split(":")[-1]}, token=token())["currentUser"]["task"]
            if task:
                mission(task, t["sport"], rarity, task.get("taskAppearances") or [])
    except Exception as e:
        print(f"::warning title=resum missions::{str(e)[:150]}")


def run(day=None):
    """Envia la imatge del resum del dia `day` (per defecte, ahir)."""
    from bot.notify import telegram
    from bot.tgimg import send_digest
    # finestra: les últimes 24 h fins ara (a les 8:00; així entra l'NBA de la matinada; decisió del David, 12/11)
    refresh()
    now = dt.datetime.now(dt.timezone.utc)
    if day:
        lo = dt.datetime.fromisoformat(day).replace(hour=8, tzinfo=MAD).astimezone(dt.timezone.utc)
        now = lo + dt.timedelta(hours=24)
    lo = now - dt.timedelta(hours=24)

    def inwin(v):
        try:
            d = dt.datetime.fromisoformat(str(v.get("date")).replace("Z", "+00:00"))
            return lo <= d < now
        except Exception:
            return False
    j = load_json(FILE, {})
    sets = sorted([v for v in j.get("setlineup", {}).values() if inwin(v)], key=lambda v: (v["sport"], v.get("mode", ""), v["date"]))
    mis = [v for v in j.get("mission", {}).values() if inwin(v)]
    evs = [v["text"] for v in j.get("event", {}).values() if inwin(v)]
    day = now.astimezone(MAD).date().isoformat()
    if not (sets or mis or evs):
        print(f"::notice title=resum::res del {day}")
        return
    blocks = []
    for v in sets:
        sc, tg = v.get("score"), v.get("target")
        won = None if sc is None or tg is None else sc >= tg
        blocks.append({"kind": "set", "title": f"{'🏀' if v['sport'] == 'NBA' else '⚽'} Set · {v.get('board')} · nivell {v.get('level')}"
                       + (" · equip" if "Squad" in (v.get("mode") or "") else ""),
                       "score": sc, "target": tg, "won": won,
                       "players": [{"name": p["name"], "pic": p.get("pic"), "badge": "" if p.get("score") is None else f"{p['score']:.0f}"}
                                   for p in v["players"]]})
    for v in mis:
        oks = [_ok(p.get("status")) for p in v["picks"]]
        blocks.append({"kind": "mission", "title": f"{'🏀' if v['sport'] == 'NBA' else '⚽'} {v.get('title')}", "tag": v.get("rarity") or "",
                       "desc": v.get("desc") or "", "won": (True if oks and all(o is True for o in oks) else (False if oks and all(o is False for o in oks) else None)),
                       "players": [{"name": p["name"], "pic": p.get("pic"), "ok": o, "status": p.get("status")} for p, o in zip(v["picks"], oks)]})
    d = dt.date.fromisoformat(day)
    title = f"Resum del {['dilluns', 'dimarts', 'dimecres', 'dijous', 'divendres', 'dissabte', 'diumenge'][d.weekday()]} {d.day}/{d.month} (últimes 24 h)"
    won = sum(1 for b in blocks if b["won"] is True)
    lost = sum(1 for b in blocks if b["won"] is False)
    sw = sum(1 for b in blocks if b["kind"] == "set" and b["won"] is True)
    sl = sum(1 for b in blocks if b["kind"] == "set" and b["won"] is False)
    mk = sum(1 for b in blocks if b["kind"] == "mission" for p in b["players"] if p.get("ok"))
    mn = sum(1 for b in blocks if b["kind"] == "mission" for p in b["players"])
    cap = f"☀️ {title}: Set {sw} guanyades, {sl} perdudes · missions {mk}/{mn} picks encertats" + ("\n" + "\n".join(evs) if evs else "")
    if not send_digest(title, blocks, caption=cap[:1000]):
        telegram(cap + "\n" + "\n".join(f"{'✅' if b['won'] else '❌' if b['won'] is False else '•'} {b['title']}" for b in blocks))


if __name__ == "__main__":
    import sys
    run(sys.argv[1] if len(sys.argv) > 1 else None)
