"""FutbolFantasy Fantasy✨: omple els onzes buits amb els punts projectats de SorareInside.

Ús:  python -m bot.ff [--max-hours 20] [--only europa-league ...]
Normes (CLAUDE.md): ≥80% titular, respectar usos, tàctica vàlida, cap parella de rivals,
màxims punts projectats; empat → el que surt primer a la llista. Ítems → elegible amb més PS.
"""
import argparse
import json
import datetime as dt
import re
import unicodedata
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from bot import si
from bot.notify import telegram
from bot.web import ROOT, inject, login_futbolfantasy, login_sorareinside, new_context, save_json, save_session

FF = "https://www.futbolfantasy.com"
# Etiqueta del joc → (pàgina de la competició, país i lliga a SorareInside). L'ordre importa (LaLiga 2 abans que LaLiga).
COMPS = [
    ("LaLiga 2", "laliga2", ("Spain", "Segunda División")),
    ("LaLiga", "laliga", ("Spain", "Primera División")),
    ("Premier League", "premier-league", ("England", "Premier League")),
    ("Serie A", "serie-a", ("Italy", "Serie A")),
    ("Champions", "champions", ("Europe", "UEFA Champions League")),
    ("Europa League", "europa-league", ("Europe", "UEFA Europa League")),
]
ALIAS = json.loads((ROOT / "config" / "futbolfantasy.json").read_text(encoding="utf-8")).get("alias", {})
DEFAULT_TACTICS = ["5-3-2", "5-4-1", "4-5-1", "4-4-2", "4-3-3", "3-5-2", "3-4-3"]
POS = {"POR": "G", "DEF": "D", "MED": "M", "DEL": "F"}


# Lletres que no es descomponen amb NFD (sense això, "Ødegaard" quedava "degaard")
TRANSLIT = str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "Æ": "Ae", "ß": "ss", "ł": "l", "Ł": "L", "đ": "d", "Đ": "D",
                          "ı": "i", "œ": "oe", "Œ": "Oe", "þ": "th", "ð": "d"})


def plain(s):
    return unicodedata.normalize("NFD", (s or "").translate(TRANSLIT)).encode("ascii", "ignore").decode()


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", plain(s).lower()).split()


def name_score(a, b):
    ta, tb = norm(a), norm(b)
    if ta == tb:
        return 100
    sa, sb = set(ta), set(tb)
    if sa and sa <= sb or sb and sb <= sa:
        return 80
    if ta and tb and ta[-1] == tb[-1]:
        return 60
    # noms escurçats: "Rodri" / "Rodrigo" (mínim 4 lletres), el filtre d'equip evita confusions
    # Noms escurçats ("Rodri"/"Rodrigo"): entre cognoms, o qualsevol paraula si un dels dos és un sol nom
    pairs = [(ta[-1], tb[-1])] if ta and tb else []
    if len(ta) == 1 or len(tb) == 1:
        pairs = [(x, y) for x in ta for y in tb]
    if any(len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x)) for x, y in pairs):
        return 60
    return len(sa & sb) * 20


def hours_left(rem):
    d = dict((u, int(n)) for n, u in re.findall(r"(\d+)\s*([dhms])", rem))
    return d.get("d", 0) * 24 + d.get("h", 0) + d.get("m", 0) / 60


def team_score(a, b):
    stop = {"fc", "cf", "ac", "sc", "afc", "cd", "ud", "rc", "ss", "us", "calcio", "club", "de", "real", "sk", "fk", "kv", "spor", "kulubu", "d"}
    ta, tb = set(norm(a)) - stop, set(norm(b)) - stop
    return len(ta & tb) + (1 if any(len(x) >= 4 and (x.startswith(y) or y.startswith(x)) for x in ta for y in tb if len(y) >= 4) else 0)


