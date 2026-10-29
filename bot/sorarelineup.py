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
  mySo5Lineups { id so5Leaderboard { slug displayName isArena format { title } } so5Appearances { captain anyCard { slug } anyPlayer { displayName } } } } } }"""

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


def cards(lb):
    """Cartes de la competició (de la seva raresa) amb ≥80%, una per jugador (la de més XP), en ordre de la llista."""
    # la llista sense filtre és la de la posició Extra (jugadors de camp); els porters van a part
    hi = bench(lb["slug"], {"min": 8000}) + bench(lb["slug"], {"min": 8000}, ["Goalkeeper"])
    ok = {n["anyCard"]["slug"] for n in hi}
    allc = bench(lb["slug"]) + bench(lb["slug"], None, ["Goalkeeper"])
    LOG.append(f"{lb['displayName']}: {len(allc)} cartes, {len(ok)} amb ≥80%")
    seen, copies, gazza = {}, {}, []
    for i, n in enumerate(allc):
        c, p = n["anyCard"], n["anyPlayer"]
        if c["rarityTyped"].lower() != (lb["mainRarityType"] or "").lower() or c["slug"] not in ok:
            continue
        g = (n.get("eligiblePlayerGameScores") or [{}])[0] or {}
        game = g.get("anyGame") or {}
        club = (p.get("activeClub") or {}).get("name") or ""
        teams = [(game.get("homeTeam") or {}).get("name"), (game.get("awayTeam") or {}).get("name")]
        q = {"card": c["slug"], "xp": c["xp"] or 0, "name": p["displayName"], "player": p["slug"], "club": club,
             "pos": n.get("position") or p.get("position"), "poss": [n.get("position") or p.get("position")],  # la posició de la carta "age": p.get("age"),
             "avg": n.get("avg10") or 0, "avg15": n.get("avg15") or 0, "idx": i,
             "grade": ((g.get("projection") or {}).get("grade")), "proj": (g.get("projection") or {}).get("score"),
             "game": game.get("id"), "rival": next((t for t in teams if t and t != club), None),
             "girona": "girona" in club.lower(), "gazza": "gazzaniga" in p["slug"]}
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
    return sorted(pool, key=lambda q: (q["gazza"] is not True and q["gazza"] >= 2, -q["imp"], q["idx"]))


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
                key = (nb > 0, cur["imp"] - c["imp"], c["gazza"] is not True and c["gazza"] >= 2, c["idx"])
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
    """Porters Limited amb 10–79% de ser titulars: es desen (state/sorare_gkwatch.json) perquè el planificador avisi
    1 h 15 min abans del seu partit i comprovi si són titulars (onze oficial de Sorare)."""
    from bot.web import save_json
    arena = next((l for l in fx["so5Leaderboards"] if l["isArena"] and "beginner" in l["slug"]), None)
    if not arena:
        return
    out = {}
    for lo, hi, label in ((1000, 4999, "10–49%"), (5000, 7999, "50–79%")):
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
    try:
        gm = gql(GAME, {"id": gid.split(":", 1)[-1]}, token=token())["football"]["game"]
    except Exception as e:
        gm = None
        print("::warning title=sorare porters::" + str(e)[:300])
    lines = []
    if gm:
        avail = all((gm.get(side) or {}).get("startingLineupAvailable") for side in ("homeFormation", "awayFormation"))
        if avail:
            xi = {p["slug"] for side in ("homeFormation", "awayFormation") for row in gm[side]["startingLineup"] for p in row}
            for g in gks:
                lines.append(f"{'✅' if g['slug'] in xi else '❌'} {g['name']} ({g['club']}) {'és TITULAR' if g['slug'] in xi else 'NO és titular'}")
            done[gid] = True
            save_json("sorare_gkdone.json", done)
    head = f"🧤 {g0['home']} – {g0['away']} ({hhmm})"
    if lines:
        telegram(head + " · onze oficial:\n" + "\n".join(lines))
    elif mins >= 75:
        telegram(f"{head}: porter a vigilar per a l'Arena: {who}. Quan surti l'onze oficial et dic si juga.")
    elif mins <= 12:
        telegram(f"{head}: encara no hi ha onze oficial a Sorare per a {who}. Mira-ho a X.")
    print(f"::notice title=sorare porters::{head} · {mins} min · " + ("; ".join(lines) or "sense onze oficial encara"))


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
        if props and mode == "final":
            ess = (arena["format"].get("entryItem") or {})
            rep.append(f"🏟️ Puc fer {len(props)} Arenes Beginner ({len(props) * (ess.get('quantity') or 100)} d'essència):")
            rep += lines
            rep.append("Les faig? Respon «sí» o «no» (espero fins 5 min abans del tancament).")
            telegram("\n".join(rep)); sent = len(rep)
            ans = wait_yes(int(time.time()) - 5, cut - dt.timedelta(minutes=5))
            rep2 = []
            if ans:
                ok = 0
                for i, (pick, cap) in enumerate(props, 1):
                    try:
                        save_lineup(arena, pick, cap, entry=ess.get("myEntryItemId")); ok += 1
                    except Exception as e:
                        rep2.append(f"❗ Arena {i}: {str(e)[:200]}")
                rep2.insert(0, f"{'✅' if ok == len(props) else '⚠️'} Arenes fetes: {ok} de {len(props)}")
            else:
                rep2.append("🏟️ Arenes: no les faig (" + ("m'has dit que no" if ans is False else "no he rebut el «sí» a temps") + ")")
            print("::notice title=sorare::" + " ¶ ".join(rep + rep2 + LOG)[:60000])
            telegram("\n".join(rep2))
            gk_watch(fx, [])
            return plan
        if props:
            rep.append(f"🏟️ Arenes possibles: {len(props)} ({len(props) * 100} d'essència). Te les proposaré a la revisió final i només les faré si dius «sí»:")
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
