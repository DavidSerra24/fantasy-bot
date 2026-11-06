"""Quiniela (la de LAE) amb el mètode del David, a partir de l'«Análisis» d'eduardolosilla.es (decisió del David, 7/11).

Cada partit té 5 columnes (BASE, PROB., POS., DIFÍCIL, BOMBA) per a cada filtre (Quinielista, Probables, LAE, Técnicos):
- Columna 1: el filtre amb més X a la columna PROB. (un doble com «X2» compta com a X); aquells partits → X.
  La resta, la BASE de Técnicos. Empat de filtres: Probables → LAE → Quinielista → Técnicos.
- Columna 2: Técnicos sencer: on hi ha signe a PROB., aquell signe (si és doble, la X primer); si no, la BASE.
- Ple al 15: BASE de Técnicos (gols del local i del visitant), com el David.
- Elige 8 (sobre la columna 1): els 8 partits amb el signe més probable segons Probables (quotes); el David ho feia a l'atzar.
El bot només ho envia per Telegram 2 h abans que tanqui (= 15 min abans del primer partit): no juga ni paga res.
Dades: la taula de la web (Playwright). Hores dels partits: static.eduardolosilla.es/cache/analisis<temp>_<jornada>.json.
Ús: python -m bot.losilla [--send]
"""
import datetime as dt
import re
import sys
from zoneinfo import ZoneInfo

import requests

from bot.web import load_json, save_json

MAD = ZoneInfo("Europe/Madrid")
UTC = dt.timezone.utc
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36",
     "Accept": "application/json, text/plain, */*", "Origin": "https://www.eduardolosilla.es", "Referer": "https://www.eduardolosilla.es/"}
FILTERS = ["QUINIELISTA", "PROBABLES", "LAE", "TÉCNICOS"]
TIE = ["PROBABLES", "LAE", "QUINIELISTA", "TÉCNICOS"]
DAYS = {"LUN": 0, "MAR": 1, "MIE": 2, "MIÉ": 2, "JUE": 3, "VIE": 4, "SAB": 5, "SÁB": 5, "DOM": 6}
CLOSE_BEFORE = dt.timedelta(minutes=15)  # l'app tanca 15 min abans del primer partit (13:45 per a un partit a les 14:00)


def schedule():
    """{"jornada", "temporada", "kick": ISO UTC del primer partit, "matches": [...]} de la propera jornada (sense navegador)."""
    info = requests.get("https://static.eduardolosilla.es/cache/infoDnp.json", headers=H, timeout=30).json()
    j, t = info["idJornada"], info["idTemporada"]
    ref = dt.datetime.fromisoformat(info["cierreDnp"].replace("Z", "+00:00")).astimezone(MAD)  # tancament de les penyes: el dia de referència
    an = requests.get(f"https://static.eduardolosilla.es/cache/analisis{t}_{j}.json", headers=H, timeout=30).json()
    kicks = []
    for p in an.get("partidos") or []:
        d, h = (p.get("dia") or "").upper(), p.get("hora") or ""
        if d not in DAYS or ":" not in h:
            continue
        day = ref.date() + dt.timedelta(days=(DAYS[d] - ref.weekday()) % 7)
        hh, mm = map(int, h.split(":"))
        kicks.append(dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=MAD))
    if not kicks:
        raise RuntimeError("no trobo les hores dels partits")
    out = {"jornada": j, "temporada": t, "kick": min(kicks).astimezone(UTC).isoformat(),
           "matches": [f"{p['local']} - {p['visitante']}" for p in an.get("partidos") or []]}
    save_json("losilla.json", dict(load_json("losilla.json", {}), **out, at=dt.datetime.now(UTC).isoformat()))
    return out


ROWS = """() => [...document.querySelectorAll('.c-porcentajes-analisis tr.c-porcentajes-analisis__partido')].map(tr =>
    [...tr.querySelectorAll('td')].map(td => td.textContent.trim()))"""


