"""Sorare · missions diàries: Decisive Picker (per l'API oficial).

Criteri (com SorareBuddy, decisió del David 29/10): «opcions» = probabilitat de titular × forma.
- Titular: 100% si l'onze oficial ja és publicat i hi surt (Sorare o FotMob), 0% si no hi surt; si encara no hi ha
  onze, el % de SorareInside (filtre del banc de Sorare): només entren els del 80–90%. Els de menys del 80% es
  miren igualment i només entren si surten titulars a l'onze oficial (revisió 15 min abans de cada partit).
- Diverses missions (caps de setmana, Champions): essència → pistes de crafteig → crèdits de mercat → experiència;
  una carta triada en una missió no es fa servir en una altra. Les places que queden buides s'omplen igualment amb
  les cartes que sobren (primer a les d'acció decisiva, després per prioritat).
- Forma: partits amb acció decisiva positiva dels últims 20 (desempat: últims 10 i últims 5); a les missions
  d'estadística («3+ tackles», «2+ shots on target»), partits en què va arribar a la xifra.
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
  l10: averageScore(type: LAST_TEN_PLAYED_SO5_AVERAGE_SCORE) nextDailyFixtureProjectedScore nextClassicFixtureProjectedScore
  anyFutureGameStats(first: 1) { ... on PlayerGameStatsBasketball { anyGame { id date } projectedMinsPlayed projectedPoints projectedRebounds
    projectedAssists projectedSteals projectedBlocks projectedThreePointsMade } } } } }"""
NBA_STAT = {"rebounds": "projectedRebounds", "points": "projectedPoints", "assists": "projectedAssists", "steals": "projectedSteals",
            "blocks": "projectedBlocks", "three": "projectedThreePointsMade", "threes": "projectedThreePointsMade",
            "three_points_made": "projectedThreePointsMade"}


def nba_score(slug, task, game_id=None):
    """NBA: amb les previsions de RotoWire que dona Sorare (no hi ha % de titularitat).
    Retorna (juga, valor, detall): juga = 1 si té minuts previstos i no està lesionat.
    - Daily Picker (mode SCORE: superar la L10 en 7 i fer ≥ 20): valor = punts previstos − max(20, L10 + 7)
      (com més marge, més opcions; si és negatiu, poques).
    - Missions d'estadística («N+ rebounds»…, «X Stars or less»): valor = previsió de l'estadística − N;
      els jugadors amb més estrelles de les permeses, fora."""
    import re
    try:
        p = gql(NBA_FORM, {"s": slug}, token=token())["anyPlayer"]
    except Exception as e:
        print(f"::warning title=nba {slug}::{str(e)[:300]}")
        return 0, -99, "sense dades"
    fut = next((g for g in p.get("anyFutureGameStats") or [] if g), {}) or {}
    mins = fut.get("projectedMinsPlayed") or 0
    # sense % de titularitat: si RotoWire li preveu punts, juga (com més punts, més minuts)
    plays = 0 if p.get("activeInjuries") or not ((fut.get("projectedPoints") or 0) > 0 or mins > 0) else 1
    desc = task.get("description") or ""
    m = re.search(r"([\d.]+)\s*Stars? or less", desc, re.I)
    if m and (p.get("gameplayTierStars") or 0) > float(m.group(1)):
        return 0, -99, f"{p.get('gameplayTierStars')}★ (massa estrelles)"
    if task.get("mode") == "SCORE":
        l10 = p.get("l10") or 0
        proj = p.get("nextDailyFixtureProjectedScore") or p.get("nextClassicFixtureProjectedScore") or 0
        thr = max(20, l10 + 7)
        return plays, proj - thr, f"previsió {fut.get('projectedPoints') or 0:.0f} punts reals · {proj:.0f} punts Sorare, cal {thr:.0f} (L10 {l10:.0f})"
    if re.search(r"double[- ]double", desc, re.I) or "double_double" in [a.lower() for a in task.get("decisiveActions") or []]:
        v = sorted([(fut.get("projectedPoints") or 0), (fut.get("projectedRebounds") or 0), (fut.get("projectedAssists") or 0)], reverse=True)
        return plays, v[1] - 10, f"previsió {fut.get('projectedPoints') or 0:.0f} pts / {fut.get('projectedRebounds') or 0:.0f} reb / {fut.get('projectedAssists') or 0:.0f} ast (doble-doble: 2 de 3 ≥10)"
    acts = [a.lower() for a in task.get("decisiveActions") or []]
    key = next((NBA_STAT[a] for a in acts if a in NBA_STAT), None)
    n = re.search(r"(\d+)\+", desc)
    if not key or not n:
        return plays, -99, "missió no reconeguda"
    v = fut.get(key) or 0
    return plays, v - int(n.group(1)), f"previsió {v:.1f} ({key[9:].lower()}), cal {n.group(1)}"


