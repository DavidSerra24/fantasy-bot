"""Sorare · Set (mode gratuït, cartes comunes) per l'API: taulers «Career» (personal) i «Squad» (d'equip).

NBA (decisió del David, 30/10): per punts previstos de Sorare (RotoWire) per al partit del pas, només els que juguen
(projecció > 0 i sense lesió). 5 jugadors (posició de cada casella segons la regla «Appearances»), límit d'estrelles
(regla «AverageScores», p. ex. 16 estrelles), sense repetir jugadors entre alineacions del mateix tauler, fins a les
alineacions que permeti el pas (Career: remainingLineupsCount; Squad: fins que Sorare no en deixi més, màx. 4).
Quan: el planificador mira cada dia a les 9:35 quin és el primer partit amb jugadors (scan) i fa les alineacions
12 min abans d'aquell partit (per tenir les lesions i previsions del dia).
Només es fan alineacions noves: les que ja hi ha (fetes pel David o pel bot) no es toquen.
Seguretat: només upsertStepLineup (alineacions del Set). Res de comprar sobres ni reclamar res.
Ús: python -m bot.sorareset [--dry] [--sport NBA]
"""
import argparse
import datetime as dt
import itertools
import json

from bot.notify import telegram
from bot.sorare import gql, token
from bot.web import load_json, save_json

STEP = """query($sp: Sport!, $m: BoardMode!) { currentUser { setBoard(mode: $m, sport: $sp) { id title
  myCurrentStep { __typename id level state target
    ... on CareerStep { title maxLineupsCount remainingLineupsCount pendingLineupsCount }
    ... on SquadStep { totalLineups totalScore minimumLineupsToStartStep }
    myLineups { ... on TaskLineup { id aasmState taskAppearances { ... on TaskAppearanceInterface { anyPlayer { slug displayName } anyCard { slug } } } } }
    displayedTypedRules { key ... on So5AverageScoresRule { averageType max }
      ... on So5AppearancesRule { appearances { name positions sub } } } } } } }"""
BENCH = """query($st: String!, $after: String, $f: BenchFilterInput!) { currentUser { step(id: $st) { myFilteredBench(filters: $f, first: 100, after: $after) {
  pageInfo { hasNextPage endCursor }
  nodes { ... on ComposeTeamBenchCard { position positions bonus anyCard { slug xp }
    anyPlayer { displayName slug ... on NBAPlayer { gameplayTierStars activeInjuries { id } } }
    eligiblePlayerGameScores(stepId: $st) { anyGame { id date } projectedScore } } } } } } }"""
CLAIM = """mutation($input: claimStepInput!) { claimStep(input: $input) { errors { message } } }"""
UPSERT = """mutation($input: upsertStepLineupInput!) { upsertStepLineup(input: $input) { errors { message } lineup { id } } }"""


def bench(step_id, used=False):
    out, after = [], None
    for _ in range(10):
        d = gql(BENCH, {"st": step_id, "after": after, "f": {"includeUsed": True} if used else {}}, token=token())["currentUser"]["step"]["myFilteredBench"]
        out += [n for n in d["nodes"] if n]
        if not d["pageInfo"]["hasNextPage"]:
            break
        after = d["pageInfo"]["endCursor"]
    return out


def best(cands, slots, cap):
    """Millor alineació (suma de punts previstos) amb una carta per casella (posició permesa) i estrelles ≤ cap."""
    top = sorted(cands, key=lambda c: -c["proj"])[:18]
    bestv = None
    for combo in itertools.combinations(top, len(slots)):
        if cap is not None and sum(c["stars"] for c in combo) > cap:
            continue
        if len({c["player"] for c in combo}) < len(combo):
            continue
        # assignació a les caselles (5! = 120 com a màxim)
        for perm in itertools.permutations(combo):
            if all(not s["positions"] or set(c["positions"]) & set(s["positions"]) for c, s in zip(perm, slots)):
                v = sum(c["proj"] for c in combo)
                if bestv is None or v > bestv[0]:
                    bestv = (v, perm)
                break
    return bestv


