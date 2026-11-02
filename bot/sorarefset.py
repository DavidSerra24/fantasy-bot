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
    anyPlayer { displayName slug ... on Player { activeClub { slug } } }
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


def candidates(step_id, now, used_cards, locked_players):
    """Jugadors disponibles (una carta per jugador, la de més XP) amb partit no començat, ordenats per les normes."""
    from bot.sorarelineup import lineup_status, starts
    all_ = bench(step_id, {"includeUsed": True})
    free = {n["anyCard"]["slug"] for n in bench(step_id, {})}
    hi = {n["anyPlayer"]["slug"] for n in bench(step_id, {"starterOddsBasisPointsRange": {"min": 8000}})}
    best, cache = {}, {}
    for n in all_:
        p, c = n["anyPlayer"], n["anyCard"]
        if p["slug"] in locked_players or (c["slug"] not in free and c["slug"] not in used_cards):
            continue
        games = [g for g in n.get("eligiblePlayerGameScores") or [] if g and g.get("anyGame") and D(g["anyGame"]["date"]) > now + dt.timedelta(seconds=40)]
        if not games:
            continue
        g = min(games, key=lambda g: g["anyGame"]["date"])
        q = {"slug": p["slug"], "name": p["displayName"], "card": c["slug"], "xp": c.get("xp") or 0, "pos": n.get("positions") or [n.get("position")],
             "team": ((p.get("activeClub") or {}).get("slug")), "game": g["anyGame"], "date": D(g["anyGame"]["date"]),
             "grade": ((g.get("projection") or {}).get("grade") or "?"), "proj": g.get("projectedScore") or 0, "hi": p["slug"] in hi}
        cur = best.get(p["slug"])
        if not cur or q["xp"] > cur["xp"]:
            best[p["slug"]] = q
    out = list(best.values())
    for q in out:
        xi = lineup_status(q["game"], cache) if q["date"] < now + dt.timedelta(hours=2) else None
        q["confirmed"] = bool(xi)
        q["ok"] = (starts(xi, q["slug"], q["name"]) if xi else q["hi"])
    out.sort(key=lambda q: (q["date"], GRADE.get(q["grade"], 6), -q["proj"]))
    return out


def rivals(a, b):
    ga, gb = a["game"], b["game"]
    return ga["id"] == gb["id"] and a.get("team") and b.get("team") and a["team"] != b["team"]


def fill(cands, slots, taken):
    """Una alineació: per ordre, cada jugador a la seva casella (o a l'Extra), sense rivals. Primer només els bons (≥80% o
    titulars); si no s'omple, es completa amb els següents («per si de cas»)."""
    pick = {}
    for only_ok in (True, False):
        for q in cands:
            if len(pick) == len(slots):
                break
            if q["slug"] in taken or (only_ok and not q["ok"]) or any(rivals(q, x) for x in pick.values()):
                continue
            free = [i for i, s in enumerate(slots) if i not in pick and set(q["pos"]) & set(s["positions"])]
            if not free:
                continue
            i = min(free, key=lambda i: len(slots[i]["positions"]))  # primer la casella de la seva posició, després l'Extra
            pick[i] = dict(q, extra=not only_ok)
            taken.add(q["slug"])
    return pick if len(pick) == len(slots) else None


def run(dry=False):
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
            games.update(a["game"]["date"] for a in l["taskAppearances"] if a and a.get("game"))
        locked_players = {a["anyPlayer"]["slug"] for l in locked for a in l["taskAppearances"] if a}
        used_cards = {a["anyCard"]["slug"] for l in open_ for a in l["taskAppearances"] if a}
        n_total = (st.get("maxLineupsCount") or 4) if mode == "CAREER" else 1
        n_new = min(st.get("remainingLineupsCount") or 0, max(0, n_total - len(lineups))) if mode == "CAREER" else max(0, 1 - len(lineups))
        cands = candidates(st["id"], now, used_cards, locked_players)
        taken = set(locked_players)
        lines = []
        targets = [(l, f"alineació {k + 1}") for k, l in enumerate(open_)] + [(None, f"alineació nova {k + 1}") for k in range(n_new)]
        for l, name in targets:
            pick = fill(cands, slots, taken)
            if not pick:
                lines.append(f"   ⚠️ {name}: no hi ha prou jugadors per completar-la")
                continue
            txt = ", ".join(f"{'🔸' if q['extra'] else ''}{q['name']} ({q['grade']}, {q['proj']:.0f}, {q['date']:%d/%m %H:%M}Z{', titular' if q['confirmed'] and q['ok'] else ''})"
                            for _, q in sorted(pick.items()))
            if l:
                old = {a["anyCard"]["slug"] for a in l["taskAppearances"] if a}
                if old == {q["card"] for q in pick.values()}:
                    lines.append(f"   ✅ {name} sense canvis: {txt}")
                    continue
            # capità (obligatori, «CaptainScarcity»): el d'impacte més alt; a igualtat, un de camp abans que el porter, i després el primer de la llista
            order = sorted(pick.items(), key=lambda iq: (GRADE.get(iq[1]["grade"], 6), "Goalkeeper" in iq[1]["pos"], iq[0]))
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
                games.update(q["game"]["date"] for q in pick.values())
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
