"""FotMob: onze oficial d'un partit (sovint surt abans que a Sorare, quan el club el publica).

FotMob dona també onzes «predicted»: només compten quan lineupType no és «predicted» i hi ha 11 titulars per equip.
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
    if (lu.get("lineupType") or "").lower() == "predicted":
        return None
    sides = [lu.get("homeTeam") or {}, lu.get("awayTeam") or {}]
    if any(len(s.get("starters") or []) < 11 for s in sides):
        return None
    return [p["name"] for s in sides for p in s["starters"]]
