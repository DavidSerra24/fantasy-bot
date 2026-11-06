"""Sorare Pro · alineacions Classic de la propera jornada (per l'API oficial).

Regles del David (CLAUDE.md, «Sorare Pro»):
- Només Classic. Primer Rare (1 alineació, a la primera competició possible), després Limited (fins a 4 per competició).
  Prioritat: U23 (només si hi ha porter U23 titular) → Champion → All Star.
- Tots els jugadors amb ≥80% de ser titulars (filtre de titularitat de Sorare, que és el de SorareInside).
- Ordre: impacte previst (A → F); a igualtat, l'ordre de la llista de Sorare.
- Sense repetir jugadors entre alineacions; sense jugadors d'equips que s'enfrontin.
- Capità: el d'impacte més alt; si empaten i un és porter, el de camp; si no, el primer de la llista.
- Cartes repetides: la de més XP.
- Bonificació: màxim 2 jugadors del mateix club i suma de mitjanes ≤ 370; es quadra canviant el que menys impacte perdi.
- Girona: no a All Star (Arena del David), excepte si l'essència Rare és < 100 (llavors sí, a All Star Rare).
- Gazzaniga: es reserven 2 Limited (i 1 Rare si no va a All Star Rare); els que sobrin, sempre els últims.
- Arena (Beginner, 100 d'essència): amb els sobrants, només una PROPOSTA per Telegram; mai sense el «sí» del David.
Seguretat: només llegeix i (quan s'activi) envia alineacions. Mai compra, ven, fa ofertes ni mou diners.
Ús: python -m bot.sorarelineup [dry|fill|final]  (dry: només proposta; fill: omple/actualitza; final: fill + Arena amb el «sí»)
"""
import argparse

from bot.notify import telegram
from bot.sorare import gql, token

GRADE = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0}
COMPS = [("U23", "under_twenty_one"), ("Champion", "seasonal-champions"), ("All Star", "seasonal-all_star-all_seasons_all_star_")]
CAP = 370  # bonificació Classic: suma de mitjanes L10 jugades ≤ 370
ARENA_CAP = 260  # Arena Beginner: límit obligatori de la suma de mitjanes
# Classic (Pro): 7 jugadors (índexs 0-6 com a Sorare); Arena: 5
CLASSIC = ["Goalkeeper", "Defender", "Defender", "Midfielder", "Midfielder", "Forward", "Extra"]
ARENA = ["Goalkeeper", "Defender", "Midfielder", "Forward", "Extra"]
LOG = []
SHORT = {"Goalkeeper": "POR", "Defender": "DEF", "Midfielder": "MIG", "Forward": "DAV", "Extra": "EXT"}

FIXTURE = """query { so5 { so5Fixture(sport: FOOTBALL, type: UPCOMING, eventType: CLASSIC) { slug gameWeek cutOffDate
  so5Leaderboards { id slug displayName mainRarityType isArena format { title entryItem { id myEntryItemId ... on So5CardShardsEntryItem { quantity rarity } } } }
  mySo5Lineups { id so5Leaderboard { slug displayName isArena format { title } } so5Appearances { captain anyCard { slug } anyPlayer { displayName slug } } } } } }"""

SAVE = """mutation($input: createOrUpdateSo5LineupInput!) { createOrUpdateSo5Lineup(input: $input) {
  so5Lineup { id } errors { message code } } }"""
DELETE = """mutation($input: deleteSo5LineupInput!) { deleteSo5Lineup(input: $input) { errors { message code } } }"""
GKS = """query($slug: String!, $r: RangeInput, $after: String) { so5 { so5Leaderboard(slug: $slug) {
  myBench(first: 50, after: $after, includeUsed: true, positions: [Goalkeeper], starterOddsBasisPointsRange: $r) { pageInfo { hasNextPage endCursor } nodes {
    ... on ComposeTeamBenchCard { anyCard { slug rarityTyped } anyPlayer { displayName slug activeClub { name } }
      eligiblePlayerGameScores(so5LeaderboardSlug: $slug) { anyGame { id date homeTeam { name } awayTeam { name } } } } } } } } }"""

BENCH = """query($slug: String!, $r: RangeInput, $after: String, $pos: [Position!]) { so5 { so5Leaderboard(slug: $slug) {
  myBench(first: 50, after: $after, includeUsed: true, starterOddsBasisPointsRange: $r, positions: $pos) { pageInfo { hasNextPage endCursor } nodes {
    ... on ComposeTeamBenchCard { position positions avg10: averageScore(type: LAST_TEN_PLAYED_SO5_AVERAGE_SCORE) avg15: averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE)
      anyCard { slug rarityTyped xp }
      anyPlayer { displayName slug age activeClub { name slug } ... on Player { position } }
      eligiblePlayerGameScores(so5LeaderboardSlug: $slug) { projection { grade score } anyGame { id date homeTeam { name } awayTeam { name } } } } } } } } }"""

ESSENCE = """query { currentUser { cardShardsChests(sport: FOOTBALL) { rarity cardShardsCount } } }"""

PREVIEW = """query($slug: String!, $a: [So5AppearanceInput!]!) { so5 { so5Leaderboard(slug: $slug) {
  previewSo5Lineup(appearances: $a) { rewardMultiplier feedbackRules { ruleName state message } } } } }"""


def bench(slug, rng=None, pos=None):
    out, after = [], None
    for _ in range(20):
        d = gql(BENCH, {"slug": slug, "r": rng, "after": after, "pos": pos}, token=token())["so5"]["so5Leaderboard"]["myBench"]
        out += [n for n in d["nodes"] if n]
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    return out