def run(dry=False, sports=("NBA",), scan=False):
    """scan=True: no fa res, només desa l'hora del primer partit amb jugadors (state/sorare_set.json) per al planificador."""
    now = dt.datetime.now(dt.timezone.utc)
    rep, firsts, games_used = [], [], []
    for sp in sports:
        for mode in ("CAREER", "SQUAD"):
            label = f"{'🏀' if sp == 'NBA' else '⚽'} Set {sp} · {'personal' if mode == 'CAREER' else 'equip'}"
            try:
                b = gql(STEP, {"sp": sp, "m": mode}, token=token())["currentUser"]["setBoard"]
            except Exception as e:
                rep.append(f"⚠️ {label}: {str(e)[:200]}")
                continue
            st = (b or {}).get("myCurrentStep")
            if not st:
                rep.append(f"ℹ️ {label}: cap pas actiu")
                continue
            if st["state"] == "CLAIMABLE" and sp == "NBA" and not dry:
                # pas superat: es reclama la recompensa i es passa al pas següent (decisió del David, 31/10: a la nit ell dorm)
                try:
                    d = gql(CLAIM, {"input": {"stepId": st["id"]}}, token=token())["claimStep"]
                    if d.get("errors"):
                        raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
                    rep.append(f"🎁 {label}: nivell {st['level'] + 1} superat, recompensa reclamada")
                    b = gql(STEP, {"sp": sp, "m": mode}, token=token())["currentUser"]["setBoard"]
                    st = (b or {}).get("myCurrentStep") or st
                except Exception as e:
                    rep.append(f"⚠️ {label}: no he pogut reclamar la recompensa ({str(e)[:150]})")
            head = f"{label} ({b.get('title')}, nivell {st['level'] + 1}, objectiu {st['target']}, estat {st['state']})"
            if st["state"] not in ("PLAYABLE", "LINEUP_SET"):
                rep.append(f"ℹ️ {head}: no es pot jugar ara")
                continue
            existing = [l for l in st.get("myLineups") or [] if l]
            if mode == "CAREER":
                room = st.get("remainingLineupsCount") or 0
            else:
                room = max(0, 1 - len(existing))  # tauler d'equip: 1 alineació per membre («cantidad máxima de alineaciones»)
            if room <= 0:
                rep.append(f"✅ {head}: ja té {len(existing)} alineacions")
                continue
            rules = {r["key"]: r for r in st.get("displayedTypedRules") or []}
            slots = [a for a in (rules.get("Appearances") or {}).get("appearances") or [] if not a.get("sub")]
            cap = (rules.get("AverageScores") or {}).get("max") if (rules.get("AverageScores") or {}).get("averageType") == "STARS" else None
            used = {a["anyPlayer"]["slug"] for l in existing for a in l.get("taskAppearances") or [] if a and a.get("anyPlayer")}
            cands = []
            for n in bench(st["id"]):
                p = n["anyPlayer"]
                if p["slug"] in used or p.get("activeInjuries"):
                    continue
                games = [g for g in n.get("eligiblePlayerGameScores") or [] if g and g.get("anyGame")
                         and dt.datetime.fromisoformat(g["anyGame"]["date"].replace("Z", "+00:00")) > now + dt.timedelta(minutes=5)]
                for g in games:  # també els de previsió 0: només omplen les alineacions que sobren (decisió del David, 30/10)
                    if True:
                        cands.append({"card": n["anyCard"]["slug"], "xp": n["anyCard"].get("xp") or 0, "bonus": n.get("bonus") or 0, "player": p["slug"], "name": p["displayName"],
                                      "stars": p.get("gameplayTierStars") or 0, "positions": n.get("positions") or [n.get("position")],
                                      "proj": g.get("projectedScore") or 0, "game": g["anyGame"]})
            # només els partits del mateix dia (decisió del David, 30/10): la jornada del primer partit (12 h des de l'inici)
            if cands:
                start = min(dt.datetime.fromisoformat(c["game"]["date"].replace("Z", "+00:00")) for c in cands)
                cands = [c for c in cands if dt.datetime.fromisoformat(c["game"]["date"].replace("Z", "+00:00")) < start + dt.timedelta(hours=12)]
                one = {}
                for c in cands:  # un partit per carta (el de més punts previstos dins del dia)
                    if c["card"] not in one or c["proj"] > one[c["card"]]["proj"]:
                        one[c["card"]] = c
                cands = list(one.values())
            if cands:
                firsts.append(min(c["game"]["date"] for c in cands))
            if scan:
                continue
            # una carta per jugador: la de més bonificació (%), després la de més XP (decisió del David, 30/10)
            byp = {}
            for c in cands:
                if c["player"] not in byp or (c["bonus"], c["xp"]) > (byp[c["player"]]["bonus"], byp[c["player"]]["xp"]):
                    byp[c["player"]] = c
            pool = list(byp.values())
            nproj = sum(1 for c in pool if c["proj"] > 0)
            lines = [head + f" · {len(pool)} jugadors amb partit ({nproj} amb previsió > 0; 🔸 = previsió 0, només per omplir)" + (f" · límit {cap} estrelles" if cap else "")]
            made = 0
            for k in range(room):
                r = best(pool, slots, cap)
                if not r:
                    lines.append("   no queden jugadors per a una altra alineació")
                    break
                v, perm = r
                apps = [{"index": i, "cardSlug": c["card"], "gameId": c["game"]["id"].split(":")[-1]} for i, c in enumerate(perm)]
                txt = ", ".join(f"{'🔸' if not c['proj'] else ''}{c['name']} ({c['proj']:.0f}, {c['stars']}★, {c['game']['date'][5:16].replace('T', ' ')}Z)" for c in perm)
                if dry:
                    lines.append(f"   (prova) alineació {k + 1}: {txt} · {v:.0f} previstos · {sum(c['stars'] for c in perm)}★")
                else:
                    try:
                        d = gql(UPSERT, {"input": {"stepId": st["id"], "appearances": apps}}, token=token())["upsertStepLineup"]
                        if d.get("errors"):
                            raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
                        lines.append(f"   ✅ alineació {k + 1}: {txt} · {v:.0f} previstos · {sum(c['stars'] for c in perm)}★")
                        made += 1
                    except Exception as e:
                        lines.append(f"   ❌ alineació {k + 1}: {str(e)[:200]}")
                        break
                games_used.extend(c["game"]["date"] for c in perm)
                chosen = {c["player"] for c in perm}
                pool = [c for c in pool if c["player"] not in chosen]
            rep.append("\n".join(lines))
    stt = load_json("sorare_set.json", {})
    if games_used:
        stt["games"] = sorted(set(games_used) | {g for g in stt.get("games", []) if g > now.isoformat()[:19]})
    if firsts:
        stt["first"] = min(firsts)
    stt["at"] = now.isoformat()
    save_json("sorare_set.json", stt)
    if scan:  # també les hores dels partits de les alineacions ja fetes (per a les revisions del planificador)
        for sp in sports:
            for mode in ("CAREER", "SQUAD"):
                try:
                    st = gql(LINEUPS, {"sp": sp, "m": mode}, token=token())["currentUser"]["setBoard"]["myCurrentStep"]
                except Exception:
                    continue
                for l in (st or {}).get("myLineups") or []:
                    for a in (l or {}).get("taskAppearances") or []:
                        if a and a.get("game") and a["game"]["date"] > now.isoformat()[:19]:
                            games_used.append(a["game"]["date"])
        stt["games"] = sorted(set(games_used) | {g for g in stt.get("games", []) if g > now.isoformat()[:19]})
        save_json("sorare_set.json", stt)
        # revisions dins de la mateixa execució (accions dinàmiques), sense esperar la propera execució del planificador
        dyn, done = load_json("dyn_actions.json", []), set(load_json("done.json", []))
        for gd in stt["games"]:
            G = dt.datetime.fromisoformat(gd.replace("Z", "+00:00"))
            for mins in (20, 8):
                k = f"soraresetrev:{gd}:{mins}"
                at = G - dt.timedelta(minutes=mins)
                if k not in done and now < G - dt.timedelta(minutes=3) and at < now + dt.timedelta(minutes=95) and not any(d["key"] == k for d in dyn):
                    dyn.append({"key": k, "at": max(at, now).isoformat(), "do": "soraresetrev", "comp": f"{gd}:{mins}", "deadline": (G - dt.timedelta(minutes=3)).isoformat()})
        fs = stt.get("first")  # pas nou després de reclamar (o alineacions pendents): alineacions 12 min abans del primer partit
        if fs and firsts:
            F = dt.datetime.fromisoformat(fs.replace("Z", "+00:00"))
            k = f"soraresetgo:{fs}"
            at = F - dt.timedelta(minutes=12)
            if k not in done and now < F - dt.timedelta(minutes=2) and at < now + dt.timedelta(minutes=95) and not any(d["key"] == k for d in dyn):
                dyn.append({"key": k, "at": max(at, now).isoformat(), "do": "soraresetgo", "comp": fs, "deadline": (F - dt.timedelta(minutes=2)).isoformat()})
        save_json("dyn_actions.json", dyn)
        print(f"::notice title=set::primer partit amb jugadors del Set: {stt.get('first')} · partits de les alineacions: {', '.join(stt['games'])}")
        if any("🎁" in r for r in rep):
            telegram("Sorare · Set\n" + "\n".join(r for r in rep if "🎁" in r or "⚠️" in r)
                     + (f"\nFaré les alineacions del nivell següent 12 min abans del primer partit ({fs[11:16]} UTC)." if fs and firsts else ""))
        return
    msg = "Sorare · Set" + (" (prova)" if dry else "") + "\n" + "\n".join(rep)
    for k, r in enumerate(rep):
        print(f"::notice title=set {k + 1}::" + r.replace("\n", " ¶ ")[:3900])
    if dry or any("✅ alineació" in r or "❌" in r for r in rep):
        telegram(msg)