def candidates(sidata, official=None):
    """Candidats ordenats per PS. official = {equip SorareInside: [titulars oficials]}: per a aquests equips
    només compten els titulars confirmats (i compten com a 100%, encara que abans tinguessin menys del 80%)."""
    official = official or {}
    order = sidata["_order"]
    opp = {}
    for i in range(0, len(order) - 1, 2):
        opp[order[i]], opp[order[i + 1]] = order[i + 1], order[i]
    out = []
    for t in order:
        rows = sidata.get(t)
        if not isinstance(rows, list):
            continue
        off = official.get(t)
        for r in rows:
            for p in r:
                if p.get("ps") is None:
                    continue
                if off is not None:
                    if not any(name_score(p["name"], o) >= 60 for o in off):
                        continue  # no és titular oficial
                elif (p.get("pct") or 0) < 80:
                    continue
                out.append({"si": p["name"], "team": t, "opp": opp.get(t), "ps": p["ps"], "pct": 100 if off is not None else p["pct"]})
    out.sort(key=lambda x: -x["ps"])  # ordenació estable: en cas d'empat, l'ordre de la llista
    for i, c in enumerate(out):
        c["idx"] = i
    return out


def official_lineups(slug, kickoff, sidata, wait_until=None, log=None):
    log = log if log is not None else []
    """Onzes oficials (FotMob i, si no, ESPN) dels partits que comencen a `kickoff`. Espera (reintenta cada 3 min)
    fins a `wait_until` si encara no s'han publicat. Retorna {equip SorareInside: [titulars]}."""
    import time
    from bot import espn
    try:
        evs = espn.matches_at(slug, kickoff.astimezone(dt.timezone.utc))
    except Exception as e:
        log.append(f"ESPN no disponible ({e})")
        return {}
    teams = [t for t in sidata.get("_order", [])]
    out = {}
    for ev in evs:
        st = None
        while True:
            st = None
            try:  # primer FotMob (sovint el té abans, quan el club el publica), si no ESPN
                from bot import fotmob
                st = fotmob.starters_by_team(ev["home"], ev["away"], ev["start"])
            except Exception:
                st = None
            if not st:
                try:
                    st = espn.starters(slug, ev["id"])
                except Exception:
                    st = None
            if st or not wait_until or dt.datetime.now(dt.timezone.utc) >= wait_until:
                break
            time.sleep(180)
        if not st:
            log.append(f"onzes oficials de {ev['home']}-{ev['away']} encara no publicats")
            continue
        for espn_team, names in st.items():
            best = max(teams, key=lambda t: team_score(t, espn_team), default=None)
            if best and team_score(best, espn_team) > 0:
                out[best] = names
        log.append(f"onzes oficials de {ev['home']}-{ev['away']} aplicats")
    return out


def click(page, selector):
    """Clic real a un element: el centra a la pantalla (que no el tapi cap anunci) i, si cal, força el clic."""
    loc = page.locator(selector).first
    loc.evaluate("e => e.scrollIntoView({block: 'center'})")
    page.wait_for_timeout(300)
    try:
        loc.click(timeout=8000)
    except Exception:
        loc.click(force=True, timeout=8000)


def open_picker(page, jid):
    click(page, f'a.fantasy-add[data-juego="{jid}"]')
    page.locator(".modal.show input[type=text]").wait_for(timeout=10000)
    page.wait_for_timeout(600)


def close_modal(page):
    if page.locator(".modal.show").count():
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        if page.locator(".modal.show .close").count():
            page.locator(".modal.show .close").first.click()
            page.wait_for_timeout(500)


def lookup(page, jid, cands, limit=60):
    open_picker(page, jid)
    return lookup_open(page, cands, limit)