def cards(lb, floor=8000, rarities=None):
    """Cartes de la competició (de la seva raresa) amb ≥80% (o ≥ floor), una per jugador (la de més XP), en ordre de la
    llista. Amb floor < 8000 (All Star Rare quan no n'hi ha prou; decisió del David, 3/11) cada carta porta «tier»:
    0 = ≥80%, 1 = 70%, 2 = 60%…, i els de més % van primer."""
    # la llista sense filtre és la de la posició Extra (jugadors de camp); els porters van a part
    tier = {}
    for t, lo in enumerate(range(8000, floor - 1, -1000)):
        rng = {"min": lo} if lo == 8000 else {"min": lo, "max": lo + 999}
        for n in bench(lb["slug"], rng) + bench(lb["slug"], rng, ["Goalkeeper"]):
            tier.setdefault(n["anyCard"]["slug"], t)
    ok = set(tier)
    allc = bench(lb["slug"]) + bench(lb["slug"], None, ["Goalkeeper"])
    LOG.append(f"{lb['displayName']}: {len(allc)} cartes, {len(ok)} amb ≥80%")
    seen, copies, gazza = {}, {}, []
    for i, n in enumerate(allc):
        c, p = n["anyCard"], n["anyPlayer"]
        if (c["rarityTyped"].lower() not in rarities if rarities else c["rarityTyped"].lower() != (lb["mainRarityType"] or "").lower()) or c["slug"] not in ok:
            continue
        g = (n.get("eligiblePlayerGameScores") or [{}])[0] or {}
        game = g.get("anyGame") or {}
        club = (p.get("activeClub") or {}).get("name") or ""
        teams = [(game.get("homeTeam") or {}).get("name"), (game.get("awayTeam") or {}).get("name")]
        q = {"card": c["slug"], "xp": c["xp"] or 0, "name": p["displayName"], "player": p["slug"], "club": club,
             "pos": n.get("position") or p.get("position"), "poss": [n.get("position") or p.get("position")],  # la posició de la carta "age": p.get("age"),
             "avg": n.get("avg10") or 0, "avg15": n.get("avg15") or 0, "idx": i,
             "grade": ((g.get("projection") or {}).get("grade")), "proj": (g.get("projection") or {}).get("score"),
             "game": game.get("id"), "gobj": game, "date": game.get("date"), "rival": next((t for t in teams if t and t != club), None),
             "girona": "girona" in club.lower(), "gazza": "gazzaniga" in p["slug"], "tier": tier.get(c["slug"], 0)}
        q["imp"] = GRADE.get(q["grade"], -1)
        copies[q["player"]] = copies.get(q["player"], 0) + 1
        if q["gazza"]:
            gazza.append(q)
        if q["player"] not in seen or q["xp"] > seen[q["player"]]["xp"]:
            seen[q["player"]] = q
    for q in seen.values():
        q["copies"] = copies[q["player"]]
    if gazza and (lb["mainRarityType"] or "").lower() == "limited":
        # Gazzaniga Limited: es reserven 2 per a l'Arena del David; la resta es poden fer servir (encara que sigui
        # repetir jugador), cada còpia en una alineació diferent i sempre les últimes (la segona després de la primera)
        for q in list(seen.values()):
            if q["gazza"]:
                del seen[q["player"]]
        gazza.sort(key=lambda q: -q["xp"])
        for k, q in enumerate(gazza[:max(0, len(gazza) - 2)]):
            seen[f"{q['player']}#{k}"] = dict(q, player=f"{q['player']}#{k}", gazza=k + 1)
    out = sorted(seen.values(), key=lambda q: q["idx"])
    LOG.append(f"   porters ≥80%: {', '.join(q['name'] + (' #' + str(q['gazza']) if q['gazza'] else '') for q in out if q['pos'] == 'Goalkeeper') or 'cap'}")
    return out


def order(pool):
    # gk_arena posa «tier» (0 = titular confirmat, 1 = 80–90%): primer els confirmats
    # a igualtat de lletra, els punts previstos de Sorare (el número d'on surt la lletra) i després la mitjana L15, com
    # al Set de futbol (decisió del David, 4/11)
    return sorted(pool, key=lambda q: (q.get("tier", 0), q["gazza"] is not True and q["gazza"] >= 2, -q["imp"], -(q.get("proj") or 0), -(q.get("avg15") or q.get("avg") or 0), q["idx"]))


# Norma de rivals (decisió del David, 4/11): "all" = cap jugador amb un del rival; si no surt cap alineació, "back" =
# cap porter ni defensa amb un rival (migcampistes i davanters rivals sí); si tampoc, "none" = sense norma.
RIVALS = ["all"]
BACK = ("Goalkeeper", "Defender")


def faces(a, b):
    if RIVALS[0] == "none" or not (a["game"] and a["game"] == b["game"] and a["club"] != b["club"]):
        return False
    return RIVALS[0] == "all" or a["pos"] in BACK or b["pos"] in BACK


def fits(q, slot):
    if slot == "Extra":
        return q["pos"] != "Goalkeeper"
    return slot == q["pos"] or slot in q["poss"]


def build(pool, slots, cap=CAP, avg="avg", hard=False):
    """Sense rivals; si així no surt cap alineació, amb rivals (es marquen amb «rivals» a cada jugador)."""
    pick = None
    try:
        for lvl in ("all", "back", "none"):
            RIVALS[0] = lvl
            pick = _build(pool, slots, cap, avg, hard)
            if pick is not None:
                if lvl != "all":
                    pick = [dict(q, rivals=lvl) for q in pick]
                break
    finally:
        RIVALS[0] = "all"
    return pick


def _build(pool, slots, cap=CAP, avg="avg", hard=False):
    """Alineació (llista de jugadors per casella, en l'ordre de `slots`) o None. Ordre: impacte i llista; sense rivals.
    Cada jugador va a la casella de la seva posició; si està plena, a una altra de les seves posicions i, si no, a Extra.
    Després quadra la bonificació (màx. 2 per club i suma de mitjanes ≤ cap). Amb hard=True, el límit és obligatori."""
    pick = [None] * len(slots)
    for q in order(pool):
        if any(o and faces(q, o) for o in pick):
            continue
        free = [k for k, s_ in enumerate(slots) if pick[k] is None and s_ != "Extra" and fits(q, s_)]
        free.sort(key=lambda k: slots[k] != q["pos"])
        if not free and q["pos"] != "Goalkeeper":
            free = [k for k, s_ in enumerate(slots) if pick[k] is None and s_ == "Extra"]
        if free:
            pick[free[0]] = q
        if all(pick):
            break
    if not all(pick):
        return None
    pick = fit_bonus(pick, pool, slots, cap, avg, hard)
    return pick


def bonus_bad(pick, cap, avg, hard):
    from collections import Counter
    clubs = Counter(q["club"] for q in pick)
    over = max(0, sum(q[avg] for q in pick) - cap)
    return over if hard else sum(max(0, v - 2) for v in clubs.values()) * 1000 + over


