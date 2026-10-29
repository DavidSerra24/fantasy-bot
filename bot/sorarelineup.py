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
Ús: python -m bot.sorarelineup [--dry]   (de moment sempre en prova: no envia res a Sorare)
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
  so5Leaderboards { id slug displayName mainRarityType isArena format { title } }
  mySo5Lineups { id so5Leaderboard { slug displayName } so5Appearances { captain anyCard { slug } anyPlayer { displayName } } } } } }"""

BENCH = """query($slug: String!, $r: RangeInput, $after: String, $pos: [Position!]) { so5 { so5Leaderboard(slug: $slug) {
  myBench(first: 50, after: $after, includeUsed: true, starterOddsBasisPointsRange: $r, positions: $pos) { pageInfo { hasNextPage endCursor } nodes {
    ... on ComposeTeamBenchCard { positions avg10: averageScore(type: LAST_TEN_PLAYED_SO5_AVERAGE_SCORE) avg15: averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE)
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


def cards(lb):
    """Cartes de la competició (de la seva raresa) amb ≥80%, una per jugador (la de més XP), en ordre de la llista."""
    # la llista sense filtre és la de la posició Extra (jugadors de camp); els porters van a part
    hi = bench(lb["slug"], {"min": 8000}) + bench(lb["slug"], {"min": 8000}, ["Goalkeeper"])
    ok = {n["anyCard"]["slug"] for n in hi}
    allc = bench(lb["slug"]) + bench(lb["slug"], None, ["Goalkeeper"])
    LOG.append(f"{lb['displayName']}: {len(allc)} cartes, {len(ok)} amb ≥80%")
    seen, copies = {}, {}
    for i, n in enumerate(allc):
        c, p = n["anyCard"], n["anyPlayer"]
        if c["rarityTyped"].lower() != (lb["mainRarityType"] or "").lower() or c["slug"] not in ok:
            continue
        g = (n.get("eligiblePlayerGameScores") or [{}])[0] or {}
        game = g.get("anyGame") or {}
        club = (p.get("activeClub") or {}).get("name") or ""
        teams = [(game.get("homeTeam") or {}).get("name"), (game.get("awayTeam") or {}).get("name")]
        q = {"card": c["slug"], "xp": c["xp"] or 0, "name": p["displayName"], "player": p["slug"], "club": club,
             "pos": p.get("position"), "poss": n.get("positions") or [p.get("position")], "age": p.get("age"),
             "avg": n.get("avg10") or 0, "avg15": n.get("avg15") or 0, "idx": i,
             "grade": ((g.get("projection") or {}).get("grade")), "proj": (g.get("projection") or {}).get("score"),
             "game": game.get("id"), "rival": next((t for t in teams if t and t != club), None),
             "girona": "girona" in club.lower(), "gazza": "gazzaniga" in p["slug"]}
        q["imp"] = GRADE.get(q["grade"], -1)
        copies[q["player"]] = copies.get(q["player"], 0) + 1
        if q["player"] not in seen or q["xp"] > seen[q["player"]]["xp"]:
            seen[q["player"]] = q
    for q in seen.values():
        q["copies"] = copies[q["player"]]
    return sorted(seen.values(), key=lambda q: q["idx"])


def order(pool):
    return sorted(pool, key=lambda q: (q["gazza"], -q["imp"], q["idx"]))


def faces(a, b):
    return a["game"] and a["game"] == b["game"] and a["club"] != b["club"]


def fits(q, slot):
    if slot == "Extra":
        return q["pos"] != "Goalkeeper"
    return slot == q["pos"] or slot in q["poss"]


def build(pool, slots, cap=CAP, avg="avg", hard=False):
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
    """Canvis d'un jugador, el que menys impacte perdi, fins a complir la bonificació (o el límit obligatori)."""
    for _ in range(10):
        bad = bonus_bad(pick, cap, avg, hard)
        if not bad:
            return pick
        used = {q["player"] for q in pick}
        best = None
        for k, cur in enumerate(pick):
            for c in pool:
                if c["player"] in used or not fits(c, slots[k]):
                    continue
                if any(faces(c, o) for j, o in enumerate(pick) if j != k):
                    continue
                new = pick[:k] + [c] + pick[k + 1:]
                nb = bonus_bad(new, cap, avg, hard)
                if nb >= bad:
                    continue
                key = (nb > 0, cur["imp"] - c["imp"], c["gazza"], c["idx"])
                if best is None or key < best[0]:
                    best = (key, new)
        if not best:
            break
        pick = best[1]
    return None if hard and bonus_bad(pick, cap, avg, hard) else pick


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
    return s + " · " + flags


def run(dry=True):
    fx = gql(FIXTURE, token=token())["so5"]["so5Fixture"]
    lbs = [l for l in fx["so5Leaderboards"] if not l["isArena"] and l["format"]["title"] == "Classic"]
    essence = {}
    try:
        for c in gql(ESSENCE, token=token())["currentUser"]["cardShardsChests"]:
            essence[c["rarity"].lower()] = essence.get(c["rarity"].lower(), 0) + c["cardShardsCount"]
    except Exception as e:
        print("::warning title=sorare essència::" + str(e)[:300])
    rare_ess = essence.get("rare")
    girona_rare_allstar = rare_ess is not None and rare_ess < 100
    rep = [f"Sorare · GW{fx['gameWeek']} · tanca {fx['cutOffDate'][:16].replace('T', ' ')} UTC"
           + (" (PROVA: no envio res)" if dry else ""),
           f"Essència: Rare {rare_ess if rare_ess is not None else '?'} · Limited {essence.get('limited', '?')}"
           + (" → Girona permès a All Star Rare" if girona_rare_allstar else "")]
    if fx.get("mySo5Lineups"):
        rep.append("Ja hi ha " + str(len(fx["mySo5Lineups"])) + " alineacions fetes: "
                   + "; ".join(f"{l['so5Leaderboard']['displayName']}: " + ", ".join(a["anyPlayer"]["displayName"] for a in l["so5Appearances"]) for l in fx["mySo5Lineups"]))
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
            if allstar and not (rarity == "rare" and girona_rare_allstar):
                pool = [q for q in pool if not q["girona"]]
            if rarity == "limited":  # 2 Gazzaniga Limited reservats: només entra si en té més de 2 (i sempre l'últim)
                g = [q for q in pool if q["gazza"]]
                if g and g[0].get("copies", 0) <= 2:
                    pool = [q for q in pool if not q["gazza"]]
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
                cap = captain(pick)
                n += 1; made += 1
                used[rarity] |= {q["player"] for q in pick}
                pool = [q for q in pool if q["player"] not in used[rarity]]
                plan.append((lb, pick, cap))
                rep.append(f"🃏 {lb['displayName']} #{n}: {describe(pick, cap)} · {preview(lb, pick, cap)}")
            if n == 0:
                rep.append(f"{lb['displayName']}: no hi ha prou jugadors amb ≥80% per a una alineació")
            elif n < 4 and not total:
                rep.append(f"{lb['displayName']}: {n} alineacions (no queden jugadors per a més)")
    # Arena Beginner (5 jugadors, límit 260): proposta amb els sobrants Limited (≥80%, sense Girona ni Gazzaniga: Arena manual del David)
    arena = next((l for l in fx["so5Leaderboards"] if l["isArena"] and "beginner" in l["slug"]), None)
    if arena:
        pool = [q for q in cards(arena) if q["player"] not in used["limited"] and not q["girona"] and not q["gazza"]]
        props = []
        while True:
            pick = build(pool, ARENA, ARENA_CAP, "avg15", hard=True)
            if not pick:
                break
            props.append((pick, captain(pick)))
            got = {q["player"] for q in pick}
            pool = [q for q in pool if q["player"] not in got]
        if props:
            rep.append(f"🏟️ Proposta d'Arena Beginner: puc fer {len(props)} Arenes ({len(props) * 100} d'essència); quan s'activi et preguntaré «Les faig?»:")
            for i, (pick, cap) in enumerate(props, 1):
                rep.append(f"   Arena {i}: " + ", ".join(f"{SHORT[sl]} {q['name']}{' ©' if q is cap else ''} ({q['grade'] or '?'})" for sl, q in zip(ARENA, pick))
                           + f" · {sum(q['avg15'] for q in pick):.0f}/260 · {preview(arena, pick, cap)}")
        else:
            rep.append("🏟️ Arena: no queden prou jugadors amb ≥80% per a cap Arena")
    print("::notice title=sorare::" + " ¶ ".join(rep + LOG)[:60000])
    telegram("\n".join(rep))
    return plan


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    run(dry=True)  # fins que el David validi les propostes, sempre en prova
