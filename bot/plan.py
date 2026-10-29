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
import time

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
            # Quiniela: recordatori per Telegram el dia abans i 5 h abans del tancament (només si està buida)
            for lead in (26, 5):
                k = f"quinrem:{comp}:{D.isoformat()}:{lead}"
                if due(k, D - dt.timedelta(hours=lead), D - dt.timedelta(hours=1)):
                    acts.append({"key": k, "at": max(D - dt.timedelta(hours=lead), now).isoformat(), "do": "quinrem", "comp": comp,
                                 "deadline": D.isoformat(), "text": f"{D.astimezone(MADRID):%a %d %H:%M}"})
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
    # Mister: revisió abans de la resolució del mercat (5:00): retira pujes i ven els que han baixat de %
    pre_t = local.replace(hour=4, minute=15, second=0, microsecond=0).astimezone(UTC)
    k = f"mister-pre:{local.date()}"
    if due(k, pre_t, pre_t + dt.timedelta(minutes=40)):
        add(k, pre_t, "mister", "pre", pre_t + dt.timedelta(minutes=40))
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
    # Extra de la Copa del Rey: revisió 40 min abans que tanqui (onzes oficials dels primers partits)
    if ffd.get("Extras"):
        CT = dt.datetime.strptime(ffd["Extras"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=MADRID).astimezone(UTC)
        k = f"copa-final:{CT.isoformat()}"
        if due(k, CT - dt.timedelta(minutes=40), CT):
            add(k, CT - dt.timedelta(minutes=40), "copa", None, CT)
    # Sorare Pro: omplir quan surt l'impacte previst (dimecres i diumenge 21:15), revisió 2 h abans i revisió final + Arena 40 min abans
    for wd in (2, 6):
        if local.weekday() == wd:
            t = local.replace(hour=21, minute=15, second=0, microsecond=0).astimezone(UTC)
            k = f"sorare-fill:{local.date()}"
            if due(k, t, t + dt.timedelta(hours=3)):
                add(k, t, "sorare", "fill", t + dt.timedelta(hours=3))
    sf = load_json("sorare_fixture.json", {})
    if sf.get("cutoff"):
        C = dt.datetime.fromisoformat(sf["cutoff"].replace("Z", "+00:00"))
        if C > now:
            info.append(f"Sorare GW{sf.get('gw')}: tanca {C.astimezone(MADRID):%a %d %H:%M}")
        # revisió cada matí (9:30) els dies abans del tancament: dijous i divendres (tanca divendres), dilluns i dimarts (tanca dimarts)
        mt = local.replace(hour=9, minute=30, second=0, microsecond=0).astimezone(UTC)
        if mt < C - dt.timedelta(hours=2) and C - mt < dt.timedelta(hours=48):
            k = f"sorare-mati:{sf['slug']}:{local.date()}"
            if due(k, mt, C - dt.timedelta(hours=2)):
                add(k, mt, "sorare", "fill", C - dt.timedelta(hours=2))
        for lead, mode in ((dt.timedelta(hours=2), "fill"), (dt.timedelta(minutes=40), "final")):
            k = f"sorare-{mode}:{sf['slug']}:{int(lead.total_seconds())}"
            if due(k, C - lead, C - dt.timedelta(minutes=5)):
                add(k, C - lead, "sorare", mode, C - dt.timedelta(minutes=5))
    # Sorare: porters amb 10–79% → avís 1 h 15 min abans del partit i comprovació de l'onze oficial
    for g in load_json("sorare_gkwatch.json", {}).get("gks", []):
        G = dt.datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
        for mins in (75, 55, 40, 25, 12):
            k = f"sorarexi:{g['game']}:{mins}"
            if due(k, G - dt.timedelta(minutes=mins), G):
                add(k, G - dt.timedelta(minutes=mins), "sorarexi", f"{g['game']}|{mins}", G)
    for key_, v in load_json("sorare_gkarena.json", {}).items():
        if v.get("status") == "proposed":
            S = dt.datetime.fromisoformat(v["submit_at"])
            k = f"sorarearena:{key_}"
            if due(k, S, S + dt.timedelta(minutes=5)):
                add(k, S, "sorarearena", key_, S + dt.timedelta(minutes=5))
    # Sorare: Decisive Picker (missió diària) al matí (10:00) i 15 min abans de cada partit amb candidats (onzes oficials)
    t10 = local.replace(hour=10, minute=0, second=0, microsecond=0).astimezone(UTC)
    k = f"soraremission:{local.date()}"
    if due(k, t10, t10 + dt.timedelta(hours=12)):
        add(k, t10, "soraremission", "mati", t10 + dt.timedelta(hours=12))
    for gd in load_json("sorare_missions.json", {}).get("games", []):
        G = dt.datetime.fromisoformat(gd.replace("Z", "+00:00"))
        k = f"soraremission:{gd}"
        if due(k, G - dt.timedelta(minutes=15), G):
            add(k, G - dt.timedelta(minutes=15), "soraremission", gd, G)
    k = f"ff-mati:{local.date()}"
    if due(k, morning_t, ff_today or now + dt.timedelta(days=1)):
        add(k, morning_t, "ff", None, ff_today or now + dt.timedelta(days=1))
    try:  # els missatges de Telegram mai han d'aturar el planificador
        acts += telegram_commands(now)
    except Exception as e:
        info.append(f"Telegram: error llegint missatges ({type(e).__name__}: {e})")
    return acts, info


def telegram_commands(now):
    """Llegeix els missatges nous del xat de Telegram. «/quiniela [competició] resultats» → acció immediata."""
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        return []
    from bot.quiniela import split_comp
    st = load_json("tg_offset.json", {"offset": 0})
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params={"offset": st["offset"], "timeout": 0}, timeout=20).json()
    except Exception as e:
        print("telegram getUpdates:", e)
        return []
    out = []
    for u in r.get("result", []):
        m = u.get("message") or {}
        # codi de 6 xifres recent (entrada de Sorare): no el consumim, és per a bot/sorare.py
        if re.fullmatch(r"\d{6}", re.sub(r"\s", "", m.get("text") or "")) and time.time() - m.get("date", 0) < 600:
            break
        st["offset"] = u["update_id"] + 1
        if str((m.get("chat") or {}).get("id")) != str(chat):
            continue  # només el xat del David
        t = (m.get("text") or "").strip()
        if re.fullmatch(r"s[ií]\W*|yes\W*|ok\W*|endavant\W*|fes-la\W*|fes-les\W*", t.lower()):  # «sí» per a una Arena de Sorare
            from bot.web import save_json as _sj
            _sj("sorare_yes.json", (load_json("sorare_yes.json", []) + [m.get("date", 0)])[-20:])
            continue
        from bot.quiniela import parse_grok
        grok = parse_grok(t)
        if grok:  # taula del Grok enganxada (amb o sense /quiniela): una acció per competició
            for c, picks in grok.items():
                out.append({"key": f"quiniela:{u['update_id']}:{c}", "at": now.isoformat(), "do": "quiniela", "comp": c,
                            "deadline": (now + dt.timedelta(hours=6)).isoformat(),
                            "text": "; ".join(f"{h} {a}-{b} {v}" for h, v, a, b in picks)})
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat, "text": "👍 Rebudes: " + ", ".join(f"{c} ({len(p)} partits)" for c, p in grok.items()) + ". Les poso ara."}, timeout=20)
            continue
        if not t.lower().startswith("/quiniela"):
            continue
        comp, rest = split_comp(t[len("/quiniela"):].split("@", 1)[-1] if t[len("/quiniela"):].startswith("@") else t[len("/quiniela"):])
        comp = comp or load_json("quinrem_last.json", {}).get("comp")
        if not comp:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": "⚠️ Digues la competició: /quiniela serie-a ..."}, timeout=20)
            continue
        out.append({"key": f"quiniela:{u['update_id']}", "at": now.isoformat(), "do": "quiniela", "comp": comp,
                    "deadline": (now + dt.timedelta(hours=6)).isoformat(), "text": rest})
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": f"👍 Rebuda la quiniela de {comp}. La poso ara."}, timeout=20)
    from bot.web import save_json
    save_json("tg_offset.json", st)
    return out


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