def fit_bonus(pick, pool, slots, cap, avg, hard):
    """Canvis fins a complir la bonificació (o el límit obligatori), perdent el mínim d'impacte.
    Primer un sol canvi; si cap canvi sol no hi arriba, parelles de canvis (error del 5/11: amb 10 canvis petits
    d'un en un, All Star Limited #1 i #2 es quedaven a 401 i 408/370)."""
    bad = bonus_bad(pick, cap, avg, hard)
    if not bad:
        return pick
    used = {q["player"] for q in pick}

    def options(cur_pick, k, extra_used=()):
        for c in pool:
            if c["player"] in used or c["player"] in extra_used or not fits(c, slots[k]):
                continue
            if any(faces(c, o) for j, o in enumerate(cur_pick) if j != k):
                continue
            yield c

    def loss(old, new):
        # impacte perdut, després els Gazzaniga repetits al final, després l'ordre de la llista
        return (sum(o["imp"] - n["imp"] for o, n in zip(old, new)),
                sum(n["gazza"] is not True and n["gazza"] >= 2 for n in new), sum(n["idx"] for n in new))

    best = None
    for k, cur in enumerate(pick):
        for c in options(pick, k):
            new = pick[:k] + [c] + pick[k + 1:]
            if not bonus_bad(new, cap, avg, hard):
                key = loss([cur], [c])
                if best is None or key < best[0]:
                    best = (key, new)
    # parelles de canvis: només els candidats que baixen la mitjana (els 12 de més impacte per casella)
    cands = {}
    for k, cur in enumerate(pick):
        cs = [c for c in options(pick, k) if c[avg] < cur[avg]]
        cs.sort(key=lambda c: (-c["imp"], c["idx"]))
        cands[k] = cs[:12]
    for k1 in range(len(pick)):
        for k2 in range(k1 + 1, len(pick)):
            for c1 in cands[k1]:
                for c2 in cands[k2]:
                    if c1["player"] == c2["player"] or faces(c1, c2):
                        continue
                    new = list(pick)
                    new[k1], new[k2] = c1, c2
                    if any(faces(new[k], o) for k in (k1, k2) for j, o in enumerate(new) if j != k):
                        continue
                    if not bonus_bad(new, cap, avg, hard):
                        key = loss([pick[k1], pick[k2]], [c1, c2])
                        if best is None or key < best[0]:
                            best = (key, new)
    if best:
        return best[1]
    # si ni així, canvis d'un en un (el que més baixi per impacte perdut), com abans
    for _ in range(20):
        bad = bonus_bad(pick, cap, avg, hard)
        if not bad:
            return pick
        used = {q["player"] for q in pick}
        step = None
        for k, cur in enumerate(pick):
            for c in options(pick, k):
                new = pick[:k] + [c] + pick[k + 1:]
                nb = bonus_bad(new, cap, avg, hard)
                if nb >= bad:
                    continue
                key = (cur["imp"] - c["imp"], nb, c["idx"])
                if step is None or key < step[0]:
                    step = (key, new)
        if not step:
            break
        pick = step[1]
    return None if hard and bonus_bad(pick, cap, avg, hard) else pick


def clean_level(pick):
    """Norma de rivals més estricta que compleix l'alineació: 0 = cap rival, 1 = només migcampistes/davanters, 2 = cap."""
    try:
        for i, lvl in enumerate(("all", "back")):
            RIVALS[0] = lvl
            if not any(faces(a, b) for x, a in enumerate(pick) for b in pick[x + 1:]):
                return i
        return 2
    finally:
        RIVALS[0] = "all"


def swap_rivals(pick, others, slots=CLASSIC, cap=CAP, avg="avg"):
    """(6/11, el David: Mbeumo ↔ Félix Correia) Si una alineació només surt amb rivals, prova d'intercanviar un jugador
    amb una alineació anterior de la mateixa competició: els mateixos jugadors, però repartits sense rivals.
    Només si l'altra alineació no empitjora (rivals i bonificació). Retorna (pick, índex de l'altra, altra nova) o None."""
    lvl0 = clean_level(pick)
    if lvl0 == 0:
        return None
    best = None
    for oi, other in enumerate(others):
        ol0, ob0 = clean_level(other), bonus_bad(other, cap, avg, False)
        pb0 = bonus_bad(pick, cap, avg, False)
        for k, a in enumerate(pick):
            for j, b in enumerate(other):
                if not (fits(b, slots[k]) and fits(a, slots[j])):
                    continue
                np_ = pick[:k] + [b] + pick[k + 1:]
                no_ = other[:j] + [a] + other[j + 1:]
                l1, l2 = clean_level(np_), clean_level(no_)
                if l1 >= lvl0 or l2 > ol0 or bonus_bad(np_, cap, avg, False) > pb0 or bonus_bad(no_, cap, avg, False) > ob0:
                    continue
                key = (l1, l2, abs(a["imp"] - b["imp"]))
                if best is None or key < best[0]:
                    best = (key, np_, oi, no_)
    return best and best[1:]


def captain(pick):
    return min(pick, key=lambda q: (-q["imp"], q["pos"] == "Goalkeeper", q["idx"]))


def preview(lb, pick, cap):
    a = [{"cardSlug": q["card"], "captain": q is cap, "index": i} for i, q in enumerate(pick)]
    try:
        d = gql(PREVIEW, {"slug": lb["slug"], "a": a}, token=token())["so5"]["so5Leaderboard"]["previewSo5Lineup"]
        bad = [f"{r['ruleName']}: {r['message'] or r['state']}" for r in (d.get("feedbackRules") or []) if r["state"] == "INVALID"]
        return f"×{d['rewardMultiplier']}" + (" | ❗ " + "; ".join(bad) if bad else "")
    except Exception as e:
        return f"(sense previsualització: {str(e)[:120]})"


def describe(pick, cap, slots=CLASSIC):
    from collections import Counter
    clubs = Counter(q["club"] for q in pick)
    total = sum(q["avg"] for q in pick)
    s = ", ".join(f"{SHORT[sl]} {q['name']}{' ©' if q is cap else ''} ({q['grade'] or '?'}, {q['avg']:.0f})" for sl, q in zip(slots, pick))
    flags = ("✅" if max(clubs.values()) <= 2 else "⚠️ >2 d'un club") + " · " + (f"✅ {total:.0f}/370" if total <= CAP else f"⚠️ {total:.0f}/370")
    lv = next((q.get("rivals") for q in pick if q.get("rivals")), None)
    if lv == "back":
        flags += " · ⚠️ amb migcampistes/davanters d'equips que s'enfronten (sense rivals no sortia)"
    elif lv:
        flags += " · ⚠️ amb jugadors d'equips que s'enfronten, també porter/defensa (no sortia d'una altra manera)"
    return s + " · " + flags


def save_lineup(lb, pick, cap, entry=None):
    inp = {"so5LeaderboardId": lb["id"], "so5Appearances": [{"cardSlug": q["card"], "captain": q is cap, "index": i} for i, q in enumerate(pick)]}
    if entry:
        inp["entryItemId"] = entry
    d = gql(SAVE, {"input": inp}, token=token())["createOrUpdateSo5Lineup"]
    if d.get("errors"):
        raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
    return d["so5Lineup"]["id"]


def delete_lineup(lid):
    d = gql(DELETE, {"input": {"so5LineupId": lid}}, token=token())["deleteSo5Lineup"]
    if d.get("errors"):
        raise RuntimeError("; ".join(e["message"] for e in d["errors"]))