LINEUPS = """query($sp: Sport!, $m: BoardMode!) { currentUser { setBoard(mode: $m, sport: $sp) { title
  myCurrentStep { id state
    myLineups { ... on TaskLineup { id aasmState taskAppearances { ... on TaskAppearanceInterface { index anyCard { slug } anyPlayer { slug displayName } game { id date } } } } }
    displayedTypedRules { key ... on So5AverageScoresRule { averageType max } ... on So5AppearancesRule { appearances { name positions sub } } } } } } }"""


def best_fill(pool, slots, cap, fixed):
    """Millor manera d'omplir les caselles lliures (les de `fixed` ja estan bloquejades: partit començat)."""
    free_idx = [i for i in range(len(slots)) if i not in fixed]
    if not free_idx:
        return 0, {}
    fstars = sum(c["stars"] for c in fixed.values())
    fplayers = {c["player"] for c in fixed.values()}
    top = sorted([c for c in pool if c["player"] not in fplayers], key=lambda c: -c["proj"])[:18]
    bestv = None
    for combo in itertools.combinations(top, len(free_idx)):
        if cap is not None and fstars + sum(c["stars"] for c in combo) > cap:
            continue
        if len({c["player"] for c in combo}) < len(combo):
            continue
        v = sum(c["proj"] for c in combo)
        if bestv is not None and v <= bestv[0]:
            continue
        for perm in itertools.permutations(combo):
            if all(not slots[i]["positions"] or set(c["positions"]) & set(slots[i]["positions"]) for c, i in zip(perm, free_idx)):
                bestv = (v, dict(zip(free_idx, perm)))
                break
    return bestv