def priority(t):
    """Essència (0) → pistes de crafteig (1) → crèdits de mercat (2) → experiència (3) → altres (4) (decisió del David, 30/10).
    Si la missió no diu les recompenses, es miren a la descripció («Essence», «Clue», «Market credit», «XP»)."""
    d = (t.get("description") or "").lower()
    best = 0 if "essence" in d else 1 if "clue" in d else 2 if "credit" in d else 3 if " xp" in d else 4
    for r in t.get("rewardConfigs") or []:
        cur = (r.get("currency") or "").upper()
        tn = r["__typename"]
        if tn == "CardShardRewardConfig" or "SHARD" in cur or "ESSENCE" in cur:
            best = min(best, 0)
        elif "CLUE" in cur:
            best = min(best, 1)
        elif "CREDIT" in cur or "Credit" in tn or "MARKET" in cur:
            best = min(best, 2)
        elif tn == "ExperienceRewardConfig" or cur.endswith("_XP") or cur == "XP":
            best = min(best, 3)
    return best


TASK = """query($id: ID!) { currentUser { task(id: $id) { ... on DecisivePlayerPickerTask { id title description maxAppearancesCount mode rarity expired aasmState decisiveActions decisiveStats { name shortName }
  taskAppearances { id index status anyCard { slug } anyPlayer { displayName slug } game { id date } }
  pickableGames(first: 60) { nodes { game { id date homeTeam { name } awayTeam { name } } cards { slug xp rarityTyped anyPlayer { displayName slug } } } } } } } }"""
FORM = """query($s: String!) { anyPlayer(slug: $s) { displayName
  ... on Player { allPlayerGameScores(first: 20) { nodes { anyGame { date } ... on PlayerGameScore { positiveDecisiveStats { stat statValue } }
    anyPlayerGameStats { ... on PlayerGameStats { gameStarted minsPlayed %s } } } } } } }"""


def camel(stat):
    a = stat.split("_")
    return a[0] + "".join(x.title() for x in a[1:])


UPSERT = """mutation($input: upsertTaskAppearancesInput!) { upsertTaskAppearances(input: $input) { errors { message } } }"""


def form(slug, stat=None, need=1):
    """(l5, l10, l20, titular10): partits «encertats» als últims 5/10/20 i titularitats dels últims 10.
    Encertat = acció decisiva positiva (Decisive Picker) o, a les missions d'estadística («3+ tackles», «2+ shots on
    target»), haver arribat a la xifra (stat = nom de l'estadística de Sorare, p. ex. won_tackle)."""
    fld = camel(stat) if stat else ""
    try:
        nodes = gql(FORM % fld, {"s": slug}, token=token())["anyPlayer"]["allPlayerGameScores"]["nodes"]
    except Exception as e:
        print(f"::warning title=forma {slug}::{str(e)[:300]}")
        return 0, 0, 0, 0
    now = dt.datetime.now(dt.timezone.utc)
    past = [n for n in nodes if n.get("anyGame") and dt.datetime.fromisoformat(n["anyGame"]["date"].replace("Z", "+00:00")) < now]
    if stat:
        dec = [1 if ((n.get("anyPlayerGameStats") or {}).get(fld) or 0) >= need else 0 for n in past]
    else:
        dec = [1 if any((x.get("statValue") or 0) > 0 for x in n.get("positiveDecisiveStats") or []) else 0 for n in past]
    st = [1 if ((n.get("anyPlayerGameStats") or {}).get("gameStarted") or 0) > 0 else 0 for n in past[:10]]
    return sum(dec[:5]), sum(dec[:10]), sum(dec[:20]), (sum(st) / len(st) if st else 0)


PLAY = """query($r: Rarity, $sp: Sport!) { currentUser { taskGroup(slug: "play") { myTasks(rarity: $r, sport: $sp) { __typename
  ... on DecisivePlayerPickerTask { id title description rarity expired
    rewardConfigs { __typename ... on InGameCurrencyRewardConfig { currency amount } ... on CardShardRewardConfig { quantity rarity } } } } } } }"""