def sync(fx, plan, rep):
    """Deixa a Sorare exactament les alineacions Classic del pla: es queden les que ja són iguals (mateixes cartes i
    capità), s'esborren les altres i es creen les que falten (primer esborrar, perquè les cartes quedin lliures)."""
    have = [l for l in fx.get("mySo5Lineups") or [] if not l["so5Leaderboard"]["isArena"] and l["so5Leaderboard"]["format"]["title"] == "Classic"]
    def sig_have(l):
        return (l["so5Leaderboard"]["slug"], frozenset(a["anyCard"]["slug"] for a in l["so5Appearances"]),
                next((a["anyCard"]["slug"] for a in l["so5Appearances"] if a["captain"]), None))
    def sig_plan(lb, pick, cap):
        return (lb["slug"], frozenset(q["card"] for q in pick), cap["card"])
    keep, todo = set(), []
    hs = {l["id"]: sig_have(l) for l in have}
    for lb, pick, cap in plan:
        sp = sig_plan(lb, pick, cap)
        match = next((lid for lid, sh in hs.items() if sh == sp and lid not in keep), None)
        if match:
            keep.add(match)
        else:
            todo.append((lb, pick, cap))
    errs, deleted, created = [], 0, 0
    for l in have:
        if l["id"] not in keep:
            try:
                delete_lineup(l["id"]); deleted += 1
            except Exception as e:
                errs.append(f"esborrar {l['so5Leaderboard']['displayName']}: {str(e)[:150]}")
    for lb, pick, cap in todo:
        try:
            save_lineup(lb, pick, cap); created += 1
        except Exception as e:
            errs.append(f"{lb['displayName']} ({', '.join(q['name'] for q in pick[:3])}…): {str(e)[:200]}")
    after = gql(FIXTURE, token=token())["so5"]["so5Fixture"]["mySo5Lineups"]
    n_ok = sum(1 for l in after if not l["so5Leaderboard"]["isArena"] and l["so5Leaderboard"]["format"]["title"] == "Classic")
    rep.append(f"{'✅' if not errs and n_ok == len(plan) else '⚠️'} Sorare: {len(keep)} sense canvis, {deleted} esborrades, {created} noves → ara n'hi ha {n_ok} de {len(plan)}"
               + ("" if not errs else " | ❗ " + " | ".join(errs)))


def gk_watch(fx, rep):
    """Porters Limited amb 20–70% de ser titulars (més del 10% i menys del 80%): es desen (state/sorare_gkwatch.json) perquè el planificador avisi
    1 h 15 min abans del seu partit i comprovi si són titulars (onze oficial de Sorare)."""
    from bot.web import save_json
    arena = next((l for l in fx["so5Leaderboards"] if l["isArena"] and "beginner" in l["slug"]), None)
    if not arena:
        return
    out = {}
    for lo in range(2000, 8000, 1000):  # més del 10% i menys del 80%: 20, 30, 40, 50, 60 i 70%
        hi, label = lo + 999, f"{lo // 100}%"
        after = None
        for _ in range(10):
            d = gql(GKS, {"slug": arena["slug"], "r": {"min": lo, "max": hi}, "after": after}, token=token())["so5"]["so5Leaderboard"]["myBench"]
            for n in d["nodes"]:
                if not n or n["anyCard"]["rarityTyped"].lower() != "limited":
                    continue
                g = ((n.get("eligiblePlayerGameScores") or [{}])[0] or {}).get("anyGame") or {}
                if not g.get("id"):
                    continue
                p = n["anyPlayer"]
                out[p["slug"]] = {"name": p["displayName"], "slug": p["slug"], "club": (p.get("activeClub") or {}).get("name"), "pct": label,
                                  "game": g["id"], "date": g["date"], "home": (g.get("homeTeam") or {}).get("name"), "away": (g.get("awayTeam") or {}).get("name")}
            if not d["pageInfo"]["hasNextPage"]:
                break
            after = d["pageInfo"]["endCursor"]
    import datetime as _dt
    from bot.web import load_json
    for g in out.values():
        g["fixture"] = fx["slug"]
    old = load_json("sorare_gkwatch.json", {})
    now = _dt.datetime.now(_dt.timezone.utc)
    for g in old.get("gks", []):  # els porters de la jornada en joc (després del tancament) es mantenen fins al seu partit
        g.setdefault("fixture", old.get("fixture"))
        if g["slug"] not in out and _dt.datetime.fromisoformat(g["date"].replace("Z", "+00:00")) > now and g["fixture"] != fx["slug"]:
            out[g["slug"] + "|" + g["game"]] = g
    save_json("sorare_gkwatch.json", {"fixture": fx["slug"], "gks": sorted(out.values(), key=lambda g: g["date"])})
    if out:
        from zoneinfo import ZoneInfo
        import datetime as dt
        M = ZoneInfo("Europe/Madrid")
        rep.append("🧤 Porters a vigilar (et l'aviso 1 h 15 min abans i miro si són titulars): " + ", ".join(
            f"{g['name']} ({g['pct']}, {dt.datetime.fromisoformat(g['date'].replace('Z', '+00:00')).astimezone(M):%a %H:%M})" for g in sorted(out.values(), key=lambda g: g["date"])))


GAME = """query($id: ID!) { football { game(id: $id) { date homeTeam { name } awayTeam { name }
  homeFormation { startingLineupAvailable startingLineup { slug } bench { slug } }
  awayFormation { startingLineupAvailable startingLineup { slug } bench { slug } } } } }"""


