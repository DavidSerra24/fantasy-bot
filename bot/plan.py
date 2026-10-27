"""Planificador (cada 30 minuts, molt lleuger: sense navegador).

Mira els tancaments i decideix què cal fer en els propers 30 minuts:
  - Matí (9 h, hora de Madrid), cada dia: Predicted11 de totes les jornades obertes i FutbolFantasy dels jocs buits
    (els extres de LaLiga, només el dia que tanquen).
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
LEAD = dt.timedelta(minutes=50)       # FutbolFantasy: revisió final (onzes oficials)
LEAD_P11 = dt.timedelta(minutes=50)   # Predicted11: última revisió (si GitHub comença tard, no passa res)
WINDOW = dt.timedelta(minutes=60)  # s'agafa l'acció si toca dins la propera hora i s'espera fins a l'hora exacta


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


KICK = {}  # competició → primer partit de la propera jornada (es desa a state/mister_kickoffs.json)


def plan(now=None, done=None):
    """Retorna les accions pendents. Una acció és pendent si la seva hora ja ha arribat (o arriba
    en els propers 30 min), el joc encara no ha tancat i no s'ha fet abans (done)."""
    now = now or dt.datetime.now(UTC)
    done = set(done or [])
    local = now.astimezone(MADRID)
    ffd = load_json("deadlines_ff.json")
    acts, info = [], []

    def due(key, t, deadline):
        if key in done or deadline <= now:
            return False
        return t < now + WINDOW

    def add(key, t, do, comp, deadline):
        acts.append({"key": key, "at": max(t, now).isoformat(), "do": do, "comp": comp, "deadline": deadline.isoformat()})

    morning_t = local.replace(hour=9, minute=0, second=0, microsecond=0).astimezone(UTC)
    ff_today = None
    for comp in P11 + ["europa-league"]:
        D = None
        if comp in P11:
            try:
                D = p11_deadline(comp)
            except Exception as e:
                info.append(f"{comp}: error llegint Predicted11 ({e})")
        K = ff_deadline(comp, ffd) or (D + dt.timedelta(hours=2) if D else None)
        if comp in ("laliga", "laliga2") and (D or K):
            KICK[comp] = (D + dt.timedelta(hours=2) if D else K).isoformat()  # primer partit de la jornada (Mister)
        if D and D > now:
            info.append(f"{comp}: Predicted11 tanca {D.astimezone(MADRID):%a %d %H:%M}")
            # cada matí s'omple (o s'actualitza) tot el que és obert; la revisió final és sempre 50 min abans
            if True:
                k = f"p11-mati:{comp}:{local.date()}"
                if due(k, morning_t, D):
                    add(k, morning_t, "p11", comp, D)
            k = f"p11-final:{comp}:{D.isoformat()}"
            if due(k, D - LEAD_P11, D):
                add(k, D - LEAD_P11, "p11", comp, D)
        if K and K > now:
            info.append(f"{comp}: FutbolFantasy tanca {K.astimezone(MADRID):%a %d %H:%M}")
            if K.astimezone(MADRID).date() == local.date():
                ff_today = K if not ff_today else min(ff_today, K)
            k = f"ff-final:{comp}:{K.isoformat()}"
            if due(k, K - LEAD, K):
                add(k, K - LEAD, "fffinal", comp, K)
    # Mister: pujes cada dia després de la renovació del mercat (5:00)
    mister_t = local.replace(hour=6, minute=0, second=0, microsecond=0).astimezone(UTC)
    k = f"mister:{local.date()}"
    if due(k, mister_t, mister_t + dt.timedelta(hours=12)):
        add(k, mister_t, "mister", None, mister_t + dt.timedelta(hours=12))
    # Mister: ofertes pels jugadors en venda (arriben a les 17:00 i a les 5:00)
    for hh in (5, 17):
        off_t = local.replace(hour=hh, minute=10, second=0, microsecond=0).astimezone(UTC)
        k = f"misteroff:{local.date()}:{hh}"
        if due(k, off_t, off_t + dt.timedelta(hours=10)):
            add(k, off_t, "misteroff", None, off_t + dt.timedelta(hours=10))
    # Mister: alineació cada matí (6:40) i revisió final 45 min abans del primer partit de cada lliga
    xi_t = local.replace(hour=6, minute=40, second=0, microsecond=0).astimezone(UTC)
    k = f"misterxi:{local.date()}"
    if due(k, xi_t, xi_t + dt.timedelta(hours=12)):
        add(k, xi_t, "misterxi", None, xi_t + dt.timedelta(hours=12))
    for comp, iso in KICK.items():
        kt = dt.datetime.fromisoformat(iso)
        k = f"misterxi-final:{comp}:{iso}"
        if due(k, kt - dt.timedelta(minutes=45), kt):
            add(k, kt - dt.timedelta(minutes=45), "misterxi", comp, kt)
    k = f"ff-mati:{local.date()}"
    if due(k, morning_t, ff_today or now + dt.timedelta(days=1)):
        add(k, morning_t, "ff", None, ff_today or now + dt.timedelta(days=1))
    return acts, info


if __name__ == "__main__":
    done = load_json("done.json", [])
    acts, info = plan(done=done)
    (STATE / "actions.json").write_text(json.dumps(acts), encoding="utf-8")
    if KICK:
        (STATE / "mister_kickoffs.json").write_text(json.dumps(KICK), encoding="utf-8")
    print("\n".join(info))
    print("Accions:", acts)
    if os.getenv("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"has={'true' if acts else 'false'}\n")
    if acts:
        print("::notice title=plan::" + " | ".join(f"{a['do']} {a['comp'] or ''} {a['at'][11:16]}Z" for a in acts))

