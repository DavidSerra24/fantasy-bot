"""FotMob: onze oficial d'un partit (sovint surt abans que a Sorare, quan el club el publica).

FotMob dona també onzes previstos («predicted») i l'onze del partit anterior («lastStarting11»): només compta
lineupType «standard» (onze oficial), amb 11 titulars per equip i com a molt 3 h abans del partit.
Sense navegador (només requests), perquè es pugui fer servir des de qualsevol workflow.
"""
import datetime as dt
import re
import unicodedata

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
STOP = {"fc", "cf", "ac", "sc", "afc", "cd", "ud", "rc", "ss", "us", "calcio", "club", "de", "real", "sk", "fk", "kv", "spor",
        "kulubu", "d", "sv", "vfb", "vfl", "tsg", "1", "as", "ogc", "losc", "rcd", "sd", "ca", "sporting", "fussball", "football"}
_days = {}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9 ]+", " ", s).split()


def team_score(a, b):
    ta, tb = set(norm(a)) - STOP, set(norm(b)) - STOP
    return len(ta & tb) + (1 if any(len(x) >= 4 and (x.startswith(y) or y.startswith(x)) for x in ta for y in tb if len(y) >= 4) else 0)


def same_player(a, b):
    """Sorare i FotMob escriuen els noms diferent: igual, o mateix cognom (última paraula) i inicial compatible."""
    ta, tb = norm(a), norm(b)
    if not ta or not tb:
        return False
    if ta == tb or set(ta) <= set(tb) or set(tb) <= set(ta):
        return True
    return ta[-1] == tb[-1] and (len(ta) == 1 or len(tb) == 1 or ta[0][0] == tb[0][0])


def matches(day):
    k = day.strftime("%Y%m%d")
    if k not in _days:
        try:
            _days[k] = [m for lg in requests.get(f"https://www.fotmob.com/api/data/matches?date={k}", headers=H, timeout=20).json().get("leagues", [])
                        for m in lg.get("matches", [])]
        except Exception:
            _days[k] = []
    return _days[k]


YOUTH = re.compile(r"\b(u\d\d|ii|b|women|w|femenino|feminine|reserves?|youth|juvenil)\b", re.I)


def find(home, away, when):
    """id del partit de FotMob: mateixos equips (local i visitant) i mateixa hora (±20 min). FotMob agrupa per dia
    local: es miren el dia d'abans, el mateix i el de després. Els equips filials, juvenils o femenins no compten
    (llevat que el nom de Sorare també ho sigui)."""
    best, bs = None, 0
    youth = bool(YOUTH.search(home) or YOUTH.search(away))
    for d in (when - dt.timedelta(days=1), when, when + dt.timedelta(days=1)):
        for m in matches(d):
            hn, an = m["home"].get("longName") or m["home"]["name"], m["away"].get("longName") or m["away"]["name"]
            if not youth and (YOUTH.search(hn) or YOUTH.search(an)):
                continue
            t = (m.get("status") or {}).get("utcTime")
            try:
                if not t or abs((dt.datetime.fromisoformat(t.replace("Z", "+00:00")) - when).total_seconds()) > 20 * 60:
                    continue
            except ValueError:
                continue
            sc = min(team_score(home, hn), team_score(away, an))
            if sc > bs:
                best, bs = m["id"], sc
    return best if bs > 0 else None


def starters(home, away, when):
    """Llista de noms dels titulars oficials dels dos equips, o None si FotMob encara no té l'onze oficial."""
    mid = find(home, away, when)
    if not mid:
        return None
    try:
        lu = requests.get(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}", headers=H, timeout=20).json()["content"].get("lineup") or {}
    except Exception:
        return None
    # «standard» = onze oficial; «predicted» i «lastStarting11» (l'onze del partit anterior) no compten
    if (lu.get("lineupType") or "").lower() != "standard" or when - dt.datetime.now(dt.timezone.utc) > dt.timedelta(hours=3):
        return None
    sides = [lu.get("homeTeam") or {}, lu.get("awayTeam") or {}]
    if any(len(s.get("starters") or []) < 11 for s in sides):
        return None
    return [p["name"] for s in sides for p in s["starters"]]


def starters_by_team(home, away, when):
    """{nom de l'equip a FotMob: [titulars]} dels dos equips, o None si encara no hi ha onze oficial."""
    mid = find(home, away, when)
    if not mid:
        return None
    try:
        lu = requests.get(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}", headers=H, timeout=20).json()["content"].get("lineup") or {}
    except Exception:
        return None
    if (lu.get("lineupType") or "").lower() != "standard" or when - dt.datetime.now(dt.timezone.utc) > dt.timedelta(hours=3):
        return None
    sides = [lu.get("homeTeam") or {}, lu.get("awayTeam") or {}]
    if any(len(s.get("starters") or []) < 11 for s in sides):
        return None
    return {s.get("name") or "": [p["name"] for p in s["starters"]] for s in sides}


TOP = re.compile(r"laliga|la liga|segunda|primera division|premier league|serie a|bundesliga|ligue 1|champions league|europa league", re.I)


TOPC = {"ESP", "ENG", "ITA", "GER", "FRA", "INT"}
_SQ = {}


