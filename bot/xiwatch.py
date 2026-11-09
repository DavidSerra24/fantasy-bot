"""Avís de titular (manual, mister.yml amb bot.xiwatch "Nom|Equip" "Nom|Equip" …): espera els onzes oficials (FotMob)
dels partits de cada jugador, per ordre d'hora, i avisa per Telegram del primer que surt titular («posa'l»). Si un no
és titular, passa al següent. Fet per al David (8/11): substitut de Maffeo a Fentaniños, Bellerín o Andrés García.
"""
import datetime as dt
import sys
import time

import requests

from bot.ff import name_score, team_score
from bot.fotmob import H, starters_by_team
from bot.notify import telegram
from zoneinfo import ZoneInfo

M = ZoneInfo("Europe/Madrid")


def next_match(team):
    now = dt.datetime.now(dt.timezone.utc)
    for k in range(3):
        d = now + dt.timedelta(days=k)
        try:
            lgs = requests.get(f"https://www.fotmob.com/api/data/matches?date={d:%Y%m%d}", headers=H, timeout=20).json().get("leagues", [])
        except Exception:
            continue
        for lg in lgs:
            for m in lg.get("matches", []):
                st = m.get("status") or {}
                names = [m[s].get("longName") or m[s]["name"] for s in ("home", "away")]
                if st.get("finished") or st.get("started") or not any(team_score(n, team) > 0 for n in names):
                    continue
                when = dt.datetime.fromisoformat(st["utcTime"].replace("Z", "+00:00"))
                if when > now:
                    return names[0], names[1], when
    return None


def main(specs):
    repl = next((a.split("=", 1)[1] for a in specs if a.startswith("--en-lloc=")), "Maffeo")
    specs = [a for a in specs if not a.startswith("--")]
    items = []
    for sp in specs:
        nm, team = sp.split("|")
        m = next_match(team)
        if m:
            items.append((m[2], nm, team, m))
        else:
            print(f"::warning title=xiwatch::no trobo el proper partit de {team}")
    items.sort()
    for when, nm, team, (h, a, w) in items:
        print(f"::notice title=xiwatch::{nm} ({team}): {h}-{a} {w.astimezone(M):%a %H:%M}")
        st = None
        while dt.datetime.now(dt.timezone.utc) < when:
            st = starters_by_team(h, a, w)
            if st:
                break
            time.sleep(180)
        if not st:
            print(f"::notice title=xiwatch resultat::{nm} sense onze")
            telegram(f"⏱️ {nm}: el partit {h}–{a} ha començat i no he vist l'onze oficial.")
            continue
        side = max(st, key=lambda t: team_score(t, team))
        ok = any(name_score(alt.strip(), s) >= 75 for alt in nm.split("/") for s in st[side])  # «Nom/Àlies»
        if ok:
            print(f"::notice title=xiwatch resultat::{nm} TITULAR")
            telegram(f"✅ {nm} és TITULAR ({h}–{a}, {w.astimezone(M):%H:%M}). Posa'l al Mister en lloc de {repl}.")
            return
        print(f"::notice title=xiwatch resultat::{nm} NO titular")
        telegram(f"❌ {nm} NO és titular ({h}–{a}). " + ("Miro el següent." if (when, nm) != items[-1][:2] else ("Cap dels dos surt titular." if len(items) > 1 else f"No canviïs {repl}.")))


if __name__ == "__main__":
    main(sys.argv[1:])
