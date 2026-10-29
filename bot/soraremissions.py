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

TASKS = """query($r: Rarity!) { currentUser { featuredTasks(rarity: $r, sport: FOOTBALL) { __typename id title description
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


def priority(t):
    """Essència (0) → pistes de crafteig (1) → experiència (2) → altres (3)."""
    best = 3
    for r in t.get("rewardConfigs") or []:
        cur = r.get("currency") or ""
        if r["__typename"] == "CardShardRewardConfig" or "SHARD" in cur or "ESSENCE" in cur:
            best = min(best, 0)
        elif "CRAFT_CLUE" in cur:
            best = min(best, 1)
        elif r["__typename"] == "ExperienceRewardConfig" or cur.endswith("_XP"):
            best = min(best, 2)
    return best
TASK = """query($id: ID!) { currentUser { task(id: $id) { ... on DecisivePlayerPickerTask { id title description maxAppearancesCount mode rarity expired aasmState
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
    for rarity in ("limited", "rare", "super_rare", "unique"):
        try:
            for t in gql(TASKS, {"r": rarity}, token=token())["currentUser"]["featuredTasks"]:
                if t["__typename"] == "DecisivePlayerPickerTask":
                    all_tasks.append((priority(t), rarity, t))
        except Exception as e:
            rep.append(f"⚠️ {rarity}: {str(e)[:150]}")
    all_tasks.sort(key=lambda x: x[0])  # primer les d'essència, després pistes, després experiència
    odds = si_odds() if all_tasks else {}
    used_cards = set()
    PRI = {0: "essència", 1: "pistes de crafteig", 2: "experiència", 3: "altres"}
    if True:
        for pri, rarity, t in all_tasks:
            tid = t["id"].split(":")[-1]
            task = gql(TASK, {"id": tid}, token=token())["currentUser"]["task"]
            if task.get("expired") or task.get("mode") != "DECISIVE":
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
            for q in cand.values():
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
            line = [f"🎯 {task['title']} ({rarity}, {n_max} places, recompensa: {PRI[pri]}): {task['description']}"]
            for i, a in sorted(locked.items()):
                line.append(f"   🔒 {a['anyPlayer']['displayName']} ({a['status'].lower()})")
            if cur:
                line.append("   ara triats: " + ", ".join(a["anyPlayer"]["displayName"] for a in cur.values()))
            for q in ranked[:6]:
                M = q["date"].astimezone(__import__("zoneinfo").ZoneInfo("Europe/Madrid"))
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
