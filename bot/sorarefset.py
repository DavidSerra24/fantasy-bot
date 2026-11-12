"""Sorare Set de FUTBOL per l'API (decisió del David, 2/11).

Normes:
- Només jugadors amb ≥80% de ser titulars (filtre `starterOddsBasisPointsRange` del banc del pas) o **titulars confirmats**
  a l'onze oficial (Sorare/FotMob); si l'onze oficial ja ha sortit i no hi és, fora.
- Ordre: primer els que juguen abans («Playing soon»), després per **impacte previst** (lletra A → F) i, a igualtat,
  per **punts previstos** (projectedScore).
- Sense repetir jugadors dins del tauler; dins d'una alineació, cap parell de jugadors d'equips que s'enfronten.
- De cada jugador, la carta amb més experiència.
- Tots els partits possibles. Tauler personal: sempre 4 alineacions; si el nivell es supera es reclama, si es perd es
  reinicia, com més aviat millor (per si després hi ha més partits). Tauler d'equip: 1 alineació.
- Cada passada torna a calcular **de zero** les alineacions que encara no han començat (revisió fins a l'últim moment):
  si n'hi ha una de millor, la canvia. Si amb els del ≥80% no es pot completar una alineació, s'omple amb els següents
  («per si de cas»), marcats amb 🔸.
Ús: python -m bot.sorare fset (prova) / fsetgo
"""
import datetime as dt

from bot.notify import telegram
from bot.sorare import gql, token
from bot.sorareset import RESTART, UPSERT, claim_step
from bot.web import load_json, save_json

STEP = """query($m: BoardMode!) { currentUser { setBoard(mode: $m, sport: FOOTBALL) { id title
  myCurrentStep { __typename id level state target
    ... on CareerStep { maxLineupsCount remainingLineupsCount }
    myLineups { ... on TaskLineup { id aasmState score taskAppearances { ... on TaskAppearanceInterface { index score anyPlayer { slug displayName } anyCard { slug pictureUrl } game { id date } } } } }
    displayedTypedRules { key ... on So5AppearancesRule { appearances { name positions sub } } } } } } }"""

def gql_step(v):
    """STEP i, de passada, anota les alineacions (punts) per al resum del matí (bot/digest.py, 12/11)."""
    d = gql(STEP, v, token=token())
    try:
        from bot import digest
        b = d["currentUser"]["setBoard"] or {}
        st = b.get("myCurrentStep") or {}
        digest.set_lineups("FOOTBALL", b, st, st.get("myLineups"))
    except Exception as e:
        print(f"::warning title=resum::{str(e)[:120]}")
    return d

BENCH = """query($st: String!, $after: String, $f: BenchFilterInput!) { currentUser { step(id: $st) { myFilteredBench(filters: $f, first: 100, after: $after) {
  pageInfo { hasNextPage endCursor }
  nodes { ... on ComposeTeamBenchCard { position positions anyCard { slug xp pictureUrl }
    anyPlayer { displayName slug ... on Player { activeClub { slug } avg: averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE) } }
    eligiblePlayerGameScores(stepId: $st) { anyGame { id date ... on Game { homeTeam { slug name } awayTeam { slug name } } }
      projectedScore ... on PlayerGameScore { projection { grade } } } } } } } } }"""
from zoneinfo import ZoneInfo
MAD = ZoneInfo("Europe/Madrid")
GRADE = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5}
D = lambda x: dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def bench(step_id, f):
    out, after = [], None
    for _ in range(15):
        d = gql(BENCH, {"st": step_id, "after": after, "f": f}, token=token())["currentUser"]["step"]["myFilteredBench"]
        out += [n for n in d["nodes"] if n]
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    return out


