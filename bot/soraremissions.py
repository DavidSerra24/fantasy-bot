"""Sorare · missions diàries: Decisive Picker (per l'API oficial).

Criteri (com SorareBuddy, decisió del David 29/10): «opcions» = probabilitat de titular × forma.
- Titular: 100% si l'onze oficial ja és publicat i hi surt (Sorare o FotMob), 0% si no hi surt; si encara no hi ha
  onze, el % de SorareInside (filtre del banc de Sorare): només entren els del 80–90%. Els de menys del 80% es
  miren igualment i només entren si surten titulars a l'onze oficial (revisió 15 min abans de cada partit).
- Diverses missions (caps de setmana, Champions): primer les que donen essència, després pistes de crafteig, després
  experiència; una carta triada en una missió no es fa servir en una altra.
- Forma: partits amb acció decisiva positiva dels últims 20 (desempat: últims 10 i últims 5).
Es trien els N millors (N = places de la missió, normalment 3), un per jugador. Els picks d'un partit ja començat
no es toquen. Es revisa al matí i abans de cada partit (amb els onzes oficials) i es canvia un pick si n'hi ha un de
millor (p. ex. el triat no és titular).
Seguretat: només llegeix i posa els picks de la missió (upsertTaskAppearances). Res de comprar, vendre ni diners.
Ús: python -m bot.soraremissions [--dry]
"""
import argparse
import datetime as dt
import json

from bot.notify import telegram
from bot.sorare import gql, token
from bot.web import load_json, save_json

TASKS = """query($r: Rarity!, $sp: Sport!) { currentUser { featuredTasks(rarity: $r, sport: $sp) { __typename id title description
  rewardConfigs { __typename ... on InGameCurrencyRewardConfig { currency amount } ... on CardShardRewardConfig { quantity rarity } } } } }"""
FIX = """query($t: So5State) { so5 { so5Fixture(sport: FOOTBALL, type: $t, eventType: CLASSIC) { slug so5Leaderboards { slug isArena mainRarityType } } } }"""
ODDS = """query($s: String!, $r: RangeInput, $after: String, $pos: [Position!]) { so5 { so5Leaderboard(slug: $s) {
  myBench(first: 50, after: $after, includeUsed: true, starterOddsBasisPointsRange: $r, positions: $pos) { pageInfo { hasNextPage endCursor }
    nodes { ... on ComposeTeamBenchCard { anyPlayer { slug } } } } } } }"""


def si_odds():
    """% de titularitat de SorareInside (el que fa servir Sorare) per jugador: 0.9 (≥90%) o 0.8 (80–89%).
    L'API no el dona directament; es treu amb el filtre del banc d'All Star de la jornada en joc i de la propera."""
    out = {}
    for st in ("LIVE", "UPCOMING"):
        try:
            fx = gql(FIX, {"t": st}, token=token())["so5"]["so5Fixture"]
        except Exception:
            continue
        for lb in (fx or {}).get("so5Leaderboards") or []:
            if lb["isArena"] or "all_star" not in lb["slug"] or lb["mainRarityType"] not in ("limited", "rare"):
                continue
            for rng, v in (({"min": 8000, "max": 8999}, 0.8), ({"min": 9000}, 0.9)):
                for pos in (None, ["Goalkeeper"]):
                    after = None
                    for _ in range(15):
                        d = gql(ODDS, {"s": lb["slug"], "r": rng, "after": after, "pos": pos}, token=token())["so5"]["so5Leaderboard"]["myBench"]
                        for n in d["nodes"]:
                            if n:
                                out[n["anyPlayer"]["slug"]] = max(out.get(n["anyPlayer"]["slug"], 0), v)
                        if not d["pageInfo"]["hasNextPage"]:
                            break
                        after = d["pageInfo"]["endCursor"]
    return out


NBA_FORM = """query($s: String!) { anyPlayer(slug: $s) { displayName ... on NBAPlayer { gameplayTierStars activeInjuries { id }
  l10: averageScore(type: LAST_TEN_PLAYED_SO5_AVERAGE_SCORE) nextDailyFixtureProjectedScore
  allAverageStats(limit: LAST_10) { stat value lastValues }
  allPlayerGameScores(first: 20) { nodes { score } } } } }"""
NBA_STAT = {"rebounds": "REBOUNDS", "points": "POINTS", "assists": "ASSISTS", "steals": "STEALS", "blocks": "BLOCKS",
            "three": "THREE_POINTS_MADE", "threes": "THREE_POINTS_MADE", "three_points_made": "THREE_POINTS_MADE"}


