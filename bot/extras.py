"""Jocs extres de FutbolFantasy (LaLiga): Trío revulsivo, Trío antagonista i Resiliencia de portero.

Criteris (acordats amb el David):
  - Revulsivo: jugadors amb la marca "R" de revulsiu de FutbolFantasy, ≤50% de titularitat i sense lesió;
    els de millor mitjana de punts (desempat: menys % de titularitat).
  - Antagonista: els 2 porters titulars (≥70% de futbolfantasy.com) amb MENYS punts projectats + el jugador de camp titular (≥70%)
    amb més targetes grogues per partit.
  - Resiliencia de portero: els 3 porters titulars (≥70%) amb MÉS punts projectats.
"""
import datetime as dt
import re

from bot import ff, si
from bot.web import load_json, login_sorareinside, new_context, save_json, save_session

FF = "https://www.futbolfantasy.com"


def match_pages(page, jornada):
    """Jugadors de les pàgines de partit de la jornada de LaLiga (alineacions probables de FutbolFantasy)."""
    page.goto(f"{FF}/laliga/posibles-alineaciones", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    links = page.evaluate("() => [...new Set([...document.querySelectorAll('a[href*=\"/partidos/\"]')].map(a => a.href.split('#')[0]))]")
    players = []
    seen = 0
    for url in links[:24]:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        head = page.inner_text("body")[:200]
        m = re.search(r"Jornada (\d+)", head)
        if jornada is not None and (not m or int(m.group(1)) != jornada):
            continue
        seen += 1
        jn = int(m.group(1)) if m else None
        got = page.evaluate("""(url) => [...document.querySelectorAll('[class*="jugador_"]')].map(e => {
            const a = e.querySelector('a[data-probabilidad]'); if (!a) return null;
            const rv = e.querySelector('.ff-revulsivo');
            const name = e.querySelector('img[alt]')?.alt && e.querySelector('img[alt]').alt !== 'Más info' ? e.querySelector('img[alt]').alt
                         : e.innerText.replace(/\\s+/g, ' ').trim().replace(/^[\\d.%\\s]+/, '');
            const num = k => parseFloat(a.getAttribute('data-' + k)) || 0;
            return { name: name.replace(/^[%\\s]+/, '').trim(), url, suplente: e.getAttribute('data-onceff') === 'suplente', revulsivo: !!rv,
                     pct: parseInt(a.getAttribute('data-probabilidad')) || 0, lesion: a.getAttribute('data-lesion'),
                     pj: num('totalpartidosjugados'), amarillas: num('totalamarillas'), media: num('totalpuntosfutmondostatspartido') };
        }).filter(Boolean)""", url)
        for g in got:
            g["j"] = jn
        players += got
        if seen >= (10 if jornada is not None else 20):  # sense jornada: totes les pàgines (també la propera)
            break
    return players


def pick_revulsivo(players):
    c = [p for p in players if p["revulsivo"] and p["pct"] <= 50 and str(p["lesion"]) in ("-1", "", "None")]
    c.sort(key=lambda p: (-p["media"], p["pct"]))
    return c


def gk_list(sidata, players=None):
    """Porters titulars: % de futbolfantasy.com (≥70%) si hi són; si no, SorareInside (≥80%). PS de SorareInside."""
    out = []
    ffp = [{"name": p["name"], "url": p.get("url"), "pct": p["pct"]} for p in players or [] if not p.get("suplente")]
    for t in sidata.get("_order", []):
        rows = sidata.get(t)
        if isinstance(rows, list) and rows and rows[0]:
            g = rows[0][0]
            fp = ff.ff_pct(g["name"], t, ffp) if ffp else None
            if g.get("ps") is not None and (fp >= ff.FF_MIN if fp is not None else (g.get("pct") or 0) >= 80):
                out.append({"si": g["name"], "team": t, "ps": g["ps"]})
    return out


def fill_names(page, jid, names, report, label, want=3):
    """Busca cada nom al selector del joc i el posa (usa la mateixa lògica de noms que el Fantasy)."""
    placed = []
    for n in names:
        if len(placed) >= want:
            break
        ff.open_picker(page, jid)
        res = page.evaluate("(q) => __ff.search(q)", n) or []
        if not res and ff.norm(n):
            res = page.evaluate("(q) => __ff.search(q)", ff.norm(n)[-1]) or []
        best = max(res, key=lambda r: ff.name_score(n, r["n"]), default=None)
        if not best or ff.name_score(n, best["n"]) < 80 or (best["u"] is not None and str(best["u"]) == "0"):
            ff.close_modal(page)
            skip = load_json("extras_unusable.json", {})
            skip.setdefault(label.split(" (")[0], [])
            if n not in skip[label.split(" (")[0]]:
                skip[label.split(" (")[0]].append(n)  # sense usos o no trobat: no s'ha de tornar a triar
            save_json("extras_unusable.json", skip)
            continue
        page.locator(".modal.show .sel-item:visible").filter(has=page.locator(".sel-nombre", has_text=best["n"])).first.click()
        page.locator(".modal.show").wait_for(state="hidden", timeout=10000)
        page.wait_for_timeout(800)
        placed.append({"n": best["n"], "id": str(best["id"])})
    report.append(f"{'✅' if len(placed) == want else '⚠️'} {label}: {', '.join(p['n'] for p in placed) or 'cap'}")
    return placed


KINDS = {"revulsivo": "Trío revulsivo", "antagonista": "Trío antagonista", "resiliencia": "Resiliencia de portero"}


def kind_of(card):
    t = (card["title"] + " " + card["label"]).lower()
    return next((k for k in KINDS if k in t), None)


def orders(sidata, players):
    """Llista ordenada de candidats per a cada joc: [{'n': nom, 'team': equip SorareInside o None}]."""
    gks = gk_list(sidata, players)
    starters = [p for p in players if not p["suplente"] and p["pct"] >= ff.FF_MIN]
    low = sorted(gks, key=lambda x: x["ps"])
    hot = sorted([p for p in starters if p["pj"] > 0], key=lambda p: -(p["amarillas"] / p["pj"]))
    return {
        "revulsivo": [{"n": p["name"], "team": None} for p in pick_revulsivo(players)],
        "antagonista": [{"n": x["si"], "team": x["team"], "gk": True} for x in low[:4]]
                       + [{"n": p["name"], "team": None} for p in hot if not any(ff.name_score(p["name"], x["si"]) >= 80 for x in low)],
        "resiliencia": [{"n": x["si"], "team": x["team"], "gk": True} for x in sorted(gks, key=lambda x: -x["ps"])],
    }


def run(page, b, report, max_hours=20.0, dry=False):
    """page: sessió de FutbolFantasy ja iniciada. Omple els extres de LaLiga que estiguin buits i tanquin aviat."""
    from bot.web import inject
    cards = ff.cards(page)
    allg = [c for c in cards if c["hours"] and 0 < c["hours"] <= max_hours and kind_of(c)]
    games = [c for c in allg if c["empty"] == 3]  # buits: s'omplen
    filled = [c for c in allg if c["empty"] < 3]  # ja omplerts: es revisen amb les dades del dia
    if not allg:
        return
    games = games or filled
    m = re.search(r"J(\d+)", games[0]["label"] + " " + games[0]["title"])
    jornada = int(m.group(1)) if m else None
    sctx = new_context(b, "sorareinside")
    spg = sctx.new_page()
    login_sorareinside(spg)
    save_session(sctx, "sorareinside")
    deadline = dt.datetime.now(ff.MADRID) + dt.timedelta(hours=games[0]["hours"])
    sidata = si.extract_league(spg, "Spain", "Primera División", deadline.date(), use_cache=False)
    save_json("si_ff_laliga.json", sidata)
    players = match_pages(page, jornada) if jornada else []
    save_json("extras_players.json", players)
    ords = orders(sidata, players)
    for g in [g for g in games if g["empty"] == 3]:
        kind = kind_of(g)
        names = [x["n"] for x in ords[kind]]
        if dry:
            report.append(f"🧪 {KINDS[kind]} [prova]: {', '.join(names[:6])}")
            continue
        page.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        inject(page, "ff")
        placed = fill_names(page, g["id"], names, report, KINDS[kind])
        save_json(f"extra_{kind}.json", {"jid": g["id"], "picked": placed})
    if filled:  # revisió diària dels ja omplerts (com els Fantasy i Predicted11)
        final_extras(page, report, dry=dry)


def final_extras(page, report, dry=False):
    """Revisió final dels extres de LaLiga (dades fresques + onzes oficials del primer partit).
    Els jugadors ja triats s'identifiquen per les caselles (el buscador no els mostra)."""
    from bot import espn
    from bot.web import load_json, inject
    sidata, players = load_json("si_ff_laliga.json"), load_json("extras_players.json", [])
    if not sidata or not players:
        return
    cards = [c for c in ff.cards(page) if kind_of(c) and c["ids"] and c["hours"] and c["hours"] > 0]
    if not cards:
        return
    kickoff = (dt.datetime.now(ff.MADRID) + dt.timedelta(hours=cards[0]["hours"])).astimezone(dt.timezone.utc)
    starters, teams_first = [], set()
    for ev in espn.matches_at("laliga", kickoff):
        lu = None
        try:  # primer l'onze oficial de FotMob (mai el probable), si no ESPN
            from bot import fotmob
            lu = fotmob.starters_by_team(ev["home"], ev["away"], ev["start"])
        except Exception:
            lu = None
        lu = lu or espn.starters("laliga", ev["id"])
        if not lu:
            report.append(f"ℹ️ Extres: l'onze oficial de {ev['home']}-{ev['away']} encara no hi és")
            continue
        for team, names in lu.items():
            starters += names
            best = max(sidata.get("_order", []), key=lambda t: ff.team_score(t, team), default=None)
            if best and ff.team_score(best, team) > 0:
                teams_first.add(best)
    is_starter = lambda n: any(ff.name_score(n, s_) >= 80 for s_ in starters)
    ords = orders(sidata, players)
    for card in cards:
        kind = kind_of(card)

        def valid(x):
            if kind == "revulsivo":
                return not (starters and is_starter(x["n"]))
            if x.get("team") in teams_first and starters:
                return is_starter(x["n"])
            return True

        bad = set(load_json("extras_unusable.json", {}).get(KINDS[kind], []))
        desired = [x["n"] for x in ords[kind] if valid(x) and x["n"] not in bad]
        slots = ff.read_slots(page, card["id"])
        top = desired[:3]
        keep = [s_ for s_ in slots if any(ff.name_score(s_["name"], d) >= 60 for d in top)]
        out = [s_ for s_ in slots if s_ not in keep]
        if not out:
            report.append(f"✅ {KINDS[kind]}: revisat, sense canvis")
            continue
        if dry:
            report.append(f"🧪 {KINDS[kind]}: canviaria {', '.join(s_['name'] for s_ in out)} (millors ara: {', '.join(top)}) — no he fet cap canvi")
            continue
        for s_ in out:
            ff.remove_slot(page, card["id"], s_["slot"])
        page.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        inject(page, "ff")
        todo = [d for d in desired if not any(ff.name_score(s_["name"], d) >= 60 for s_ in keep)]
        tmp = []
        placed = fill_names(page, card["id"], todo, tmp, KINDS[kind], want=len(out))
        # si els millors no tenen usos, pot tornar a entrar el mateix que s'havia tret: llavors no és cap canvi
        back = [s_["name"] for s_ in out if any(ff.name_score(s_["name"], p_["n"]) >= 60 for p_ in placed)]
        gone = [s_["name"] for s_ in out if s_["name"] not in back]
        came = [p_["n"] for p_ in placed if not any(ff.name_score(p_["n"], b_) >= 60 for b_ in back)]
        ok = len(placed) == len(out)
        if not gone and ok:
            report.append(f"✅ {KINDS[kind]}: sense canvis (els que tenen més PS no tenen usos o no es poden triar; es queden {', '.join(back)})")
        else:
            report.append(f"{'✅' if ok else '⚠️'} {KINDS[kind]}: " + (f"surten {', '.join(gone)} → entren {', '.join(came) or 'cap'}" if gone else "")
                          + (f" (es queda {', '.join(back)})" if back else "") + ("" if ok else f" — REVISA-HO: només {len(placed)} de {len(out)}"))