def postponed(days=6, ccode="ESP", top=False, squads=False):
    """Equips (nom de FotMob) amb un partit aplaçat o suspès en els propers `days` dies (lligues del país `ccode`).
    top=True: les lligues dels Fantasy de tots els països (LaLiga, Premier, Serie A, Champions…)."""
    import json as _json
    out = set()
    now = dt.datetime.now(dt.timezone.utc)
    man = _manual(now)
    pages = []
    for k in range(days + 1):
        d = now + dt.timedelta(days=k)
        try:
            pages.append(requests.get(f"https://www.fotmob.com/api/data/matches?date={d:%Y%m%d}", headers=H, timeout=20).json().get("leagues", []))
        except Exception:
            continue

    def leagues():
        for lgs in pages:
            for lg in lgs:
                if ccode and not top and lg.get("ccode") != ccode:
                    continue
                if top and lg.get("ccode") not in TOPC:
                    continue
                # només LaLiga i LaLiga 2 (no la femenina, la Primera RFEF ni la Copa); amb top, també les altres dels Fantasy
                lname = (lg.get("name") or "").lower()
                ok = TOP.search(lname) if top else re.search(r"laliga|la liga|segunda|primera division", lname)
                if not ok or re.search(r"women|femen|f$|rfef|federaci|copa|cup(?! )|u21|u19|youth", lname):
                    continue
                yield lg, lname
    if man and any(not e.get("date") for e in man.values()):  # primer partit de cada equip avisat a mà
        for lg, lname in leagues():
            for m in lg.get("matches", []):
                _man_hit(man, m, lname)
        _manual_save(man)
    for lg, lname in leagues():
        for m in lg.get("matches", []):
            st = m.get("status") or {}
            txt = _json.dumps(st).lower()
            mt = _man_hit(man, m, lname)
            if st.get("cancelled") or "postpon" in txt or '"pp"' in txt or "aplaz" in txt or mt:
                names = [m[side].get("longName") or m[side]["name"] for side in ("home", "away")]
                if any(YOUTH.search(x) for x in names):
                    continue
                print(f"::notice title=aplaçat::{lg.get('name')}: {' - '.join(names)} ({st.get('utcTime')}){' (avís del David)' if mt else ''} {txt[:200]}")
                out.update(names)
                for side, nm in zip(("home", "away"), names):
                    if m[side].get("id"):
                        _SQ.setdefault(nm, m[side]["id"])
    _manual_save(man)
    if squads:
        return {nm: squad(_SQ[nm]) if nm in _SQ else [] for nm in out}
    return out


# Aplaçaments que el David diu per Telegram («/aplaçat Castellón», 5/11) abans que FotMob ho marqui:
# state/postponed_manual.json {equip: {"added": ISO, "date": ISO del partit aplaçat o null}}. S'aplica només al primer
# partit de l'equip després de l'avís (el de la data desada) i s'esborra quan aquell dia ja ha passat.
def _manual(now):
    try:
        from bot.web import load_json
        man = load_json("postponed_manual.json", {})
    except Exception:
        return {}
    for t, e in list(man.items()):
        if e.get("date") and dt.datetime.fromisoformat(e["date"]) < now - dt.timedelta(hours=6):
            del man[t]
    return man


def add_manual(team):
    from bot.web import load_json, save_json
    man = load_json("postponed_manual.json", {})
    man[team] = {"added": dt.datetime.now(dt.timezone.utc).isoformat(), "date": None}
    save_json("postponed_manual.json", man)


def _man_hit(man, m, lname):
    if not man or not re.search(r"laliga|la liga|segunda|primera division|premier|serie a|champions|europa", lname):
        return None
    try:
        D = dt.datetime.fromisoformat(((m.get("status") or {}).get("utcTime") or "").replace("Z", "+00:00"))
    except Exception:
        return None
    for t, e in man.items():
        names = [m[side].get("longName") or m[side].get("name") or "" for side in ("home", "away")]
        if not any(team_score(t, n) > 0 for n in names) or any(YOUTH.search(n) for n in names):
            continue
        if e.get("date"):
            if abs((D - dt.datetime.fromisoformat(e["date"])).total_seconds()) < 3 * 3600:
                return t
        elif D > dt.datetime.fromisoformat(e["added"]) - dt.timedelta(hours=3):
            if not e.get("_cand") or D < dt.datetime.fromisoformat(e["_cand"]):
                e["_cand"] = D.isoformat()
    return None


def _manual_save(man):
    if not man:
        return
    changed = False
    for e in man.values():
        if not e.get("date") and e.get("_cand"):
            e["date"] = e.pop("_cand")
            changed = True
        e.pop("_cand", None)
    if changed:
        try:
            from bot.web import save_json
            save_json("postponed_manual.json", man)
        except Exception:
            pass


def squad(team_id):
    """Noms dels jugadors de la plantilla d'un equip de FotMob."""
    try:
        d = requests.get(f"https://www.fotmob.com/api/data/teams?id={team_id}", headers=H, timeout=20).json()
    except Exception:
        return []
    out = []
    for grp in (d.get("squad") or {}).get("squad") or []:
        for p in grp.get("members") or []:
            if p.get("name"):
                out.append(p["name"])
    return out



if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--aplaca":
        add_manual(" ".join(sys.argv[2:]))
    print("::notice title=aplaçats::" + ", ".join(sorted(postponed())))
    for t, ns in postponed(days=10, top=True, squads=True).items():
        print(f"::notice title=plantilla {t}::{len(ns)}: {', '.join(ns[:40])}")