def candidates(step_id, now, used_cards, locked_players, squad=False):
    """Jugadors disponibles (una carta per jugador, la de més XP) amb partit no començat, ordenats per les normes."""
    from bot.sorarelineup import lineup_status, starts
    all_ = bench(step_id, {"includeUsed": True})
    free = {n["anyCard"]["slug"] for n in bench(step_id, {})}
    hi = {n["anyPlayer"]["slug"] for n in bench(step_id, {"starterOddsBasisPointsRange": {"min": 8000}, "includeUsed": True})}  # també les cartes ja posades
    hi9 = {n["anyPlayer"]["slug"] for n in bench(step_id, {"starterOddsBasisPointsRange": {"min": 9000}, "includeUsed": True})}  # % a les imatges (12/11)
    best, cache = {}, {}
    for n in all_:
        p, c = n["anyPlayer"], n["anyCard"]
        # al tauler d'equip es pot posar qualsevol carta, encara que ja sigui en una alineació del personal (el David, 2/11)
        # els jugadors d'alineacions ja començades també hi són (marcats «locked»): només per repetir-los amb una altra
        # carta quan no queda ningú més (decisió del David, 12/11)
        if (squad and p["slug"] in locked_players) or (not squad and c["slug"] not in free and c["slug"] not in used_cards):
            continue
        games = [g for g in n.get("eligiblePlayerGameScores") or [] if g and g.get("anyGame") and D(g["anyGame"]["date"]) > now + dt.timedelta(seconds=40)]
        if not games:
            continue
        g = min(games, key=lambda g: g["anyGame"]["date"])
        q = {"slug": p["slug"], "name": p["displayName"], "card": c["slug"], "xp": c.get("xp") or 0, "pic": c.get("pictureUrl"), "pos": n.get("positions") or [n.get("position")],
             "team": ((p.get("activeClub") or {}).get("slug")), "game": g["anyGame"], "date": D(g["anyGame"]["date"]),
             "grade": ((g.get("projection") or {}).get("grade") or "?"), "proj": g.get("projectedScore") or 0, "avg": p.get("avg") or 0, "hi": p["slug"] in hi,
             "pct": 90 if p["slug"] in hi9 else 80 if p["slug"] in hi else None}
        q["locked"] = p["slug"] in locked_players
        cur = best.get(p["slug"])
        allc = (cur or {}).get("cards", []) + [(c["slug"], q["xp"], q["pic"])]
        allc.sort(key=lambda t: -t[1])  # de més a menys XP: primer la de més XP, després la següent (el David, 12/11)
        if not cur or q["xp"] > cur["xp"]:
            best[p["slug"]] = q
        best[p["slug"]]["cards"] = allc
    out = list(best.values())
    for q in out:
        xi = lineup_status(q["game"], cache) if q["date"] < now + dt.timedelta(hours=2) else None
        q["confirmed"] = bool(xi)
        q["ok"] = (starts(xi, q["slug"], q["name"]) if xi else q["hi"])
    # personal: els que juguen abans, després impacte, punts previstos i mitjana; equip: sense «playing soon» (el David, 2/11)
    out.sort(key=lambda q: (() if squad else (q["date"],)) + (GRADE.get(q["grade"], 6), -q["proj"], -q["avg"]))
    return out


def rivals(a, b, level="all"):
    """level "all": cap jugador amb un del rival; "back": només porter/defensa amb un rival (decisió del David, 4/11)."""
    ga, gb = a["game"], b["game"]
    if not (ga["id"] == gb["id"] and a.get("team") and b.get("team") and a["team"] != b["team"]):
        return False
    back = lambda q: bool(set(q["pos"]) & {"Goalkeeper", "Defender"})
    return level == "all" or back(a) or back(b)


def fill(cands, slots, taken, dups=None, used=None):
    """Una alineació com la fa el David (2/11, 2a explicació): es recorre la llista ordenada (els que juguen abans; dins de
    la mateixa hora, impacte, punts previstos i mitjana) i cada jugador va a la casella de la seva posició (o a l'Extra)
    si n'hi ha una de lliure i no s'enfronta amb cap dels ja posats. Així el millor de la primera hora (Talbi, C 53) entra
    primer i els seus rivals (Selvik, Magnetti, Ajorque) queden fora; el porter surt de l'hora següent (Leo Román).
    Primer només els bons (≥80% o titulars); si no s'omple, es completa amb els següents («per si de cas», 🔸)."""
    pick = {}
    snap = set(taken)
    res = None
    for lvl in ("all", "back", "none"):  # sense rivals → cap porter/defensa amb un rival → sense norma (4/11)
        taken.clear(); taken |= snap
        res = _fill(cands, slots, taken, lvl)
        if res is not None:
            return res
    # si no queden jugadors (p. ex. porters), un jugador ja posat es pot repetir amb una altra carta seva, sempre al final
    # i només per a les caselles que falten, com amb el Gazzaniga (decisió del David, 12/11: Livaković repetit)
    if dups:
        for lvl in ("all", "back", "none"):
            taken.clear(); taken |= snap
            res = _fill(cands, slots, taken, lvl, dups, used or set())
            if res is not None:
                return res
    taken.clear(); taken |= snap
    return None