def gk_check(gid, mins):
    """Avís i comprovació d'un partit amb porters vigilats: a 75 min avisa; a cada comprovació, si l'onze oficial
    ja és a Sorare, diu si cada porter és titular (i ja no es torna a comprovar)."""
    import datetime as dt
    from zoneinfo import ZoneInfo
    from bot.web import load_json, save_json
    gks = [g for g in load_json("sorare_gkwatch.json", {}).get("gks", []) if g["game"] == gid]
    done = load_json("sorare_gkdone.json", {})
    if not gks or done.get(gid):
        return
    g0 = gks[0]
    hhmm = dt.datetime.fromisoformat(g0["date"].replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/Madrid")).strftime("%H:%M")
    who = ", ".join(f"{g['name']} ({g['pct']})" for g in gks)
    lines = []
    xi = lineup_status({"id": gid, "date": g0["date"], "home": g0["home"], "away": g0["away"]}, {})
    if xi:
        for g in gks:
            ok = starts(xi, g["slug"], g["name"])
            lines.append(f"{'✅' if ok else '❌'} {g['name']} ({g['club']}) {'és TITULAR' if ok else 'NO és titular'} (onze de {'Sorare' if xi[0] == 'sorare' else 'FotMob'})")
        done[gid] = True
        save_json("sorare_gkdone.json", done)
        st = load_json("sorare_gkarena.json", {})
        for g in gks:
            if not starts(xi, g["slug"], g["name"]):
                continue
            g = dict(g, fixture=g.get("fixture") or load_json("sorare_gkwatch.json", {}).get("fixture"))
            try:
                res = gk_arena(g)
            except Exception as e:
                res = None
                print("::warning title=sorare arena porter::" + str(e)[:300])
            if res:
                lb, pick, cap, entry = res
                import time as _t
                first = min(q["date"] for q in pick)
                sub = first - dt.timedelta(minutes=5)
                key = g["slug"] + "|" + gid
                st[key] = {"game": gid, "gk": g, "at": int(_t.time()), "status": "proposed", "submit_at": sub.isoformat()}
                M = ZoneInfo("Europe/Madrid")
                lines.append(f"🏟️ Proposta d'Arena (100 d'essència): {arena_text(pick, cap)}\n"
                             f"La faig? Respon «sí». L'envio a les {sub.astimezone(M):%H:%M} (5 min abans del primer partit, {first.astimezone(M):%H:%M}), "
                             f"amb els titulars confirmats en aquell moment.")
                from bot.web import load_json as _lj, save_json as _sj  # acció dinàmica dins de la mateixa execució
                _sj("dyn_actions.json", _lj("dyn_actions.json", []) + [{"key": f"sorarearena:{key}", "at": sub.isoformat(), "do": "sorarearena",
                                                                        "comp": key, "deadline": first.isoformat()}])
            else:
                lines.append(f"🏟️ Amb {g['name']} no surt cap Arena vàlida (falten jugadors titulars o del 80–90%).")
        save_json("sorare_gkarena.json", st)
    head = f"🧤 {g0['home']} – {g0['away']} ({hhmm})"
    if lines:
        telegram(head + " · onze oficial:\n" + "\n".join(lines))
    elif mins >= 75:
        telegram(f"{head}: porter a vigilar per a l'Arena: {who}. Quan surti l'onze oficial et dic si juga.")
    elif mins <= 12:
        telegram(f"{head}: encara no hi ha onze oficial (ni a Sorare ni a FotMob) per a {who}. Mira-ho a X.")
    print(f"::notice title=sorare porters::{head} · {mins} min · " + ("; ".join(lines) or "sense onze oficial encara"))


FIXTURE_SLUG = FIXTURE.replace("query {", "query($s: String!) {").replace("so5Fixture(sport: FOOTBALL, type: UPCOMING, eventType: CLASSIC)", "so5Fixture(slug: $s)")
YES = r"s[ií]\W*|yes\W*|ok\W*|endavant\W*|fes-la\W*|fes-les\W*"


def lineup_status(game, cache):
    """Onze oficial d'un partit: primer Sorare; si encara no hi és, FotMob (sovint surt abans, quan el club el publica).
    Retorna None si encara no se sap, o ("sorare", slugs) / ("fotmob", noms)."""
    import datetime as dt
    from bot import fotmob
    gid = game["id"]
    if gid not in cache:
        cache[gid] = None
        try:
            gm = gql(GAME, {"id": gid.split(":", 1)[-1]}, token=token())["football"]["game"]
            if all((gm.get(side) or {}).get("startingLineupAvailable") for side in ("homeFormation", "awayFormation")):
                cache[gid] = ("sorare", {p["slug"] for side in ("homeFormation", "awayFormation") for row in gm[side]["startingLineup"] for p in row})
        except Exception:
            pass
        if cache[gid] is None:
            try:
                names = fotmob.starters((game.get("homeTeam") or {}).get("name") or game.get("home") or "", (game.get("awayTeam") or {}).get("name") or game.get("away") or "",
                                        dt.datetime.fromisoformat(game["date"].replace("Z", "+00:00")))
                if names:
                    cache[gid] = ("fotmob", names)
            except Exception:
                pass
    return cache[gid]


def starts(st, slug, name):
    from bot import fotmob
    if st[0] == "sorare":
        return slug in st[1]
    return any(fotmob.same_player(name, n) for n in st[1])


def gk_arena(gk, final=False):
    """Arena Beginner amb un porter vigilat que és titular. Els altres 4: primer els titulars confirmats (per impacte),
    i si d'una posició no n'hi ha, els del 80–90% (com el Pro). Poden jugar abans o després del porter, però l'Arena es
    tanca quan comença el primer partit de qualsevol jugador: s'envia 5 min abans d'aquest primer partit (submit_at).
    Amb final=True (en enviar-la), els d'un partit que ja hauria de tenir onze i encara no se sap si juguen, fora.
    Retorna (lb, pick, cap, entry) o None."""
    import datetime as dt
    fx = gql(FIXTURE_SLUG, {"s": gk["fixture"]}, token=token())["so5"]["so5Fixture"]
    arena = next((l for l in fx["so5Leaderboards"] if l["isArena"] and "beginner" in l["slug"]), None)
    if not arena:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    busy = {a["anyCard"]["slug"] for l in fx.get("mySo5Lineups") or [] for a in l["so5Appearances"]}
    busy_p = {a["anyPlayer"].get("slug") for l in fx.get("mySo5Lineups") or [] for a in l["so5Appearances"]}  # sense repetir jugadors
    hi = {n["anyCard"]["slug"] for n in bench(arena["slug"], {"min": 8000})}
    cache, pool, gkq = {}, [], None
    for i, n in enumerate(bench(arena["slug"]) + bench(arena["slug"], None, ["Goalkeeper"])):
        c, p = n["anyCard"], n["anyPlayer"]
        # Arena Limited: també hi van cartes de raresa superior (Rare, Super Rare, Unique; el David, 4/11: Rrahmani)
        if c["rarityTyped"].lower() not in ("limited", "rare", "super_rare", "unique") or c["slug"] in busy or (p["slug"] in busy_p and p["slug"] != gk["slug"]):
            continue
        g = (n.get("eligiblePlayerGameScores") or [{}])[0] or {}
        game = g.get("anyGame") or {}
        if not game.get("id"):
            continue
        D = dt.datetime.fromisoformat(game["date"].replace("Z", "+00:00"))
        club = (p.get("activeClub") or {}).get("name") or ""
        pos = n.get("position") or p.get("position")
        q = {"card": c["slug"], "xp": c["xp"] or 0, "name": p["displayName"], "player": p["slug"], "club": club, "pos": pos, "poss": [pos],
             "avg": n.get("avg10") or 0, "idx": i, "grade": (g.get("projection") or {}).get("grade"), "proj": (g.get("projection") or {}).get("score"), "game": game["id"], "date": D,
             "girona": "girona" in club.lower(), "gazza": False}
        q["imp"] = GRADE.get(q["grade"], -1)
        if p["slug"] == gk["slug"]:
            if not gkq or q["xp"] > gkq["xp"]:
                gkq = q
            continue
        if pos == "Goalkeeper" or D < now + dt.timedelta(minutes=10 if not final else 3) or q["girona"] or "gazzaniga" in p["slug"]:
            continue  # el porter és el vigilat; partits ja començats (o a punt) fora; Girona i Gazzaniga: Arena manual del David
        xi = lineup_status(game, cache)
        if xi is not None:
            if not starts(xi, p["slug"], p["displayName"]):
                continue
            q["tier"] = 0  # titular confirmat
            q["src"] = xi[0]
        elif c["slug"] in hi and not (final and D - now < dt.timedelta(minutes=50)):
            q["tier"] = 1  # encara sense onze: 80–90%
        else:
            continue
        pool.append(q)
    if not gkq:
        return None
    # un jugador per carta (la de més XP); ordre: confirmats, després 80–90%; dins de cada grup, impacte i llista
    best = {}
    for q in pool:
        if q["player"] not in best or q["xp"] > best[q["player"]]["xp"]:
            best[q["player"]] = q
    pool = list(best.values())
    pick = build([gkq] + pool, ARENA, ARENA_CAP, "avg", hard=True)
    if not pick or pick[0] is not gkq:
        return None
    return arena, pick, captain(pick), (arena["format"].get("entryItem") or {}).get("myEntryItemId")


def arena_text(pick, cap):
    return ", ".join(f"{SHORT[sl]} {q['name']}{' ©' if q is cap else ''} ({q['grade'] or '?'}{', titular' if q.get('tier') == 0 else ', 80–90%' if q.get('tier') == 1 else ''})"
                     for sl, q in zip(ARENA, pick)) + f" · {sum(q['avg'] for q in pick):.0f}/260"


def yes_after(ts):
    """Hi ha un «sí» al xat de Telegram després de `ts` (segons)? Mira els missatges encara no llegits pel planificador
    i els «sí» que el planificador ja ha desat (state/sorare_yes.json)."""
    import os
    import re
    import requests
    from bot.web import load_json
    if any(t >= ts for t in load_json("sorare_yes.json", [])):
        return True
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    try:
        r = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", params={"timeout": 0}, timeout=20).json()
    except Exception:
        return False
    for u in r.get("result", []):
        m = u.get("message") or {}
        if str((m.get("chat") or {}).get("id")) == str(chat) and m.get("date", 0) >= ts and re.fullmatch(YES, (m.get("text") or "").strip().lower()):
            return True
    return False


def gk_arena_final(key):
    """5 min abans del primer partit de l'Arena proposada: si el David ha dit «sí», es refà amb les dades del moment
    (titulars confirmats) i s'envia."""
    from bot.web import load_json, save_json
    st = load_json("sorare_gkarena.json", {})
    pend = [(k, v) for k, v in st.items() if k == key and v.get("status") == "proposed"]
    for k, v in pend:
        if not yes_after(v["at"]):
            v["status"] = "no"
            telegram(f"🏟️ Arena amb {v['gk']['name']}: no l'he feta (no he rebut el «sí»).")
            continue
        res = gk_arena(v["gk"], final=True)
        if not res:
            v["status"] = "error"
            telegram(f"⚠️ Arena amb {v['gk']['name']}: ara no surt cap alineació vàlida; no l'he feta.")
            continue
        lb, pick, cap, entry = res
        try:
            save_lineup(lb, pick, cap, entry=entry)
            v["status"] = "done"
            telegram(f"✅ Arena feta (100 d'essència): {arena_text(pick, cap)}")
        except Exception as e:
            v["status"] = "error"
            telegram(f"❌ Arena amb {v['gk']['name']}: {str(e)[:300]}")
    save_json("sorare_gkarena.json", st)


def wait_yes(since, until):
    """Espera fins a `until` (UTC) una resposta «sí»/«no» al xat de Telegram (missatges posteriors a `since`)."""
    import datetime as dt
    import os
    import re
    import time
    import requests
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    base = f"https://api.telegram.org/bot{tok}"
    offset = 0
    while dt.datetime.now(dt.timezone.utc) < until:
        r = requests.get(f"{base}/getUpdates", params={"offset": offset, "timeout": 25}, timeout=40).json()
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            m = u.get("message") or {}
            if str((m.get("chat") or {}).get("id")) != str(chat) or m.get("date", 0) < since:
                continue
            t = (m.get("text") or "").strip().lower()
            if re.fullmatch(r"s[ií]\W*|yes\W*|ok\W*|endavant\W*|fes-les\W*", t):
                return True
            if re.fullmatch(r"no\W*", t):
                return False
    return None


# ── Arenes fins a l'últim moment (decisió del David, 6/11) ─────────────────────────────────────────────────────────
# L'Arena es tanca quan comença el primer partit dels seus 5 jugadors. El bot proposa les Arenes possibles a la
# revisió final i abans de cada hora de partits (també amb la Gameweek ja començada), el David diu «sí» (= fins a N
# Arenes) i el bot no les envia fins 6 min abans del primer partit de cada una, refetes amb les dades del moment
# (titulars confirmats; si el del primer partit no és titular, es canvia). Les ja enviades no es toquen.
ARSTATE = "sorare_arenas.json"
ARENA_RAR = ("limited", "rare", "super_rare", "unique")  # a l'Arena Limited hi van també rareses superiors (el David, 4/11)


def _when(q):
    import datetime as dt
    return dt.datetime.fromisoformat(q["date"].replace("Z", "+00:00"))


def arena_props(fx, final=False):
    """Arenes Beginner possibles ara amb les cartes lliures. Retorna (arena, props [(pick, cap)], dates dels candidats)."""
    import datetime as dt
    arena = next((l for l in fx["so5Leaderboards"] if l["isArena"] and "beginner" in l["slug"]), None)
    if not arena:
        return None, [], []
    now = dt.datetime.now(dt.timezone.utc)
    lus = fx.get("mySo5Lineups") or []
    busy = {a["anyCard"]["slug"] for l in lus for a in l["so5Appearances"]}
    busy_p = {a["anyPlayer"].get("slug") for l in lus for a in l["so5Appearances"]}
    cache, pool = {}, []
    for q in cards(arena, floor=2000, rarities=ARENA_RAR):
        base_p = q["player"].split("#")[0]
        if q["card"] in busy or (base_p in busy_p and not q["gazza"]) or not q.get("date") or (q["girona"] and not q["gazza"]):
            continue
        D = _when(q)
        if D < now + dt.timedelta(minutes=3 if final else 10):
            continue  # partit començat o a punt
        g = dict(q.get("gobj") or {}, id=q["game"])
        xi = lineup_status(g, cache)
        if xi is not None:
            if not starts(xi, base_p, q["name"]):
                continue  # onze oficial publicat i no hi és
            q = dict(q, tier=0, src=xi[0])  # titular confirmat
        elif q["tier"] == 0 and not (final and D - now < dt.timedelta(minutes=50)):
            q = dict(q, tier=1)  # ≥80%, encara sense onze
        else:
            continue  # <80% sense onze, o partit que ja hauria de tenir onze i no se sap
        pool.append(q)
    dates = sorted({_when(q) for q in pool})
    props = []
    while True:
        pick = build(pool, ARENA, ARENA_CAP, "avg", hard=True)
        if not pick:
            break
        props.append((pick, captain(pick)))
        got = {q["player"] for q in pick}
        pool = [q for q in pool if q["player"] not in got]
    return arena, props, dates


def _arena_line(i, pick, cap):
    from zoneinfo import ZoneInfo
    first = min(_when(q) for q in pick)
    return (f"   Arena {i} (l'envio a les {(first - __import__('datetime').timedelta(minutes=6)).astimezone(ZoneInfo('Europe/Madrid')):%a %H:%M}): "
            + arena_text(pick, cap))


def late_arenas(kind="prop", at=None):
    """kind="prop": proposa (o actualitza) les Arenes possibles i en demana el «sí».
    kind="go": 6 min abans del partit `at` (ISO), envia les Arenes aprovades que tenen el primer partit aleshores,
    refetes amb les dades del moment."""
    import datetime as dt
    import time
    from bot.web import load_json, save_json
    st = load_json(ARSTATE, {})
    slug = st.get("fx") or load_json("sorare_fixture.json", {}).get("slug")
    if not slug:
        return
    fx = gql(FIXTURE_SLUG, {"s": slug}, token=token())["so5"]["so5Fixture"]
    if st.get("fx") != fx["slug"]:
        st = {"fx": fx["slug"], "approved": 0, "made": 0}
    if st.get("sent_at") and yes_after(st["sent_at"]):  # «sí» a l'última proposta: fins a N Arenes
        st["approved"] = max(st.get("approved", 0), st.get("made", 0) + st.get("sent_n", 0))
        st["sent_at"] = None
    arena, props, dates = arena_props(fx, final=kind == "go")
    st["kicks"] = [d.isoformat() for d in dates]
    left = st.get("approved", 0) - st.get("made", 0)
    ess = (arena or {}).get("format", {}).get("entryItem") or {}
    if kind == "go":
        T = dt.datetime.fromisoformat(at) if at else dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=6)
        due = [(p, c) for p, c in props if min(_when(q) for q in p) <= T + dt.timedelta(minutes=2)]
        if left > 0 and due:
            ok, msgs = 0, []
            for pick, cap in due[:left]:
                try:
                    save_lineup(arena, pick, cap, entry=ess.get("myEntryItemId"))
                    ok += 1
                    msgs.append("✅ " + arena_text(pick, cap))
                except Exception as e:
                    msgs.append(f"❗ {str(e)[:200]}")
            st["made"] = st.get("made", 0) + ok
            telegram(f"🏟️ Arenes enviades ara ({ok} × {ess.get('quantity') or 100} d'essència; en queden {st['approved'] - st['made']} d'aprovades):\n" + "\n".join(msgs))
        save_json(ARSTATE, st)
        print(f"::notice title=sorare arenes::go {at}: {len(due)} a punt, aprovades pendents {left}")
        return
    # proposta: només si n'hi ha més de les ja aprovades i ha canviat respecte de l'última
    sig = " | ".join(",".join(q["player"] for q in p) for p, _ in props)
    if props and len(props) > left and sig != st.get("sig"):
        lines = [_arena_line(i, p, c) for i, (p, c) in enumerate(props, 1)]
        telegram(f"🏟️ Puc fer {len(props)} Arenes Beginner ({len(props) * (ess.get('quantity') or 100)} d'essència)"
                 + (f"; ja me n'has aprovat {left}" if left > 0 else "") + ":\n" + "\n".join(lines)
                 + "\nLes faig? Respon «sí». Les envio 6 min abans del primer partit de cada una, refetes amb els titulars del moment."
                 + " Abans de cada partit les torno a mirar.")
        st.update(sent_at=int(time.time()) - 5, sent_n=len(props) - max(left, 0), sig=sig)
    elif not props:
        st["sig"] = ""
    save_json(ARSTATE, st)
    print(f"::notice title=sorare arenes::prop: {len(props)} possibles, aprovades pendents {left} · " + " | ".join(arena_text(p, c) for p, c in props)[:2000])