def review(sports=("NBA",), dry=False):
    """Abans de cada partit es tornen a calcular les alineacions **de zero, com si fos la primera vegada** (decisió del
    David, 31/10): els jugadors amb el partit ja començat es queden; la resta de caselles s'omplen amb el millor que hi
    ha ara (punts previstos actuals, lesions, límit d'estrelles, sense repetir jugadors). Si el resultat millora una
    alineació, es canvia."""
    now = dt.datetime.now(dt.timezone.utc)
    rep = []
    D = lambda x: dt.datetime.fromisoformat(x.replace("Z", "+00:00"))
    for sp in sports:
        for mode in ("CAREER", "SQUAD"):
            label = f"{'🏀' if sp == 'NBA' else '⚽'} Set {sp} · {'personal' if mode == 'CAREER' else 'equip'}"
            try:
                st = gql(LINEUPS, {"sp": sp, "m": mode}, token=token())["currentUser"]["setBoard"]["myCurrentStep"]
            except Exception as e:
                rep.append(f"⚠️ {label}: {str(e)[:200]}")
                continue
            lineups = [l for l in (st or {}).get("myLineups") or [] if l and l.get("taskAppearances")]
            if not lineups:
                continue
            rules = {r["key"]: r for r in st.get("displayedTypedRules") or []}
            slots = [a for a in (rules.get("Appearances") or {}).get("appearances") or [] if not a.get("sub")]
            cap = (rules.get("AverageScores") or {}).get("max") if (rules.get("AverageScores") or {}).get("averageType") == "STARS" else None
            info = {}
            for n in bench(st["id"], used=True):
                p = n["anyPlayer"]
                info[n["anyCard"]["slug"]] = {"card": n["anyCard"]["slug"], "player": p["slug"], "name": p["displayName"], "stars": p.get("gameplayTierStars") or 0,
                                              "inj": bool(p.get("activeInjuries")), "positions": n.get("positions") or [n.get("position")],
                                              "bonus": n.get("bonus") or 0, "xp": n["anyCard"].get("xp") or 0,
                                              "games": [g for g in n.get("eligiblePlayerGameScores") or [] if g and g.get("anyGame")]}
            dates = [D(a["game"]["date"]) for l in lineups for a in l["taskAppearances"] if a and a.get("game")]
            if not dates:
                continue
            start = min(dates)
            # caselles bloquejades (partit començat) i punts previstos actuals de cada alineació
            fixed_all, cur_val = {}, {}
            for l in lineups:
                fx, val = {}, 0
                for a in l["taskAppearances"]:
                    if not a:
                        continue
                    c = info.get(a["anyCard"]["slug"]) or {"card": a["anyCard"]["slug"], "player": a["anyPlayer"]["slug"], "name": a["anyPlayer"]["displayName"], "stars": 0, "positions": [], "games": []}
                    g = next((g for g in c["games"] if a.get("game") and g["anyGame"]["id"] == a["game"]["id"]), {})
                    proj = 0 if c.get("inj") else (g.get("projectedScore") or 0)
                    val += proj
                    if not a.get("game") or D(a["game"]["date"]) <= now + dt.timedelta(minutes=3):
                        fx[a["index"]] = dict(c, proj=proj, game=a["game"])
                fixed_all[l["id"]], cur_val[l["id"]] = fx, val
            locked_players = {c["player"] for fx in fixed_all.values() for c in fx.values()}
            # tots els jugadors disponibles ara (partit del dia no començat), una carta per jugador (més bonificació, després XP)
            pool = {}
            for c in info.values():
                if c["player"] in locked_players:
                    continue
                for g in c["games"]:
                    d = D(g["anyGame"]["date"])
                    if now + dt.timedelta(minutes=3) < d < start + dt.timedelta(hours=12):
                        cand = dict(c, proj=0 if c["inj"] else (g.get("projectedScore") or 0), game=g["anyGame"])
                        cur = pool.get(c["player"])
                        if not cur or (cand["bonus"], cand["xp"], cand["proj"]) > (cur["bonus"], cur["xp"], cur["proj"]):
                            pool[c["player"]] = cand
            pool = list(pool.values())
            lines, plan = [], []
            for l in sorted(lineups, key=lambda l: -cur_val[l["id"]]):  # primer la millor (la que ha d'arribar a l'objectiu)
                fx = fixed_all[l["id"]]
                r = best_fill(pool, slots, cap, fx)
                if not r:
                    plan.append((l, None, cur_val[l["id"]]))
                    continue
                v, fill = r
                pool = [c for c in pool if c["player"] not in {c_["player"] for c_ in fill.values()}]
                plan.append((l, fill, v + sum(c["proj"] for c in fx.values())))
            old_total = sum(cur_val[l["id"]] for l in lineups)
            new_total = sum(nv if f is not None else cur_val[l["id"]] for l, f, nv in plan)
            if new_total <= old_total + 2:
                continue  # el que hi ha ja és (pràcticament) el millor
            todo = []
            for l, fill, nv in plan:
                if fill is None:
                    continue
                old = {a["index"]: a for a in l["taskAppearances"] if a}
                if all(old.get(i_) and old[i_]["anyCard"]["slug"] == c["card"] for i_, c in fill.items()):
                    continue
                fx = fixed_all[l["id"]]
                apps = [{"index": i_, "cardSlug": c["card"], "gameId": c["game"]["id"].split(":")[-1]} for i_, c in sorted({**fx, **fill}.items())]
                outs = [old[i_]["anyPlayer"]["displayName"] for i_, c in fill.items() if old.get(i_) and old[i_]["anyCard"]["slug"] != c["card"]]
                ins = [f"{c['name']} ({c['proj']:.0f})" for i_, c in fill.items() if not old.get(i_) or old[i_]["anyCard"]["slug"] != c["card"]]
                todo.append({"l": l, "apps": apps, "txt": f"{cur_val[l['id']]:.0f} → {nv:.0f} previstos · surten {', '.join(outs)} · entren {', '.join(ins)}"})
            if dry:
                lines += ["   (prova) " + t["txt"] for t in todo]
            else:
                for _ in range(len(todo) + 1):  # una carta no pot ser a dues alineacions: es repeteix fins que tot entra
                    for t in [t for t in todo if not t.get("done")]:
                        try:
                            d = gql(UPSERT, {"input": {"stepId": st["id"], "lineupId": t["l"]["id"], "appearances": t["apps"]}}, token=token())["upsertStepLineup"]
                            if d.get("errors"):
                                raise RuntimeError("; ".join(e["message"] for e in d["errors"]))
                            t["done"] = True
                        except Exception as e:
                            t["err"] = str(e)[:200]
                    if all(t.get("done") for t in todo):
                        break
                lines += [("   🔁 " if t.get("done") else "   ❌ ") + t["txt"] + ("" if t.get("done") else f": {t.get('err')}") for t in todo]
            if lines:
                lines.insert(0, f"   total {old_total:.0f} → {new_total:.0f} previstos")
            if lines:
                rep.append(label + "\n" + "\n".join(lines))
    for k, r in enumerate(rep):
        print(f"::notice title=set revisió {k + 1}::" + r.replace("\n", " ¶ ")[:3900])
    if rep:
        telegram("Sorare · Set · revisió" + (" (prova)" if dry else "") + "\n" + "\n".join(rep))
    else:
        print("::notice title=set revisió::cap alineació millorable; sense canvis")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--sport", nargs="*", default=["NBA"])
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--review", action="store_true")
    a = ap.parse_args()
    if a.review:
        review(tuple(a.sport), a.dry)
    else:
        run(a.dry, tuple(a.sport), a.scan)