def nba_score(slug, task):
    """NBA (com SorareBuddy, adaptat): (disponibilitat, encerts, detall).
    - Disponibilitat: lesionat → 0; si no, la part dels últims 10 partits que ha jugat (s'exigeix ≥ 80%, com al futbol).
    - Daily Picker (mode SCORE: superar la seva L10 en 7 punts i fer ≥ 20): part dels últims 20 partits amb
      puntuació ≥ max(20, L10 + 7); desempat, la projecció de Sorare menys la L10.
    - Missions d'estadística (rebots, punts, assistències…, «N+»; «X Stars or less»): part dels últims 10 partits amb
      l'estadística ≥ N; els jugadors amb més estrelles de les permeses, fora."""
    import re
    try:
        p = gql(NBA_FORM, {"s": slug}, token=token())["anyPlayer"]
    except Exception as e:
        print(f"::warning title=nba {slug}::{str(e)[:300]}")
        return 0, 0, "sense dades"
    stats = {a["stat"]: a for a in p.get("allAverageStats") or []}
    mins = (stats.get("MINS_PLAYED") or {}).get("lastValues") or []
    avail = 0 if p.get("activeInjuries") else (sum(1 for m in mins if (m or 0) > 0) / len(mins) if mins else 0)
    desc = task.get("description") or ""
    m = re.search(r"([\d.]+)\s*Stars? or less", desc, re.I)
    if m and (p.get("gameplayTierStars") or 0) > float(m.group(1)):
        return 0, 0, f"{p.get('gameplayTierStars')}★ (massa estrelles)"
    if task.get("mode") == "SCORE":
        l10 = p.get("l10") or 0
        thr = max(20, l10 + 7)
        sc = [n["score"] for n in (p.get("allPlayerGameScores") or {}).get("nodes") or [] if n.get("score") is not None]
        rate = sum(1 for x in sc if x >= thr) / len(sc) if sc else 0
        gain = (p.get("nextDailyFixtureProjectedScore") or 0) - l10
        return avail, rate + gain / 1000, f"L10 {l10:.0f}, cal {thr:.0f}: {sum(1 for x in sc if x >= thr)}/{len(sc)}"
    acts = [a.lower() for a in task.get("decisiveActions") or []]
    key = next((NBA_STAT[a] for a in acts if a in NBA_STAT), None)
    n = re.search(r"(\d+)\+", desc)
    if not key or not n:
        return avail, 0, "missió no reconeguda"
    vals = (stats.get(key) or {}).get("lastValues") or []
    hit = sum(1 for v in vals if (v or 0) >= int(n.group(1)))
    return avail, (hit / len(vals) if vals else 0), f"{key.lower()} ≥{n.group(1)}: {hit}/{len(vals)}"


def priority(t):
    """Essència (0) → pistes de crafteig (1) → experiència (2) → altres (3). Si la missió no diu les recompenses,
    es miren a la descripció («Essence», «Clue», «XP»)."""
    d = (t.get("description") or "").lower()
    best = 0 if "essence" in d else 1 if "clue" in d else 2 if " xp" in d else 3
    for r in t.get("rewardConfigs") or []:
        cur = r.get("currency") or ""
        if r["__typename"] == "CardShardRewardConfig" or "SHARD" in cur or "ESSENCE" in cur:
            best = min(best, 0)
        elif "CRAFT_CLUE" in cur:
            best = min(best, 1)
        elif r["__typename"] == "ExperienceRewardConfig" or cur.endswith("_XP"):
            best = min(best, 2)
    return best
TASK = """query($id: ID!) { currentUser { task(id: $id) { ... on DecisivePlayerPickerTask { id title description maxAppearancesCount mode rarity expired aasmState decisiveActions
  taskAppearances { id index status anyCard { slug } anyPlayer { displayName slug } game { id date } }
  pickableGames(first: 60) { nodes { game { id date homeTeam { name } awayTeam { name } } cards { slug xp rarityTyped anyPlayer { displayName slug } } } } } } } }"""
FORM = """query($s: String!) { anyPlayer(slug: $s) { displayName
  ... on Player { allPlayerGameScores(first: 20) { nodes { anyGame { date } ... on PlayerGameScore { positiveDecisiveStats { stat statValue } }
    anyPlayerGameStats { ... on PlayerGameStats { gameStarted minsPlayed } } } } } } }"""
