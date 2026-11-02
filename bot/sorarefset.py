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
from bot.sorareset import CLAIM, RESTART, UPSERT
from bot.web import load_json, save_json

STEP = """query($m: BoardMode!) { currentUser { setBoard(mode: $m, sport: FOOTBALL) { id title
  myCurrentStep { __typename id level state target
    ... on CareerStep { maxLineupsCount remainingLineupsCount }
    myLineups { ... on TaskLineup { id aasmState taskAppearances { ... on TaskAppearanceInterface { index anyPlayer { slug displayName } anyCard { slug } game { id date } } } } }
    displayedTypedRules { key ... on So5AppearancesRule { appearances { name positions sub } } } } } } }"""
BENCH = """query($st: String!, $after: String, $f: BenchFilterInput!) { currentUser { step(id: $st) { myFilteredBench(filters: $f, first: 100, after: $after) {
  pageInfo { hasNextPage endCursor }
  nodes { ... on ComposeTeamBenchCard { position positions anyCard { slug xp }
    anyPlayer { displayName slug ... on Player { activeClub { slug } avg: averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE) } }
    eligiblePlayerGameScores(stepId: $st) { anyGame { id date ... on Game { homeTeam { slug } awayTeam { slug } } }
      projectedScore ... on PlayerGameScore { projection { grade } } } } } } } } }"""
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
    best, cache = {}, {}
    for n in all_:
        p, c = n["anyPlayer"], n["anyCard"]
        # al tauler d'equip es pot posar qualsevol carta, encara que ja sigui en una alineació del personal (el David, 2/11)
        if p["slug"] in locked_players or (not squad and c["slug"] not in free and c["slug"] not in used_cards):
            continue
        games = [g for g in n.get("eligiblePlayerGameScores") or [] if g and g.get("anyGame") and D(g["anyGame"]["date"]) > now + dt.timedelta(seconds=40)]
        if not games:
            continue
        g = min(games, key=lambda g: g["anyGame"]["date"])
        q = {"slug": p["slug"], "name": p["displayName"], "card": c["slug"], "xp": c.get("xp") or 0, "pos": n.get("positions") or [n.get("position")],
             "team": ((p.get("activeClub") or {}).get("slug")), "game": g["anyGame"], "date": D(g["anyGame"]["date"]),
             "grade": ((g.get("projection") or {}).get("grade") or "?"), "proj": g.get("projectedScore") or 0, "avg": p.get("avg") or 0, "hi": p["slug"] in hi}
        cur = best.get(p["slug"])
        if not cur or q["xp"] > cur["xp"]:
            best[p["slug"]] = q
    out = list(best.values())
    for q in out:
        xi = lineup_status(q["game"], cache) if q["date"] < now + dt.timedelta(hours=2) else None
        q["confirmed"] = bool(xi)
        q["ok"] = (starts(xi, q["slug"], q["name"]) if xi else q["hi"])
    # personal: els que juguen abans, després impacte, punts previstos i mitjana; equip: sense «playing soon» (el David, 2/11)
    out.sort(key=lambda q: (() if squad else (q["date"],)) + (GRADE.get(q["grade"], 6), -q["proj"], -q["avg"]))
    return out


def rivals(a, b):
    ga, gb = a["game"], b["game"]
    return ga["id"] == gb["id"] and a.get("team") and b.get("team") and a["team"] != b["team"]


def fill(cands, slots, taken):
    """Una alineació com la fa el David (2/11, 2a explicació): es recorre la llista ordenada (els que juguen abans; dins de
    la mateixa hora, impacte, punts previstos i mitjana) i cada jugador va a la casella de la seva posició (o a l'Extra)
    si n'hi ha una de lliure i no s'enfronta amb cap dels ja posats. Així el millor de la primera hora (Talbi, C 53) entra
    primer i els seus rivals (Selvik, Magnetti, Ajorque) queden fora; el porter surt de l'hora següent (Leo Román).
    Primer només els bons (≥80% o titulars); si no s'omple, es completa amb els següents («per si de cas», 🔸)."""
    pick = {}
    for only_ok in (True, False):
        for q in cands:
            if len(pick) == len(slots):
                break
            if q["slug"] in taken or (only_ok and not q["ok"]) or any(rivals(q, x) for x in pick.values()):
                continue
            free = [i for i, s_ in enumerate(slots) if i not in pick and set(q["pos"]) & set(s_["positions"])]
            if not free:
                continue
            i = min(free, key=lambda i: len(slots[i]["positions"]))  # la casella de la seva posició abans que l'Extra
            pick[i] = dict(q, extra=not only_ok)
            taken.add(q["slug"])
    return pick if len(pick) == len(slots) else None