def lookup_open(page, cands, limit=60):
    """Busca cada candidat al selector: posició, usos i equip a FutbolFantasy.
    Primer dedueix l'equip de FutbolFantasy de cada equip de SorareInside amb els noms segurs,
    i després només accepta jugadors d'aquell equip (evita confondre Nico Paz amb Yeferson Paz)."""
    from collections import Counter
    raw = []
    for c in cands[:limit]:
        c["si"] = ALIAS.get(f"{c['team']}|{c['si']}", ALIAS.get(c["si"], c["si"]))
        res = page.evaluate("(q) => __ff.search(q)", c["si"]) or []
        last = (c["si"].split() or [""])[-1]
        for q in dict.fromkeys([plain(c["si"]), last, plain(last)]):  # nom sense accents, cognom tal qual i sense accents
            if res or not q or q == c["si"]:
                continue
            res = page.evaluate("(q) => __ff.search(q)", q) or []
        raw.append((c, res))
    close_modal(page)
    votes = {}
    for c, res in raw:
        strong = [r for r in res if name_score(c["si"], r["n"]) >= 80]
        if len(strong) == 1 and strong[0]["t"]:
            votes.setdefault(c["team"], Counter())[strong[0]["t"]] += 1
    team_id = {t: v.most_common(1)[0][0] for t, v in votes.items()}
    found, missing = [], []
    for c, res in raw:
        tid = team_id.get(c["team"])
        ok = [r for r in res if r["p"] in POS and (r["t"] == tid if tid else name_score(c["si"], r["n"]) >= 80)]
        best = max(ok, key=lambda r: name_score(c["si"], r["n"]), default=None)
        if not best or name_score(c["si"], best["n"]) < 60:
            if c["ps"] >= (cands[min(15, len(cands) - 1)]["ps"] if cands else 0):
                missing.append(f"{c['si']} ({c['team']}, {c['ps']} PS)")
            continue
        if best["u"] is not None and str(best["u"]) == "0":
            continue  # sense usos
        found.append({**c, "ff": best["n"], "ffid": str(best["id"]), "pos": POS[best["p"]], "uses": best["u"]})
    return found, missing


def optimise(found, tactics):
    best = None
    for tac in tactics:
        d, m, f = map(int, tac.split("-"))
        need = {"G": 1, "D": d, "M": m, "F": f}
        # Rivals: només resten punts els gols encajats als porters i defenses. Per tant, un porter o defensa no pot
        # coincidir amb cap jugador de l'equip rival; migcampistes i davanters de dos rivals sí que poden anar junts.
        pick, teams, back = [], set(), set()
        for c in sorted(found, key=lambda c: not c.get("lock")):  # primer els que s'han de mantenir; després per PS
            gd = c["pos"] in ("G", "D")
            clash = c["opp"] is not None and (c["opp"] in back or (gd and c["opp"] in teams))
            if need[c["pos"]] and not clash:
                pick.append(c)
                need[c["pos"]] -= 1
                if c["team"]:
                    teams.add(c["team"])
                    if gd:
                        back.add(c["team"])
        if any(need.values()):
            continue
        key = (sum(c["ps"] for c in pick), -sum(c["idx"] for c in pick))
        if best is None or key > best[0]:
            best = (key, tac, pick)
    return best


def fill(page, jid, pick):
    for c in pick:
        open_picker(page, jid)
        page.evaluate("(q) => __ff.search(q)", c["ff"])
        item = page.locator(".modal.show .sel-item:visible").filter(has=page.locator(".sel-nombre", has_text=c["ff"])).first
        item.click()
        page.locator(".modal.show").wait_for(state="hidden", timeout=10000)
        page.wait_for_timeout(800)