def tables():
    """{filtre: [[BASE, PROB, POS, DIF, BOMBA] per a cada fila]} (14 partits + 2 files del ple: local i visitant)."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(locale="es-ES")
        pg.goto("https://www.eduardolosilla.es/quiniela/ayudas/analisis", wait_until="networkidle", timeout=90000)
        pg.wait_for_selector(".c-porcentajes-analisis tr.c-porcentajes-analisis__partido", timeout=60000)
        for v, f in enumerate(FILTERS):
            prev = pg.evaluate(ROWS)
            pg.select_option("select.c-selector__select >> nth=0", str(v))
            rows = prev
            for _ in range(20):  # espera que la taula canviï (o 6 s, si el filtre dona el mateix)
                pg.wait_for_timeout(300)
                rows = pg.evaluate(ROWS)
                if rows != prev and len(rows) >= 15:
                    break
            out[f] = rows
            txt = pg.inner_text("body")  # taula «% <FILTRE>»: %1 %X %2 dels 14 partits (després, el ple)
            i, j = txt.find("%2"), txt.find("CSV")
            nums = [int(x) for x in re.findall(r"\b\d{1,3}\b", txt[i + 2:j])] if 0 <= i < j else []
            out.setdefault("_pct", {})[f] = [nums[k:k + 3] for k in range(0, 42, 3)] if len(nums) >= 42 else None
        b.close()
    if any(len(r) < 14 for k, r in out.items() if k != "_pct"):
        raise RuntimeError("la taula d'Análisis no té els 14 partits")
    return out


def pick(sign):
    """Un doble («X2», «1X») → la X primer; si no n'hi ha, el primer signe."""
    sign = (sign or "").strip()
    return "X" if "X" in sign else sign[:1]


def build(T):
    xs = {f: [i for i, r in enumerate(T[f][:14]) if "X" in r[1]] for f in FILTERS}
    best = max(TIE, key=lambda f: (len(xs[f]), -TIE.index(f)))
    tec = T["TÉCNICOS"]
    c1 = ["X" if i in xs[best] else pick(tec[i][0]) for i in range(14)]
    c2 = [pick(tec[i][1]) if tec[i][1] else pick(tec[i][0]) for i in range(14)]
    pleno = f"{tec[14][0] or '?'}-{tec[15][0] or '?'}" if len(tec) >= 16 else "?"
    # Elige 8 (sobre la columna 1): els 8 partits on el signe de la columna 1 és més probable segons Probables (les quotes
    # de les cases d'apostes); si no hi ha els % de Probables, els de LAE
    pct, src = None, None
    for f in ("PROBABLES", "LAE", "QUINIELISTA"):
        if (T.get("_pct") or {}).get(f):
            pct, src = T["_pct"][f], f
            break
    e8 = []
    if pct:
        prob = [pct[i]["1X2".index(c1[i])] if c1[i] in "1X2" and c1[i] else 0 for i in range(14)]
        e8 = sorted(sorted(range(14), key=lambda i: -prob[i])[:8])
        e8 = [(i, prob[i]) for i in e8]
    return {"best": best, "xcount": {f: len(v) for f, v in xs.items()}, "c1": c1, "c2": c2, "pleno": pleno, "e8": e8, "e8src": src}


def message(sch, R, T):
    close = dt.datetime.fromisoformat(sch["kick"]).astimezone(MAD) - CLOSE_BEFORE
    names = sch.get("matches") or []
    dia = ["dilluns", "dimarts", "dimecres", "dijous", "divendres", "dissabte", "diumenge"][close.weekday()]
    lines = [f"🎫 Quiniela J{sch['jornada']} · tanca {dia} a les {close:%H:%M}. Proposta amb el teu mètode:",
             f"Col. 1: X on {R['best'].capitalize()} té X a PROB. ({R['xcount'][R['best']]}); la resta, BASE de Técnicos",
             "Col. 2: Técnicos (PROB. si n'hi ha; si no, BASE)", ""]
    for i in range(14):
        n = names[i] if i < len(names) else f"Partit {i + 1}"
        lines.append(f"{i + 1}. {n.title()}: {R['c1'][i]} | {R['c2'][i]}")
    lines += [f"15. Ple (BASE de Técnicos): {R['pleno']}",
              "", "X a PROB. per filtre: " + ", ".join(f"{f.capitalize()} {n}" for f, n in R["xcount"].items()),
              ("Elige 8 (columna 1, els 8 signes més probables segons " + R["e8src"].capitalize() + "): "
               + ", ".join(f"{i + 1} ({R['c1'][i]} {p}%)" for i, p in R["e8"]) if R["e8"] else "Elige 8: no he pogut llegir els %, fes-lo a l'atzar")]
    return "\n".join(lines)


def run(send=True):
    from bot.notify import telegram
    sch = schedule()
    T = tables()
    R = build(T)
    msg = message(sch, R, T)
    for f in FILTERS:
        print(f"::notice title=losilla {f}::" + " | ".join(" ".join(c or "-" for c in r) for r in T[f]))
    print("::notice title=losilla::" + msg.replace("\n", " ¶ "))
    if send:
        telegram(msg)
        st = load_json("losilla.json", {})
        st["sent"] = sorted(set(st.get("sent", [])) | {f"{sch['temporada']}_{sch['jornada']}"})
        save_json("losilla.json", st)
    return msg


if __name__ == "__main__":
    run(send="--send" in sys.argv)