def _fill(cands, slots, taken, lvl, dups=None, used=frozenset()):
    pick = {}
    for only_ok in (True,):  # només ≥80% o titulars confirmats; sense 🔸 (decisió del David, 8/11)
        for q in cands:
            if len(pick) == len(slots):
                break
            # mai un jugador que ja se sap que no és titular (onze oficial publicat i no hi és; 8/11: Bernardo, Daghim i
            # Lenz, suplents de l'Hoffenheim, van entrar com a 🔸)
            if q["slug"] in taken or (only_ok and not q["ok"]) or (q["confirmed"] and not q["ok"]) or (lvl != "none" and any(rivals(q, x, lvl) for x in pick.values())):
                continue
            free = [i for i, s_ in enumerate(slots) if i not in pick and set(q["pos"]) & set(s_["positions"])]
            if not free:
                continue
            i = min(free, key=lambda i: len(slots[i]["positions"]))  # la casella de la seva posició abans que l'Extra
            pick[i] = dict(q, extra=not only_ok, rival=lvl != "all" and any(rivals(q, x) for x in pick.values()))
            taken.add(q["slug"])
    for q in dups or []:  # repetits: només les caselles que falten, després de tots els altres
        if len(pick) == len(slots):
            break
        if any(x["slug"] == q["slug"] for x in pick.values()) or not q["ok"] or (q["confirmed"] and not q["ok"]) \
                or (lvl != "none" and any(rivals(q, x, lvl) for x in pick.values())):
            continue
        card = next((t for t in q.get("cards") or [] if t[0] not in used), None)
        free = [i for i, s_ in enumerate(slots) if i not in pick and set(q["pos"]) & set(s_["positions"])]
        if not card or not free:
            continue
        i = min(free, key=lambda i: len(slots[i]["positions"]))
        pick[i] = dict(q, card=card[0], xp=card[1], pic=card[2], dup=True, name=q["name"] + " 🔁",
                       rival=lvl != "all" and any(rivals(q, x) for x in pick.values()))
    return pick if len(pick) == len(slots) else None


def claim_check():
    """Comprovació curta (cada 10 min; decisió del David, 6/11: reclamar com més aviat millor i fer les alineacions del
    nivell següent, per si s'acaba just quan comencen més partits). Una sola consulta: només si el tauler personal està
    per reclamar (CLAIMABLE) o perdut (FAILED) es fa la passada sencera (reclama/reinicia i omple les 4 alineacions)."""
    from bot.sorareset import claim_missions
    claim_missions()
    b = gql_step({"m": "CAREER"})["currentUser"]["setBoard"]
    st = (b or {}).get("myCurrentStep") or {}
    sq = ((gql_step({"m": "SQUAD"})["currentUser"]["setBoard"] or {}).get("myCurrentStep") or {})
    if st.get("state") in ("CLAIMABLE", "FAILED") or sq.get("state") == "FAILED":
        print(f"::notice title=set futbol::tauler personal {st['state']}: passada sencera")
        run()