def use_items(page, comp_slug, pick, report):
    page.goto(f"{FF}/fantasy/{comp_slug}", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    btn = page.locator("a, button").filter(has_text=re.compile(r"Ítems")).first
    if not btn.count():
        return
    for _ in range(5):
        btn.click()
        page.wait_for_timeout(1500)
        cards = page.locator(".modal.show .item-card")
        n = cards.count()
        done = False
        for i in range(n):
            card = cards.nth(i)
            name = card.get_attribute("data-nombre")
            card.click()
            page.wait_for_timeout(1500)
            txt = page.locator(".modal.show").inner_text()
            if "Elige un jugador" not in txt:
                continue
            eligible = [c for c in pick if c["ff"] in txt]
            if not eligible:
                continue
            target = max(eligible, key=lambda c: (c["ps"], -c["idx"]))
            page.locator(".modal.show").get_by_text(target["ff"], exact=True).first.click()
            page.wait_for_timeout(2000)
            report.append(f"   🎁 {name} → {target['ff']}")
            done = True
            break
        close_modal(page)
        if not done:
            return


MADRID = ZoneInfo("Europe/Madrid")


def cards(page):
    page.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    inject(page, "ff")
    out = page.evaluate("() => __ff.cards()")
    for c in out:
        c["ids"] = [str(x) for x in c["ids"]]
        c["hours"] = None
        if c["end"]:
            end = dt.datetime.strptime(c["end"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=MADRID)
            c["hours"] = (end - dt.datetime.now(MADRID)).total_seconds() / 3600
    return out


def remove_slot(page, jid, slot):
    """Buida una casella concreta (clic al jugador → 'Quitar selección')."""
    click(page, f'#juego-{jid} a.fantasy-slot[data-posicion="{slot}"]')
    page.locator(".modal.show").wait_for(timeout=10000)
    page.wait_for_timeout(800)
    page.locator(".modal.show").get_by_text("Quitar selección").first.click()
    page.locator(".modal.show").wait_for(state="hidden", timeout=10000)
    page.wait_for_timeout(1200)


def read_slots(page, jid):
    cards(page)
    inject(page, "ff")
    return page.evaluate("(id) => __ff.slots(id)", jid)


def remove_players(page, jid, remove_ids, log):
    """Treu del camp els jugadors indicats (clic al jugador → 'Quitar selección')."""
    for _ in range(15):
        card = next((c for c in cards(page) if c["id"] == jid), None)
        left = [i for i in (card["ids"] if card else []) if i in remove_ids]
        if not left:
            return
        idx = card["ids"].index(left[0])
        slots = sorted(card["slots"])
        pos = slots[idx] if idx < len(slots) else slots[0]
        click(page, f'#juego-{jid} a.fantasy-slot[data-posicion="{pos}"]')
        page.locator(".modal.show").wait_for(timeout=10000)
        page.wait_for_timeout(800)
        page.locator(".modal.show").get_by_text("Quitar selección").first.click()
        page.locator(".modal.show").wait_for(state="hidden", timeout=10000)
        page.wait_for_timeout(1200)
    log.append("⚠️ no he pogut treure tots els jugadors")


def final_review(page, g, cands, report, label, dry=False, known=None):
    """Revisió d'un onze ja (parcialment) ple. Retorna (tàctica, total, pick, canvis) o None.
    Els jugadors que ja són a l'onze no surten al buscador, així que s'identifiquen per les caselles.
    known: noms amb dades a SorareInside (revisió diària). Si un jugador de l'onze no hi surt (equip encara
    sense onze o sense punts projectats), no se'l treu: es manté fins que hi hagi dades."""
    jid = g["id"]
    slots = read_slots(page, jid)
    cur = []
    for s_ in slots:
        best = max(cands, key=lambda c: name_score(s_["name"], c["si"]), default=None)
        if best and name_score(s_["name"], best["si"]) >= 60:
            cur.append({**best, "ff": s_["name"], "pos": s_["pos"], "slot": s_["slot"], "current": True})
        elif known is not None and not any(name_score(s_["name"], k) >= 60 for k in known):
            cur.append({"si": s_["name"], "team": None, "opp": None, "ps": 0, "pct": 0, "idx": 99998,
                        "ff": s_["name"], "pos": s_["pos"], "slot": s_["slot"], "current": True, "lock": True})
        else:  # ja no és candidat (p. ex. ara té menys del 80% o no és titular oficial): es canviarà si cal
            cur.append({"si": s_["name"], "team": None, "opp": None, "ps": -1, "pct": 0, "idx": 99999,
                        "ff": s_["name"], "pos": s_["pos"], "slot": s_["slot"], "current": True})
    removed_first = None
    if g["empty"] == 0 and cur:
        if all(c.get("lock") for c in cur):
            report.append(f"⏳ {label}: encara no hi ha dades dels jugadors de l'onze; ho miraré més endavant")
            return None
        if dry:
            report.append(f"🧪 {label}: (prova) amb l'onze ple cal buidar una casella per buscar; no faig res")
            return None
        removed_first = min([c for c in cur if not c.get("lock")], key=lambda c: (c["ps"], -c["idx"]))
        remove_slot(page, jid, removed_first["slot"])
        cur = [c for c in cur if c is not removed_first]
    page.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    inject(page, "ff")
    found, missing = lookup(page, jid, cands)
    cur_names = [c["si"] for c in cur]
    pool = [c for c in found if not any(name_score(c["si"], n) >= 80 for n in cur_names)] + cur
    pool.sort(key=lambda c: (-c["ps"], c["idx"]))
    best = optimise(pool, DEFAULT_TACTICS)
    if not best:
        if removed_first:  # tornar a deixar l'onze com estava
            page.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
            page.wait_for_timeout(2500)
            inject(page, "ff")
            fill(page, jid, [removed_first])
        report.append(f"⏳ {label}: amb les dades d'ara no surt cap onze vàlid millor; el deixo com està")
        return None
    (total, _), tac, pick = best
    keep = [c for c in cur if any(c is p for p in pick)]
    out = [c for c in cur if not any(c is p for p in pick)]
    todo = [p for p in pick if not p.get("current")]
    if dry:
        return tac, total, pick, f"(prova) sortirien {len(out) + (1 if removed_first and not any(name_score(removed_first['si'], p['si']) >= 80 for p in todo) else 0)}"
    for c in out:
        remove_slot(page, jid, c["slot"])
    page.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    inject(page, "ff")
    fill(page, jid, todo)
    gone = [c["ff"] for c in out] + ([removed_first["ff"]] if removed_first and not any(name_score(removed_first["si"], p["si"]) >= 80 for p in todo) else [])
    came = [p["ff"] for p in todo if not (removed_first and name_score(removed_first["si"], p["si"]) >= 80)]
    changes = f"surten: {', '.join(gone) or 'cap'} · entren: {', '.join(came) or 'cap'}"
    return tac, total, pick, changes, missing


def run(max_hours=20.0, only=None, dry=False, final=False, extras_hours=None):
    """final=True: revisió abans de tancar. Torna a calcular l'onze amb les dades més noves
    (onzes oficials si ja han sortit) i fa els canvis necessaris encara que el joc ja estigui ple."""
    report = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = new_context(b, "futbolfantasy")
        pg = ctx.new_page()
        login_futbolfantasy(pg)
        save_session(ctx, "futbolfantasy")
        allc = cards(pg)
        save_json("deadlines_ff.json", {c["label"]: c["end"] for c in allc if c["end"]})
        sctx = spg = None
        allc.sort(key=lambda c: c["hours"] if c["hours"] is not None else 1e9)  # primer el que tanca abans
        for g in allc:
            comp = next((c for c in COMPS if g["label"].startswith(c[0] + " ·")), None)
            h = g["hours"]
            if h is None or h <= 0:
                continue
            if not comp:
                if re.search(r"revulsivo|antagonista|resiliencia", g["label"] + " " + g["title"], re.I):
                    continue  # els fa bot/extras.py
                if g["empty"] and h <= (extras_hours or max_hours):
                    report.append(f"✋ {g['label'] or g['title']}: pendent (joc especial, encara no automatitzat)")
                continue
            label, slug, (country, league) = comp
            if only and slug not in only:
                continue
            if h > max_hours:
                continue
            try:
                if spg is None:
                    sctx = new_context(b, "sorareinside")
                    spg = sctx.new_page()
                    login_sorareinside(spg)
                    save_session(sctx, "sorareinside")
                deadline = dt.datetime.now(MADRID) + dt.timedelta(hours=h)
                sidata = si.extract_league(spg, country, league, deadline.date(), use_cache=False)
                save_json(f"si_ff_{slug}.json", sidata)
                official, olog = {}, []
                if final:
                    kickoff = deadline
                    official = official_lineups(slug, kickoff, sidata, wait_until=kickoff.astimezone(dt.timezone.utc) - dt.timedelta(minutes=20), log=olog)
                    if official:  # dades fresques: els onzes poden haver canviat mentre esperàvem
                        sidata = si.extract_league(spg, country, league, deadline.date(), use_cache=False)
                cands = candidates(sidata, official)
                pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
                pg.wait_for_timeout(2500)
                inject(pg, "ff")
                jid = g["id"]
                if g["empty"] < 11:
                    known = None if final else [p_["name"] for t in sidata.get("_order", []) if isinstance(sidata.get(t), list)
                                                for r_ in sidata[t] for p_ in r_ if p_.get("ps") is not None]
                    r = final_review(pg, g, cands, report, g["label"], dry=dry, known=known)
                    if not r:
                        continue
                    tac, total, pick, changes = r[:4]
                    miss = r[4] if len(r) > 4 else []
                    order = {"G": 0, "D": 1, "M": 2, "F": 3}
                    names = ", ".join(f"{c['ff']} {c['ps']}" for c in sorted(pick, key=lambda c: order.get(c["pos"], 9)))
                    sl = read_slots(pg, jid)
                    ok = len(sl) == 11
                    extra = (" | " + "; ".join(olog)) if olog else ""
                    report.append(f"{'✅' if ok else '⚠️'} {g['label']} {'revisió final' if final else 'revisió diària'} ({tac}, {total} PS): {changes} | onze: {names}{extra}" + ("" if ok else f" — REVISA-HO: {len(sl)} jugadors"))
                    if not dry:
                        use_items(pg, slug, pick, report)
                    continue
                found, missing = lookup(pg, jid, cands)
                best = optimise(found, DEFAULT_TACTICS)
                if not best:
                    report.append(f"❌ {g['label']}: no he trobat un onze vàlid" if final else
                                  f"⏳ {g['label']}: encara falten dades a SorareInside per fer un onze ({len(found)} jugadors); ho torno a provar demà")
                    continue
                (total, _), tac, pick = best
                order = {"G": 0, "D": 1, "M": 2, "F": 3}
                names = ", ".join(f"{c['ff']} {c['ps']}" for c in sorted(pick, key=lambda c: order[c["pos"]]))
                warn = f" | ⚠️ no trobats a FutbolFantasy: {', '.join(missing)}" if missing else ""
                if olog:
                    warn += " | " + "; ".join(olog)
                if dry:
                    report.append(f"🧪 {g['label']} ({tac}, {total} PS) [prova, no desat]: {names}{warn}")
                    continue
                new_ids = {c["ffid"] for c in pick}
                cur = set(g["ids"])
                out_ids = cur - new_ids
                if final and cur == new_ids:
                    report.append(f"✅ {g['label']}: revisat abans de tancar, sense canvis")
                    continue
                if out_ids:
                    remove_players(pg, jid, out_ids, report)
                card = next((c for c in cards(pg) if c["id"] == jid), {"ids": []})
                todo = [c for c in pick if c["ffid"] not in set(card["ids"])]
                pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
                pg.wait_for_timeout(2500)
                inject(pg, "ff")
                fill(pg, jid, todo)
                after = next((c for c in cards(pg) if c["id"] == jid), {"ids": [], "empty": 11})
                ok = set(after["ids"]) == new_ids
                changes = f" | canvis: surten {len(out_ids)}, entren {len(todo)}" if final and cur else ""
                report.append(f"{'✅' if ok else '⚠️'} {g['label']} ({tac}, {total} PS): {names}{changes}{warn}" + ("" if ok else f" — revisa-ho, falten {after['empty']}"))
                save_json(f"ff_{slug}.json", {"jid": jid, "pick": pick})
                use_items(pg, slug, pick, report)
            except Exception as e:  # un joc no ha d'aturar la resta
                report.append(f"❌ {g['label']}: {type(e).__name__}: {str(e)[:200]}")
        try:
            from bot import extras
            if not final:
                extras.run(pg, b, report, max_hours=extras_hours or max_hours, dry=dry)
            elif not only or "laliga" in only:
                extras.final_extras(pg, report, dry=dry)
        except Exception as e:
            import traceback
            print("::notice title=tb::" + traceback.format_exc().replace("\n", " | ")[-1500:])
            report.append(f"❌ Extres: {type(e).__name__}: {str(e)[:200]}")
        save_session(ctx, "futbolfantasy")
        b.close()
    msg = "FutbolFantasy Fantasy✨" + (" (revisió final)" if final else "") + "\n" + ("\n".join(report) or "Res a fer ara.")
    print(msg)
    for l in report:
        print("::notice title=ff::" + l)
    if report:
        telegram(msg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-hours", type=float, default=20.0)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--final", action="store_true")
    a = ap.parse_args()
    run(a.max_hours, a.only, a.dry, a.final)