def list_tasks(rep):
    """Totes les missions de la pestanya «Play» (featuredTasks només en dona algunes: p. ex. no hi surt «Shot» Limited)."""
    out, seen = [], set()
    for sport in ("FOOTBALL", "NBA"):  # MLB: fora de temporada (es pot afegir quan torni)
        for rarity in ("limited", "rare", "super_rare", "unique"):
            found = []
            for q, path in ((PLAY, ("taskGroup", "myTasks")), (TASKS, ("featuredTasks",))):
                try:
                    d = gql(q, {"r": rarity, "sp": sport}, token=token())["currentUser"]
                    for k in path:
                        d = d[k]
                    found += [t for t in d if t.get("__typename") == "DecisivePlayerPickerTask" and t.get("id") and not t.get("expired")]
                except Exception as e:
                    rep.append(f"⚠️ {sport} {rarity}: {str(e)[:150]}")
            for t in found:
                if t["id"] not in seen:
                    seen.add(t["id"])
                    out.append((priority(t), rarity, dict(t, sport=sport)))
    out.sort(key=lambda x: x[0])  # essència → pistes → crèdits de mercat → experiència
    return out


def run(dry=False):
    from bot.sorarelineup import lineup_status, starts
    import re as _re
    import zoneinfo
    MAD = zoneinfo.ZoneInfo("Europe/Madrid")
    now = dt.datetime.now(dt.timezone.utc)
    rep, games_seen = [], []
    all_tasks = list_tasks(rep)
    odds = si_odds() if all_tasks else {}
    used_cards = set()
    PRI = {0: "essència", 1: "pistes de crafteig", 2: "crèdits de mercat", 3: "experiència", 4: "altres"}
    plans = []
    for pri, rarity, t in all_tasks:
        tid = t["id"].split(":")[-1]
        task = gql(TASK, {"id": tid}, token=token())["currentUser"]["task"]
        nba = t["sport"] == "NBA"
        if task.get("expired"):
            continue  # caducada (la d'ahir)
        if task.get("mode") != "DECISIVE" and not nba:
            rep.append(f"ℹ️ {task['title']} ({rarity}): {task['description']} — mode {task.get('mode')}, no la toco")
            continue
        stat = (task.get("decisiveActions") or [None])[0] if not nba else None
        mneed = _re.search(r"(\d+)\+", task.get("description") or "")
        need = int(mneed.group(1)) if (stat and mneed) else 1
        n_max = task["maxAppearancesCount"]
        apps = {a["index"]: a for a in task["taskAppearances"]}

        def started(a):
            return dt.datetime.fromisoformat(a["game"]["date"].replace("Z", "+00:00")) <= now + dt.timedelta(minutes=2) or a["status"] != "READY"
        locked = {i: a for i, a in apps.items() if started(a)}
        used_cards |= {a["anyCard"]["slug"] for a in locked.values()}
        cache, cand = {}, {}
        for gnode in task["pickableGames"]["nodes"]:
            g = gnode["game"]
            D = dt.datetime.fromisoformat(g["date"].replace("Z", "+00:00"))
            if D <= now + dt.timedelta(minutes=2):
                continue
            games_seen.append(g["date"])
            for c in gnode["cards"]:
                p = c["anyPlayer"]
                if any(a["anyPlayer"]["slug"] == p["slug"] for a in locked.values()):
                    continue
                if p["slug"] not in cand or (c.get("xp") or 0) > cand[p["slug"]]["xp"]:
                    cand[p["slug"]] = {"slug": p["slug"], "name": p["displayName"], "card": c["slug"], "xp": c.get("xp") or 0, "game": g, "date": D}
        for q in (cand.values() if nba else []):
            plays, margin, info = nba_score(q["slug"], task)
            q.update(l5=0, l10=0, l20=0, tit=float(plays), confirmed=False, chance=margin if plays else -99, info=info, margin=margin)
        for q in (cand.values() if not nba else []):
            l5, l10, l20, st10 = form(q["slug"], stat, need)
            xi = lineup_status(q["game"], cache)
            # titular: amb l'onze oficial, 100% o 0%; si no, el % de SorareInside (només compten els del 80–90%)
            tit = (1.0 if starts(xi, q["slug"], q["name"]) else 0.0) if xi else odds.get(q["slug"], 0.0)
            q.update(l5=l5, l10=l10, l20=l20, tit=tit, confirmed=bool(xi), chance=tit * l20 / 20)
        ranked = sorted(cand.values(), key=lambda q: (-q["chance"], -q["l10"], -q["l5"], q["date"]))
        free = [i for i in range(n_max) if i not in locked]
        want = []
        for q in ranked:  # 1a passada: només els que juguen (80–90% o titulars a l'onze oficial)
            if q["tit"] > 0 and q["card"] not in used_cards and len(want) < len(free):
                want.append(q)
                used_cards.add(q["card"])
        plans.append(dict(task=task, tid=tid, pri=pri, rarity=rarity, nba=nba, stat=stat, need=need, n_max=n_max, apps=apps, locked=locked,
                          free=free, ranked=ranked, want=want, extra=set()))
    # 2a passada (decisió del David, 30/10): les places que queden buides s'omplen igualment amb les cartes que sobren
    # («per si de cas», p. ex. suplents que poden entrar a la segona part). Primer a les missions d'acció decisiva
    # (un suplent té més opcions de fer una acció decisiva que no pas xuts o tackles), després per prioritat.
    for pl in sorted(plans, key=lambda pl: (0 if (not pl["stat"] and not pl["nba"]) else 1, pl["pri"])):
        rest = sorted([q for q in pl["ranked"] if q["card"] not in used_cards and q not in pl["want"]],
                      key=lambda q: (-(q.get("margin", 0) if pl["nba"] else 0), -q["l20"], -q["l10"], -q["l5"], q["date"]))
        for q in rest:
            if len(pl["want"]) >= len(pl["free"]):
                break
            pl["want"].append(q)
            pl["extra"].add(q["slug"])
            used_cards.add(q["card"])
    for pl in sorted(plans, key=lambda pl: pl["pri"]):
        task, tid, nba, stat, need, apps, locked, free, want = (pl[k] for k in ("task", "tid", "nba", "stat", "need", "apps", "locked", "free", "want"))
        cur = {i: apps[i] for i in free if i in apps}
        cur_slugs = {a["anyPlayer"]["slug"] for a in cur.values()}
        want_slugs = {q["slug"] for q in want}
        line = [f"🎯 {'🏀 ' if nba else ''}{task['title']} ({pl['rarity']}, {pl['n_max']} places, recompensa: {PRI[pl['pri']]}): {task['description']}"]
        for i, a in sorted(locked.items()):
            line.append(f"   🔒 {a['anyPlayer']['displayName']} ({a['status'].lower()})")
        if cur:
            line.append("   ara triats: " + ", ".join(a["anyPlayer"]["displayName"] for a in cur.values()))
        shown = [q for q in pl["ranked"] if q["slug"] in want_slugs] + [q for q in pl["ranked"] if q["slug"] not in want_slugs][:3]
        for q in shown:
            M = q["date"].astimezone(MAD)
            mark = ("🔸" if q["slug"] in pl["extra"] else "✅") if q["slug"] in want_slugs else "·"
            if nba:
                line.append(f"   {mark} {q['name']} · {M:%H:%M} · {q['info']}{'' if q['tit'] else ' · no juga'}")
                continue
            line.append(f"   {mark} {q['name']} · {M:%H:%M} · titular {q['tit'] * 100:.0f}%{' (onze oficial)' if q['confirmed'] else ' (SorareInside)'}"
                        f" · {(str(need) + '+ ' + stat) if stat else 'decisiu'} {q['l5']}/5 {q['l10']}/10 {q['l20']}/20 · opcions {q['chance'] * 100:.0f}%")
        if pl["extra"]:
            line.append("   🔸 = carta que sobrava, posada per si de cas")
        if want_slugs != cur_slugs and want:
            keep = {i: a for i, a in cur.items() if a["anyPlayer"]["slug"] in want_slugs}
            new = [q for q in want if q["slug"] not in {a["anyPlayer"]["slug"] for a in keep.values()}]
            slots = [i for i in free if i not in keep]
            payload = [{"index": i, "cardSlug": q["card"], "gameId": q["game"]["id"].split(":")[-1]} for i, q in zip(slots, new)]
            payload += [{"index": i, "cardSlug": a["anyCard"]["slug"], "gameId": a["game"]["id"].split(":")[-1]} for i, a in keep.items()]  # id sense «Game:»
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
            line.append("   sense canvis" if want or cur else "   cap carta per posar")
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