def run(mode="dry"):
    """mode: dry (només proposta), fill (omple/actualitza les alineacions Classic), final (com fill + Arena amb el «sí»)."""
    import datetime as dt
    import time
    from bot.web import save_json
    dry = mode == "dry"
    LOG.clear()
    fx = gql(FIXTURE, token=token())["so5"]["so5Fixture"]
    save_json("sorare_fixture.json", {"slug": fx["slug"], "gw": fx["gameWeek"], "cutoff": fx["cutOffDate"]})
    lbs = [l for l in fx["so5Leaderboards"] if not l["isArena"] and l["format"]["title"] == "Classic"]
    essence = {}
    try:
        for c in gql(ESSENCE, token=token())["currentUser"]["cardShardsChests"]:
            essence[c["rarity"].lower()] = essence.get(c["rarity"].lower(), 0) + c["cardShardsCount"]
    except Exception as e:
        print("::warning title=sorare essència::" + str(e)[:300])
    rare_ess = essence.get("rare")
    girona_rare_allstar = rare_ess is not None and rare_ess < 100
    from zoneinfo import ZoneInfo
    cut = dt.datetime.fromisoformat(fx["cutOffDate"].replace("Z", "+00:00"))
    rep = [f"Sorare · GW{fx['gameWeek']} · tanca {cut.astimezone(ZoneInfo('Europe/Madrid')):%a %d %H:%M}"
           + {"dry": " (PROVA: no envio res)", "fill": "", "final": " · revisió final"}[mode],
           f"Essència: Rare {rare_ess if rare_ess is not None else '?'} · Limited {essence.get('limited', '?')}"
           + (" → Girona permès a All Star Rare" if girona_rare_allstar else "")]
    used = {"rare": set(), "limited": set()}  # sense repetir jugadors dins de cada raresa (un jugador pot anar a Rare i a Limited)
    plan = []
    for rarity, total in (("rare", 1), ("limited", None)):  # Rare: 1 alineació a la primera competició possible; Limited: fins a 4 per competició
        made = 0
        for name, key in COMPS:
            if total and made >= total:
                break
            lb = next((l for l in lbs if key in l["slug"] and (l["mainRarityType"] or "").lower() == rarity), None)
            if not lb:
                continue
            allstar = name == "All Star"
            pool = [q for q in cards(lb) if q["player"] not in used[rarity]]
            if allstar and not (rarity == "rare" and girona_rare_allstar):  # Girona fora (els Gazzaniga Limited que sobren sí)
                pool = [q for q in pool if not q["girona"] or (rarity == "limited" and q["gazza"])]
            if rarity == "rare" and not allstar:  # el Rare de Gazzaniga es reserva si no va a All Star Rare
                pool = [q for q in pool if not q["gazza"]]
            if name == "U23" and not any(q["pos"] == "Goalkeeper" for q in pool):
                rep.append(f"{lb['displayName']}: no hi ha porter U23 titular (≥80%) → no la faig")
                continue
            n = 0
            while n < (total or 4) - (made if total else 0):
                pick = build(pool, CLASSIC)
                if not pick:
                    break
                same = [i for i, (l_, _, _) in enumerate(plan) if l_ is lb]
                sw = swap_rivals(pick, [plan[i][1] for i in same]) if same else None
                if sw:  # repartir els jugadors entre aquesta alineació i una d'anterior perquè cap tingui rivals
                    pick, oi, newo = sw
                    lvl = ("all", "back", "none")[clean_level(pick)]
                    pick = [dict({k: v for k, v in q.items() if k != "rivals"}, **({"rivals": lvl} if lvl != "all" else {})) for q in pick]
                    newo = [{k: v for k, v in q.items() if k != "rivals"} for q in newo]
                    pi = same[oi]
                    ocap = captain(newo)
                    plan[pi] = (lb, newo, ocap)
                    rep.append(f"🔄 {lb['displayName']}: he intercanviat jugadors amb una alineació anterior per evitar rivals → {describe(newo, ocap)} · {preview(lb, newo, ocap)}")
                cap = captain(pick)
                n += 1; made += 1
                used[rarity] |= {q["player"] for q in pick}
                pool = [q for q in pool if q["player"] not in used[rarity]]
                plan.append((lb, pick, cap))
                rep.append(f"🃏 {lb['displayName']} #{n}: {describe(pick, cap)} · {preview(lb, pick, cap)}")
            if n == 0 and rarity == "rare" and allstar:
                # All Star Rare: si no hi ha prou jugadors amb ≥80%, s'agafen els de més % (70%, 60%…), per impacte (el David, 3/11)
                for floor in range(7000, 1999, -1000):
                    pool2 = [q for q in cards(lb, floor) if q["player"] not in used[rarity]]
                    if not girona_rare_allstar:
                        pool2 = [q for q in pool2 if not q["girona"]]
                    pick = build(pool2, CLASSIC)
                    if pick:
                        cap = captain(pick)
                        n += 1; made += 1
                        used[rarity] |= {q["player"] for q in pick}
                        plan.append((lb, pick, cap))
                        low = [q["name"] + f" ({80 - 10 * q['tier']}%)" for q in pick if q.get("tier")]
                        rep.append(f"🃏 {lb['displayName']} #1 (amb jugadors de menys del 80%: {', '.join(low)}): {describe(pick, cap)} · {preview(lb, pick, cap)}")
                        break
            if n == 0:
                rep.append(f"{lb['displayName']}: no hi ha prou jugadors amb ≥80% per a una alineació")
            elif n < 4 and not total:
                rep.append(f"{lb['displayName']}: {n} alineacions (no queden jugadors per a més)")
    graded = any(q["grade"] for _, pick, _ in plan for q in pick)
    if not plan:
        rep.append("No surt cap alineació.")
    elif not graded:
        rep.append("⏸️ L'impacte previst encara no s'ha publicat: no envio res.")
    elif not dry:
        sync(fx, plan, rep)
    # Arena Beginner (5 jugadors, límit 260): proposta amb els sobrants Limited (≥80%; sense Girona, excepte els Gazzaniga que sobren dels 2 reservats)
    arena = next((l for l in fx["so5Leaderboards"] if l["isArena"] and "beginner" in l["slug"]), None)
    if arena:
        busy = {a["anyCard"]["slug"] for l in fx.get("mySo5Lineups") or [] if l["so5Leaderboard"]["isArena"] for a in l["so5Appearances"]}
        pool = [q for q in cards(arena) if q["player"] not in used["limited"] and (not q["girona"] or q["gazza"]) and q["card"] not in busy]
        props = []
        while True:
            pick = build(pool, ARENA, ARENA_CAP, "avg", hard=True)
            if not pick:
                break
            props.append((pick, captain(pick)))
            got = {q["player"] for q in pick}
            pool = [q for q in pool if q["player"] not in got]
        lines = [f"   Arena {i}: " + ", ".join(f"{SHORT[sl]} {q['name']}{' ©' if q is cap else ''} ({q['grade'] or '?'})" for sl, q in zip(ARENA, pick))
                 + f" · {sum(q['avg'] for q in pick):.0f}/260 · {preview(arena, pick, cap)}" for i, (pick, cap) in enumerate(props, 1)]
        if mode == "final":
            print("::notice title=sorare::" + " ¶ ".join(rep + LOG)[:60000])
            telegram("\n".join(rep))
            gk_watch(fx, [])
            from bot.web import load_json as _lj, save_json as _sj
            if _lj(ARSTATE, {}).get("fx") != fx["slug"]:
                _sj(ARSTATE, {"fx": fx["slug"], "approved": 0, "made": 0})
            late_arenas("prop")  # (6/11) ja no s'espera el «sí» aquí: s'envien 6 min abans del primer partit de cada Arena
            return plan
        if props:
            rep.append(f"🏟️ Arenes possibles: {len(props)} ({len(props) * 100} d'essència). Te les proposaré a la revisió final i abans de cada partit, i només les faré si dius «sí»:")
            rep += lines
        else:
            rep.append("🏟️ Arena: no queden prou jugadors amb ≥80% per a cap Arena")
    gk_watch(fx, rep)
    print("::notice title=sorare::" + " ¶ ".join(rep + LOG)[:60000])
    telegram("\n".join(rep))
    return plan


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="dry", choices=["dry", "fill", "final"])
    run(ap.parse_args().mode)