UPSERT = """mutation($input: upsertTaskAppearancesInput!) { upsertTaskAppearances(input: $input) { errors { message } } }"""


def form(slug):
    """(l5, l10, l20, titular10): partits amb acció decisiva positiva als últims 5/10/20 i titularitats dels últims 10."""
    try:
        nodes = gql(FORM, {"s": slug}, token=token())["anyPlayer"]["allPlayerGameScores"]["nodes"]
    except Exception as e:
        print(f"::warning title=forma {slug}::{str(e)[:300]}")
        return 0, 0, 0, 0
    now = dt.datetime.now(dt.timezone.utc)
    past = [n for n in nodes if n.get("anyGame") and dt.datetime.fromisoformat(n["anyGame"]["date"].replace("Z", "+00:00")) < now]
    dec = [1 if any((x.get("statValue") or 0) > 0 for x in n.get("positiveDecisiveStats") or []) else 0 for n in past]
    st = [1 if ((n.get("anyPlayerGameStats") or {}).get("gameStarted") or 0) > 0 else 0 for n in past[:10]]
    return sum(dec[:5]), sum(dec[:10]), sum(dec[:20]), (sum(st) / len(st) if st else 0)


def run(dry=False):
    from bot.sorarelineup import lineup_status, starts
    now = dt.datetime.now(dt.timezone.utc)
    rep, games_seen = [], []
    all_tasks = []
    for sport in ("FOOTBALL", "NBA"):  # MLB: fora de temporada (es pot afegir quan torni)
        for rarity in ("limited", "rare", "super_rare", "unique"):
            try:
                for t in gql(TASKS, {"r": rarity, "sp": sport}, token=token())["currentUser"]["featuredTasks"]:
                    if t["__typename"] == "DecisivePlayerPickerTask":
                        all_tasks.append((priority(t), rarity, dict(t, sport=sport)))
            except Exception as e:
                rep.append(f"⚠️ {sport} {rarity}: {str(e)[:150]}")
    all_tasks.sort(key=lambda x: x[0])  # primer les d'essència, després pistes, després experiència
    odds = si_odds() if all_tasks else {}
    used_cards = set()
    PRI = {0: "essència", 1: "pistes de crafteig", 2: "experiència", 3: "altres"}
    if True:
        for pri, rarity, t in all_tasks:
            tid = t["id"].split(":")[-1]
            task = gql(TASK, {"id": tid}, token=token())["currentUser"]["task"]
            nba = t["sport"] == "NBA"
            if task.get("expired") or (task.get("mode") != "DECISIVE" and not nba):
                rep.append(f"ℹ️ {task['title']} ({rarity}): {task['description']} — no és d'acció decisiva, no la toco")
                continue
            n_max = task["maxAppearancesCount"]
            apps = {a["index"]: a for a in task["taskAppearances"]}
            def started(a):
                return dt.datetime.fromisoformat(a["game"]["date"].replace("Z", "+00:00")) <= now + dt.timedelta(minutes=2) or a["status"] != "READY"
            locked = {i: a for i, a in apps.items() if started(a)}
            used_cards |= {a["anyCard"]["slug"] for a in apps.values()}
            # candidats: un per jugador (la carta de més XP), partits que encara no han començat
            cache, cand = {}, {}
            for gnode in task["pickableGames"]["nodes"]:
                g = gnode["game"]
                D = dt.datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
                if D <= now + dt.timedelta(minutes=2):
                    continue
                games_seen.append(g["date"])
                for c in gnode["cards"]:
                    p = c["anyPlayer"]
                    if c["slug"] in used_cards and not any(a["anyCard"]["slug"] == c["slug"] for a in apps.values()):
                        continue  # carta ja triada en una missió de més prioritat
                    if any(a["anyPlayer"]["slug"] == p["slug"] for a in locked.values()):
                        continue
                    if p["slug"] not in cand or (c.get("xp") or 0) > cand[p["slug"]]["xp"]:
                        cand[p["slug"]] = {"slug": p["slug"], "name": p["displayName"], "card": c["slug"], "xp": c.get("xp") or 0, "game": g, "date": D}
            for q in (cand.values() if nba else []):
                avail, rate, info = nba_score(q["slug"], task)
                q.update(l5=0, l10=0, l20=0, tit=avail if avail >= 0.8 else 0.0, confirmed=False, chance=(avail if avail >= 0.8 else 0) * rate, info=info)
            for q in (cand.values() if not nba else []):
                l5, l10, l20, st10 = form(q["slug"])
                xi = lineup_status(q["game"], cache)
                # titular: amb l'onze oficial, 100% o 0%; si no, el % de SorareInside (només compten els del 80–90%)
                tit = (1.0 if starts(xi, q["slug"], q["name"]) else 0.0) if xi else odds.get(q["slug"], 0.0)
                q.update(l5=l5, l10=l10, l20=l20, tit=tit, confirmed=bool(xi), chance=tit * l20 / 20)
            ranked = sorted(cand.values(), key=lambda q: (-q["chance"], -q["l10"], -q["l5"], q["date"]))
            free = [i for i in range(n_max) if i not in locked]
            want = [q for q in ranked if q["tit"] > 0][:len(free)]
            cur = {i: apps[i] for i in free if i in apps}
            cur_slugs = {a["anyPlayer"]["slug"] for a in cur.values()}
            want_slugs = {q["slug"] for q in want}
            used_cards |= {q["card"] for q in want}
            line = [f"🎯 {'🏀 ' if nba else ''}{task['title']} ({rarity}, {n_max} places, recompensa: {PRI[pri]}): {task['description']}"]
            for i, a in sorted(locked.items()):
                line.append(f"   🔒 {a['anyPlayer']['displayName']} ({a['status'].lower()})")
            if cur:
                line.append("   ara triats: " + ", ".join(a["anyPlayer"]["displayName"] for a in cur.values()))
            for q in ranked[:6]:
                M = q["date"].astimezone(__import__("zoneinfo").ZoneInfo("Europe/Madrid"))
                if nba:
                    line.append(f"   {'✅' if q['slug'] in want_slugs else '·'} {q['name']} · {M:%H:%M} · juga {q['tit'] * 100:.0f}% · {q['info']} · opcions {q['chance'] * 100:.0f}%")
                    continue
                line.append(f"   {'✅' if q['slug'] in want_slugs else '·'} {q['name']} · {M:%H:%M} · titular {q['tit'] * 100:.0f}%{' (onze oficial)' if q['confirmed'] else ' (SorareInside)'}"
                            f" · decisiu {q['l5']}/5 {q['l10']}/10 {q['l20']}/20 · opcions {q['chance'] * 100:.0f}%")
            if want_slugs != cur_slugs and want:
                # es mantenen a la seva casella els que ja hi són; els nous ocupen les caselles que queden
                keep = {i: a for i, a in cur.items() if a["anyPlayer"]["slug"] in want_slugs}
                new = [q for q in want if q["slug"] not in {a["anyPlayer"]["slug"] for a in keep.values()}]
                slots = [i for i in free if i not in keep]
                payload = [{"index": i, "cardSlug": q["card"], "gameId": q["game"]["id"]} for i, q in zip(slots, new)]
                payload += [{"index": i, "cardSlug": a["anyCard"]["slug"], "gameId": a["game"]["id"]} for i, a in keep.items()]
                if dry:
                    line.append("   (prova) canviaria: " + ", ".join(q["name"] for q in new) + (" en lloc de " + ", ".join(a["anyPlayer"]["displayName"] for i, a in cur.items() if i not in keep) if len(cur) > len(keep) else ""))
                else:
                    try:
                        d = gql(UPSERT, {"input": {"taskId": task["id"], "taskAppearances": payload}}, token=token())["upsertTaskAppearances"]
                        if d.get("errors"):
                            raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
                        after = gql(TASK, {"id": tid}, token=token())["currentUser"]["task"]["taskAppearances"]
                        line.append("   ✅ picks ara: " + ", ".join(a["anyPlayer"]["displayName"] for a in sorted(after, key=lambda a: a["index"])))
                    except Exception as e:
                        line.append(f"   ❌ no he pogut posar els picks: {str(e)[:200]}")
            else:
                line.append("   sense canvis")
            rep.append("\n".join(line))
    save_json("sorare_missions.json", {"games": sorted(set(games_seen)), "at": now.isoformat()})
    msg = "Sorare · missions" + (" (prova)" if dry else "") + "\n" + ("\n".join(rep) or "Cap missió de Decisive Picker avui.")
    print("::notice title=missions::" + msg.replace("\n", " ¶ ")[:20000])
    if any("✅ picks ara" in r or "❌" in r or dry for r in rep) or not rep:
        telegram(msg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    run(ap.parse_args().dry)