def run(dry=False, focus=None):
    """focus = hora (ISO) del primer partit d'unes alineacions: revisió final només d'aquelles (les altres es mantenen;
    decisió del David, 2/11). Sense focus (cada hora): es refan totes les que no han començat i s'omplen les que falten."""
    now = dt.datetime.now(dt.timezone.utc)
    rep, games, ends = [], set(), set()
    cards_img = []
    for mode in ("CAREER", "SQUAD"):
        label = f"⚽ Set · {'personal' if mode == 'CAREER' else 'equip'}"
        b = gql_step({"m": mode})["currentUser"]["setBoard"]
        st = (b or {}).get("myCurrentStep")
        if not st:
            continue
        if st["state"] == "CLAIMABLE" and mode == "SQUAD":  # el sobre del tauler d'equip l'obre el David (3/11)
            _seen = load_json("sorare_squad_notified.json", [])
            if st["id"] not in _seen:  # només un avís per nivell
                rep.append(f"🎁 {label}: nivell {st['level'] + 1} superat! Reclama tu el sobre quan vulguis (jo no el toco)")
                save_json("sorare_squad_notified.json", (_seen + [st["id"]])[-50:])
        elif st["state"] == "CLAIMABLE" and not dry:
            try:
                claim_step(st, mode)
                rep.append(f"🎁 {label}: nivell {st['level'] + 1} superat, recompensa reclamada")
            except Exception as e:
                rep.append(f"⚠️ {label}: no he pogut reclamar ({str(e)[:150]})")
            b = gql_step({"m": mode})["currentUser"]["setBoard"]; st = b["myCurrentStep"]
        if st["state"] == "FAILED" and mode == "SQUAD" and not dry:  # tauler d'equip perdut: es torna a començar (8/11)
            from bot.sorareset import restart_squad
            err = restart_squad(b, st, "FOOTBALL")
            rep.append(f"🔄 {label}: nivell {st['level'] + 1} perdut; he tornat a començar el tauler d'equip" if not err
                       else f"⚠️ {label}: nivell {st['level'] + 1} perdut i no l'he pogut reiniciar ({err[:150]}). Reinicia'l tu des del joc.")
            if not err:
                b = gql_step({"m": mode})["currentUser"]["setBoard"]; st = b["myCurrentStep"]
        if st["state"] == "FAILED" and mode == "CAREER" and not dry:
            try:
                d = gql(RESTART, {"input": {"taskId": b["id"]}}, token=token())["restartTasksTrack"]
                if d.get("errors"):
                    raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
                rep.append(f"🔄 {label}: nivell {st['level'] + 1} perdut; he reiniciat el tauler ({b.get('title')})")
            except Exception as e:
                rep.append(f"⚠️ {label}: nivell perdut i no he pogut reiniciar ({str(e)[:150]})")
            b = gql_step({"m": mode})["currentUser"]["setBoard"]; st = b["myCurrentStep"]
        if st["state"] in ("CLAIMABLE", "FAILED", "CLAIMED", "LOCKED"):
            continue
        rules = {r["key"]: r for r in st.get("displayedTypedRules") or []}
        slots = [a for a in (rules.get("Appearances") or {}).get("appearances") or [] if not a.get("sub")]
        lineups = [l for l in st.get("myLineups") or [] if l and l.get("taskAppearances")]
        started = lambda l: any(a and a.get("game") and D(a["game"]["date"]) <= now + dt.timedelta(seconds=40) for a in l["taskAppearances"])
        locked = [l for l in lineups if started(l)]
        open_ = [l for l in lineups if not started(l)]
        for l in lineups:
            ds = [a["game"]["date"] for a in l["taskAppearances"] if a and a.get("game")]
            if ds:
                games.add(min(ds, key=D))  # revisió final abans del primer partit de cada alineació
                if mode == "CAREER":  # del primer partit a l'últim: el nivell es pot superar abans que juguin tots
                    ends.add((min(ds, key=D), max(ds, key=D)))
        locked_players = {a["anyPlayer"]["slug"] for l in locked for a in l["taskAppearances"] if a}
        used_cards = {a["anyCard"]["slug"] for l in open_ for a in l["taskAppearances"] if a}
        n_total = (st.get("maxLineupsCount") or 4) if mode == "CAREER" else 1
        n_new = min(st.get("remainingLineupsCount") or 0, max(0, n_total - len(lineups))) if mode == "CAREER" else max(0, 1 - len(lineups))
        if not open_ and n_new == 0:  # totes en joc: res a fer fins que acabin els partits (el David, 6/11)
            rep.append(f"{label} ({b.get('title')}, nivell {st['level'] + 1}, objectiu {st['target']}, {len(locked)} en joc): totes en joc, res a revisar")
            continue
        cands = candidates(st["id"], now, used_cards, locked_players, squad=mode == "SQUAD")
        # partits del mateix dia (decisió del David, 8/11): només els del primer dia amb partits (hora de Madrid); les
        # alineacions que no es puguin completar aquell dia es fan l'endemà
        if cands:
            day0 = min(q["date"] for q in cands).astimezone(MAD).date()
            cands = [q for q in cands if q["date"].astimezone(MAD).date() == day0]
        allc = cands
        first = lambda l: min((D(a["game"]["date"]) for a in l["taskAppearances"] if a and a.get("game")), default=None)
        if focus:  # només les alineacions que comencen a aquesta hora; els jugadors de les altres es queden on són
            F = D(focus)
            keep = [l for l in open_ if first(l) != F]
            open_ = [l for l in open_ if first(l) == F]
            locked_players |= {a["anyPlayer"]["slug"] for l in keep for a in l["taskAppearances"] if a}
            n_new = 0
            cands = [q for q in cands if q["slug"] not in locked_players]
        # per repetir (només el personal): tots els jugadors, també els d'alineacions ja començades, amb les seves cartes
        dups = [q for q in allc if q.get("cards")] if mode == "CAREER" else None
        cands = [q for q in cands if not q.get("locked")]
        used_now = {a["anyCard"]["slug"] for l in keep for a in l["taskAppearances"] if a} if focus else set()  # cartes de les que es mantenen
        taken = set(locked_players)
        lines = []
        # primer es calculen totes les alineacions i després s'assignen a les que ja hi ha per semblança (les mateixes
        # cartes es queden a la mateixa alineació de Sorare; si no, es mourien cartes d'una a l'altra i xocarien)
        picks = []
        for _ in range(len(open_) + n_new):
            p_ = fill(cands, slots, taken, dups, used_now | {q["card"] for q in cands if q["slug"] in taken})
            if not p_:
                break
            picks.append(p_)
            used_now |= {q["card"] for q in p_.values()}
            if any(q.get("dup") for q in p_.values()):
                lines.append("   🔁 repetit amb una altra carta (no quedaven jugadors): " + ", ".join(q["name"] for q in p_.values() if q.get("dup")))
        if len(picks) < len(open_) + n_new:
            lines.append(f"   ⚠️ no hi ha prou jugadors per completar {len(open_) + n_new - len(picks)} alineacions")
            if dups:
                rp = [f"{q['name']} ({q['pos'][0][:2]}, {sum(1 for t in q['cards'] if t[0] not in used_now)} cartes lliures)" for q in dups
                      if q["ok"] and any(t[0] not in used_now for t in q["cards"]) and q["slug"] in taken]
                lines.append("   repetibles (≥80% o titulars, amb una altra carta lliure): " + (", ".join(rp) or "cap"))
            from collections import Counter
            cnt = Counter(ps for q in cands if q["slug"] not in taken for ps in q["pos"])
            miss = [s_["positions"] for s_ in slots if not any(cnt.get(x) for x in s_["positions"])]
            lines.append("   candidats lliures per posició: " + ", ".join(f"{k} {v}" for k, v in cnt.items())
                         + (f" · cap per a: {miss}" if miss else "")
                         + f" · alineacions ja fetes: {len(lineups)} ({sum(len([a for a in l['taskAppearances'] if a]) for l in lineups)} cartes)")
        remaining = list(open_)
        targets = []
        for p_ in picks:
            cards = {q["card"] for q in p_.values()}
            best = max(remaining, key=lambda l: len(cards & {a["anyCard"]["slug"] for a in l["taskAppearances"] if a}), default=None)
            if best is not None:
                remaining.remove(best)
            targets.append((best, p_))
        k_new = 0
        for l, pick in targets:
            if l is None:
                k_new += 1
            name = f"alineació {open_.index(l) + 1}" if l is not None else f"alineació nova {k_new}"
            txt = ", ".join(f"{'🔸' if q['extra'] else ''}{'⚔️' if q.get('rival') else ''}{q['name']} ({q['grade']}, {q['proj']:.0f}, {q['date']:%d/%m %H:%M}Z{', titular' if q['confirmed'] and q['ok'] else ''})"
                            for _, q in sorted(pick.items()))
            if l:
                old = {a["anyCard"]["slug"] for a in l["taskAppearances"] if a}
                if old == {q["card"] for q in pick.values()}:
                    lines.append(f"   ✅ {name} sense canvis: {txt}")
                    continue
            # capità (obligatori, «CaptainScarcity»): el d'impacte més alt; a igualtat, més punts previstos; després, més mitjana (el David, 2/11)
            order = sorted(pick.items(), key=lambda iq: (GRADE.get(iq[1]["grade"], 6), -iq[1]["proj"], -iq[1]["avg"], iq[0]))
            cap_i = order[0][0]
            apps = [{"index": i, "cardSlug": q["card"], "gameId": q["game"]["id"].split(":")[-1], "captain": i == cap_i} for i, q in sorted(pick.items())]
            txt = txt.replace(pick[cap_i]["name"] + " (", pick[cap_i]["name"] + " © (", 1)
            if dry:
                lines.append(f"   (prova) {name}: {txt}")
                continue
            inp = {"stepId": st["id"], "appearances": apps}
            if l:
                inp["lineupId"] = l["id"]
            try:
                d = gql(UPSERT, {"input": inp}, token=token())["upsertStepLineup"]
                if d.get("errors"):
                    raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
                lines.append(f"   {'🔁' if l else '✅'} {name}: {txt}")
                games.add(min((q["game"]["date"] for q in pick.values()), key=D))
                if mode == "CAREER":
                    ds_ = [q["game"]["date"] for q in pick.values()]
                    ends.add((min(ds_, key=D), max(ds_, key=D)))
            except Exception as e:
                lines.append(f"   ❌ {name}: {str(e)[:200]}")
        # revisió final (els últims minuts abans del primer partit de l'alineació): jugadors de partits posteriors que
        # encara no tenen l'onze oficial (Sorare el posa ~1 h abans) → l'impacte no és el definitiu; avís perquè el David
        # l'acabi a mà (decisió del David, 4/11)
        for l, pick in targets:  # imatge per a Telegram (11/11)
            try:
                from bot.tgimg import card, player
                nm = (f"Alineació {open_.index(l) + 1}" if l is not None else "Alineació nova") if mode == "CAREER" else "Tauler d'equip"
                order_ = sorted(pick.items(), key=lambda iq: (GRADE.get(iq[1]["grade"], 6), -iq[1]["proj"], -iq[1]["avg"], iq[0]))
                ps = []
                for i, q in sorted(pick.items()):
                    pp = slots[i]["positions"]
                    pos = pp[0] if len(pp) == 1 else ((q.get("pos") or ["Extra"])[0])  # l'Extra, a la línia de la seva posició (11/11)
                    when = q["date"].astimezone(MAD)
                    sub = f"{(q.get('team') or '').replace('-', ' ')[:13]} · {['dl','dt','dc','dj','dv','ds','dg'][when.weekday()]} {when:%H:%M}"
                    ps.append(player(pos, q["name"] + (" ✓" if q["confirmed"] and q["ok"] else ""), sub, f"{q['grade']} {q['proj']:.0f}",
                                     cap=i == order_[0][0], warn=bool(q.get("rival")), pic=q.get("pic"),
                                     pct="100%" if q["confirmed"] and q["ok"] else (f"{q['pct']}%" if q.get("pct") else "<80%")))
                c_ = card(f"{b.get('title')} · objectiu {st['target']}", ps,
                          tag="Personal" if mode == "CAREER" else "Equip", tag_col="#22d3ee" if mode == "CAREER" else "#a78bfa")
                cq = pick[order_[0][0]]
                c_.update(gw=f"Set · nivell {st['level'] + 1}", num=nm.upper(), cap_name=cq["name"], cap_club=(cq.get("team") or "").replace("-", " "),
                          score=sum(q["proj"] for q in pick.values()))
                cards_img.append(c_)
            except Exception as e:
                print(f"::warning title=set imatge::{str(e)[:150]}")
        if focus and now >= F - dt.timedelta(minutes=6):
            for l, pick in targets:
                late = [q for q in pick.values() if q["date"] > F and not q["confirmed"]]
                if late:
                    nm = f"alineació {open_.index(l) + 1}" if l is not None else "alineació nova"
                    lines.append(f"   ⚠️ {nm}: {', '.join(q['name'] + ' (' + q['date'].astimezone(MAD).strftime('%H:%M') + ')' for q in late)}"
                                 " encara sense onze oficial: l'impacte no és el definitiu. Revisa-la tu quan surtin els onzes.")
        head = f"{label} ({b.get('title')}, nivell {st['level'] + 1}, objectiu {st['target']}, {len(locked)} en joc)"
        rep.append(head + ("\n" + "\n".join(lines) if lines else ""))
    st_ = load_json("sorare_fset.json", {})
    st_["games"] = sorted(g for g in games if D(g) > now)
    st_["spans"] = sorted(list(g) for g in ends if D(g[1]) > now - dt.timedelta(hours=4))
    st_.pop("ends", None)
    if not dry:
        save_json("sorare_fset.json", st_)
    if not dry:  # nivells superats/perduts per al resum del matí (12/11)
        from bot import digest
        for r in rep:
            for ln in r.split("\n"):
                if "🎁" in ln or "🔄" in ln:
                    digest.event(ln.strip())
    for k, r in enumerate(rep):
        print(f"::notice title=set futbol {k + 1}::" + r.replace("\n", " ¶ ")[:3900])
    important = [r for r in rep if any(x in r for x in ("🎁", "🔄", "⚠️", "❌", "🔁", "✅ alineació nova"))]
    if dry:
        telegram("Sorare · Set futbol (prova)\n" + "\n".join(rep))
    elif any(("✅ alineació nova" in r or "🔁" in r or "🎁" in r or "🔄" in r or "❌" in r) for r in rep):
        # imatge amb les alineacions + només les línies importants que no són alineacions (decisió del David, 11/11)
        from bot.tgimg import send_lineups
        extra = [ln.strip() for r in rep if r in important for ln in r.split("\n")
                 if any(x in ln for x in ("🎁", "🔄", "⚠️", "❌"))]
        if not (cards_img and send_lineups(cards_img, caption="\n".join(extra)[:1000] or "Alineacions del Set (✓ = titular confirmat)")):
            telegram("Sorare · Set futbol\n" + "\n".join(r for r in rep if r in important or "✅ alineació nova" in r))


def show_order(n=45):
    """Diagnosi (sorare.yml cmd=fsetorder): l'ordre dels candidats del tauler personal, com el recorre el bot."""
    now = dt.datetime.now(dt.timezone.utc)
    st = gql_step({"m": "CAREER"})["currentUser"]["setBoard"]["myCurrentStep"]
    lineups = [l for l in st.get("myLineups") or [] if l and l.get("taskAppearances")]
    used = {a["anyCard"]["slug"] for l in lineups for a in l["taskAppearances"] if a}
    out = candidates(st["id"], now, used, set())
    P = {"Goalkeeper": "POR", "Defender": "DEF", "Midfielder": "MIG", "Forward": "DAV"}
    lines = [f"{i + 1}. {q['date'].astimezone(MAD):%a %H:%M} · {'/'.join(P.get(x, x) for x in q['pos'])} · {q['name']} ({q['team']}) · "
             f"{q['grade']} {q['proj']:.0f} · mitj. {q['avg']:.0f} · {'titular' if q['confirmed'] and q['ok'] else ('NO titular' if q['confirmed'] else ('≥80%' if q['hi'] else '<80%'))}"
             for i, q in enumerate(out[:n])]
    print("::notice title=ordre Set::" + " ¶ ".join(lines))
