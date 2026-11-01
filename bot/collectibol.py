"""Collectibol: avís per Telegram quan un dels clubs amb llicència guanya el seu partit (decisió del David, 1/11).

Collectibol regala un sobre quan un d'aquests equips guanya: el codi surt minuts després a la Story d'Instagram i de
Facebook. El bot no pot llegir les Stories ni bescanviar el codi (entrada amb Google/Apple): només avisa al moment
que s'acaba el partit perquè el David estigui atent a la Story.

Partits i resultats de FotMob (`/api/data/matches?date=`). Cada equip s'identifica primer pel nom i el país de la
seva lliga (per no confondre'l amb un altre amb el mateix nom, p. ex. l'Olimpia d'Hondures o el Barcelona SC de
l'Equador); després es recorda el seu id de FotMob (`state/collectibol.json`) i ja es reconeix a qualsevol competició.
"""
import datetime as dt
import re
import unicodedata

import requests

from bot.notify import telegram
from bot.web import load_json, save_json

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
# clubs amb llicència a Collectibol (setembre 2026): nom a FotMob → país de la seva lliga
TEAMS = {"Barcelona": "ESP", "Atletico Madrid": "ESP", "Real Betis": "ESP", "Valencia": "ESP", "Girona": "ESP", "Espanyol": "ESP",
         "Boca Juniors": "ARG", "Monaco": "FRA", "Toulouse": "FRA", "Como": "ITA", "Olimpia": "PRY"}
IG = "https://www.instagram.com/collectibol/"
YOUTH = re.compile(r"\b(u\d\d|ii|b|women|w|femenino|feminine|reserves?|youth|juvenil)\b", re.I)


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


NAMES = {norm(k): k for k in TEAMS}


def day_matches(day):
    try:
        lgs = requests.get(f"https://www.fotmob.com/api/data/matches?date={day:%Y%m%d}", headers=H, timeout=20).json().get("leagues", [])
    except Exception as e:
        print(f"::warning title=collectibol::FotMob: {str(e)[:150]}")
        return []
    return [(lg.get("ccode"), lg.get("name"), m) for lg in lgs for m in lg.get("matches", [])]


def ours(st, ccode, side):
    """Nom del club de Collectibol si aquest equip ho és (i aprèn el seu id de FotMob)."""
    ids = st.setdefault("ids", {})
    tid, name = str(side.get("id")), side.get("name") or ""
    if tid in ids:
        return ids[tid]
    if YOUTH.search(name):
        return None
    club = NAMES.get(norm(name))
    if club and ccode == TEAMS[club]:
        ids[tid] = club
        return club
    return None


def scan(now=None):
    """Partits d'avui i demà dels clubs de Collectibol → state/collectibol.json["games"] (el planificador hi posa les
    comprovacions del final del partit)."""
    now = now or dt.datetime.now(dt.timezone.utc)
    st = load_json("collectibol.json", {})
    games = st.setdefault("games", {})
    for d in (now - dt.timedelta(days=1), now, now + dt.timedelta(days=1)):
        for cc, lgname, m in day_matches(d):
            for side in ("home", "away"):
                club = ours(st, cc, m.get(side) or {})
                if not club:
                    continue
                k = str(m.get("id"))
                t = (m.get("status") or {}).get("utcTime") or ""
                if k not in games:
                    games[k] = {"club": club, "side": side, "kick": t, "home": m["home"]["name"], "away": m["away"]["name"],
                                "league": lgname, "day": f"{d:%Y%m%d}"}
                else:
                    games[k]["kick"] = t or games[k]["kick"]
    cut = (now - dt.timedelta(days=2)).isoformat()
    st["games"] = {k: g for k, g in games.items() if (g.get("kick") or "9") >= cut[:10]}  # fora els de fa més de 2 dies
    save_json("collectibol.json", st)
    return st["games"]


def check(mid):
    """Si el partit ha acabat i el club de Collectibol ha guanyat → avís per Telegram (una sola vegada)."""
    st = load_json("collectibol.json", {})
    g = (st.get("games") or {}).get(mid)
    if not g or g.get("done"):
        return
    m = next((m for _, _, m in day_matches(dt.datetime.strptime(g["day"], "%Y%m%d")) if str(m.get("id")) == mid), None)
    if not m:
        return
    s = m.get("status") or {}
    if s.get("cancelled"):
        g["done"] = "cancel·lat"
    elif s.get("finished"):
        hs, as_ = m["home"].get("score"), m["away"].get("score")
        mine, other = (hs, as_) if g["side"] == "home" else (as_, hs)
        pens = (s.get("reason") or {}).get("penalties")  # eliminatòries: guanyar als penals
        if pens and mine == other:
            mine, other = (pens[0], pens[1]) if g["side"] == "home" else (pens[1], pens[0])
        rival = g["away"] if g["side"] == "home" else g["home"]
        if mine is not None and other is not None and mine > other:
            telegram(f"🃏 Collectibol: el {g['club']} ha guanyat {s.get('scoreStr') or f'{hs}-{as_}'} contra el {rival}"
                     f" ({g.get('league')}). Atent a la Story amb el codi del sobre: {IG}")
            g["done"] = "guanyat"
        else:
            g["done"] = "no guanya"
        print(f"::notice title=collectibol::{g['home']} - {g['away']}: {s.get('scoreStr')} → {g['done']}")
    st["games"][mid] = g
    save_json("collectibol.json", st)


if __name__ == "__main__":
    import json
    print(json.dumps(scan(), ensure_ascii=False, indent=1)[:3500])
