"""Planificador (cada 30 minuts, molt lleuger: sense navegador).

Mira els tancaments i decideix què cal fer en els propers 30 minuts:
  - Matí (primera execució de les 9 h, hora de Madrid): Predicted11 i FutbolFantasy de les jornades que tanquen avui.
  - Predicted11: última revisió 50 min abans del tancament (que és 2 h abans del primer partit).
  - FutbolFantasy: revisió final 50 min abans del primer partit (amb els onzes oficials si ja hi són).
Escriu state/actions.json: [{"at": ISO UTC, "do": "p11"|"ff"|"fffinal", "comp": ...}]
"""
import datetime as dt
import json
import os
import re

import requests
from zoneinfo import ZoneInfo

from bot.web import STATE, load_json

MADRID = ZoneInfo("Europe/Madrid")
UTC = dt.timezone.utc
P11 = ["laliga", "laliga2", "premier-league", "serie-a", "champions"]
FF_LABEL = {"laliga": "LaLiga ·", "laliga2": "LaLiga 2 ·", "premier-league": "Premier League ·",
            "serie-a": "Serie A ·", "champions": "Champions ·", "europa-league": "Europa League ·"}
LEAD = dt.timedelta(minutes=50)
WINDOW = dt.timedelta(minutes=30)


def p11_deadline(comp):
    h = requests.get(f"https://www.predicted11.com/es/{comp}", headers={"User-Agent": "Mozilla/5.0"}, timeout=30).text
    m = re.search(r'data-countdown-end="(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)', h)
    return dt.datetime.fromisoformat(m.group(1)).replace(tzinfo=UTC) if m else None


def ff_deadline(comp, ffd):
    pref = FF_LABEL[comp]
    for label, end in ffd.items():
        if label.startswith(pref) and not (comp == "laliga" and label.startswith("LaLiga 2")):
            return dt.datetime.strptime(end, "%Y-%m-%d %H:%M:%S").replace(tzinfo=MADRID).astimezone(UTC)
    return None


def plan(now=None):
    now = now or dt.datetime.now(UTC)
    local = now.astimezone(MADRID)
    morning = local.hour == 9 and local.minute < 30
    ffd = load_json("deadlines_ff.json")
    acts, info = [], []

    def soon(t):
        return t is not None and now <= t < now + WINDOW

    ff_today = False
    for comp in P11 + ["europa-league"]:
        D = None
        if comp in P11:
            try:
                D = p11_deadline(comp)
            except Exception as e:
                info.append(f"{comp}: error llegint Predicted11 ({e})")
        K = ff_deadline(comp, ffd) or (D + dt.timedelta(hours=2) if D else None)
        if D and D > now:
            info.append(f"{comp}: Predicted11 tanca {D.astimezone(MADRID):%a %d %H:%M}")
            if morning and D.astimezone(MADRID).date() == local.date():
                acts.append({"at": now.isoformat(), "do": "p11", "comp": comp})
            if soon(D - LEAD):
                acts.append({"at": (D - LEAD).isoformat(), "do": "p11", "comp": comp})
        if K and K > now:
            info.append(f"{comp}: FutbolFantasy tanca {K.astimezone(MADRID):%a %d %H:%M}")
            if K.astimezone(MADRID).date() == local.date():
                ff_today = True
            if soon(K - LEAD):
                acts.append({"at": (K - LEAD).isoformat(), "do": "fffinal", "comp": comp})
    if morning and (ff_today or not ffd):
        acts.append({"at": now.isoformat(), "do": "ff", "comp": None})
    # Un cop per setmana (dilluns al matí) es refresquen els tancaments de FutbolFantasy.
    if morning and local.weekday() == 0 and not any(a["do"] == "ff" for a in acts):
        acts.append({"at": now.isoformat(), "do": "ff", "comp": None})
    return acts, info


if __name__ == "__main__":
    acts, info = plan()
    (STATE / "actions.json").write_text(json.dumps(acts), encoding="utf-8")
    print("\n".join(info))
    print("Accions:", acts)
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"has={'true' if acts else 'false'}\n")
    if acts:
        print("::notice title=plan::" + " | ".join(f"{a['do']} {a['comp'] or ''} {a['at'][11:16]}Z" for a in acts))