def run(dry=False, focus=None):
    """focus = hora (ISO) del primer partit d'unes alineacions: revisió final només d'aquelles (les altres es mantenen;
    decisió del David, 2/11). Sense focus (cada hora): es refan totes les que no han començat i s'omplen les que falten."""
    now = dt.datetime.now(dt.timezone.utc)
    rep, games = [], set()
    for mode in ("CAREER", "SQUAD"):
        label = f"⚽ Set · {'personal' if mode == 'CAREER' else 'equip'}"
        b = gql(STEP, {"m": mode}, token=token())["currentUser"]["setBoard"]
        st = (b or {}).get("myCurrentStep")
        if not st:
            continue
        if st["state"] == "CLAIMABLE" and not dry:
            try:
                d = gql(CLAIM, {"input": {"stepId": st["id"]}}, token=token())["acknowledgeStep"]
                if d.get("errors"):
                    raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
                rep.append(f"🎁 {label}: nivell {st['level'] + 1} superat, recompensa reclamada")
            except Exception as e:
                rep.append(f"⚠️ {label}: no he pogut reclamar ({str(e)[:150]})")
            b = gql(STEP, {"m": mode}, token=token())["currentUser"]["setBoard"]; st = b["myCurrentStep"]
        if st["state"] == "FAILED" and mode == "CAREER" and not dry:
            try:
                d = gql(RESTART, {"input": {"taskId": b["id"]}}, token=token())["restartTasksTrack"]
                if d.get("errors"):
                    raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
                rep.append(f"🔄 {label}: nivell {st['level'] + 1} perdut; he reiniciat el tauler ({b.get('title')})")
            except Exception as e:
                rep.append(f"⚠️ {label}: nivell perdut i no he pogut reiniciar ({str(e)[:150]})")
            b = gql(STEP, {"m": mode}, token=token())["currentUser"]["setBoard"]; st = b["myCurrentStep"]
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
        locked_players = {a["anyPlayer"]["slug"] for l in locked for a in l["taskAppearances"] if a}
        used_cards = {a["anyCard"]["slug"] for l in open_ for a in l["taskAppearances"] if a}
        n_total = (st.get("maxLineupsCount") or 4) if mode == "CAREER" else 1
        n_new = min(st.get("remainingLineupsCount") or 0, max(0, n_total - len(lineups))) if mode == "CAREER" else max(0, 1 - len(lineups))
        cands = candidates(st["id"], now, used_cards, locked_players, squad=mode == "SQUAD")
        first = lambda l: min((D(a["game"]["date"]) for a in l["taskAppearances"] if a and a.get("game")), default=None)
        if focus:  # només les alineacions que comencen a aquesta hora; els jugadors de les altres es queden on són
            F = D(focus)
            keep = [l for l in open_ if first(l) != F]
            open_ = [l for l in open_ if first(l) == F]
            locked_players |= {a["anyPlayer"]["slug"] for l in keep for a in l["taskAppearances"] if a}
            n_new = 0
            cands = [q for q in cands if q["slug"] not in locked_players]
        taken = set(locked_players)
        lines = []
        # primer es calculen totes les alineacions i després s'assignen a les que ja hi ha per semblança (les mateixes
        # cartes es queden a la mateixa alineació de Sorare; si no, es mourien cartes d'una a l'altra i xocarien)
        picks = []
        for _ in range(len(open_) + n_new):
            p_ = fill(cands, slots, taken)
            if not p_:
                break
            picks.append(p_)
        if len(picks) < len(open_) + n_new:
            lines.append(f"   ⚠️ no hi ha prou jugadors per completar {len(open_) + n_new - len(picks)} alineacions")
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
            txt = ", ".join(f"{'🔸' if q['extra'] else ''}{q['name']} ({q['grade']}, {q['proj']:.0f}, {q['date']:%d/%m %H:%M}Z{', titular' if q['confirmed'] and q['ok'] else ''})"
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
            except Exception as e:
                lines.append(f"   ❌ {name}: {str(e)[:200]}")
        head = f"{label} ({b.get('title')}, nivell {st['level'] + 1}, objectiu {st['target']}, {len(locked)} en joc)"
        rep.append(head + ("\n" + "\n".join(lines) if lines else ""))
    st_ = load_json("sorare_fset.json", {})
    st_["games"] = sorted(g for g in games if D(g) > now)
    if not dry:
        save_json("sorare_fset.json", st_)
    for k, r in enumerate(rep):
        print(f"::notice title=set futbol {k + 1}::" + r.replace("\n", " ¶ ")[:3900])
    important = [r for r in rep if any(x in r for x in ("🎁", "🔄", "⚠️", "❌", "🔁", "✅ alineació nova"))]
    if dry:
        telegram("Sorare · Set futbol (prova)\n" + "\n".join(rep))
    elif any(("✅ alineació nova" in r or "🔁" in r or "🎁" in r or "🔄" in r or "❌" in r) for r in rep):
        telegram("Sorare · Set futbol\n" + "\n".join(r for r in rep if r in important or "✅ alineació nova" in r))
