"""Sorare · Set (mode gratuït, cartes comunes) per l'API: taulers «Career» (personal) i «Squad» (d'equip).

NBA (decisió del David, 30/10): per punts previstos de Sorare (RotoWire) per al partit del pas, només els que juguen
(projecció > 0 i sense lesió). 5 jugadors (posició de cada casella segons la regla «Appearances»), límit d'estrelles
(regla «AverageScores», p. ex. 16 estrelles), sense repetir jugadors entre alineacions del mateix tauler, fins a les
alineacions que permeti el pas (Career: remainingLineupsCount; Squad: fins que Sorare no en deixi més, màx. 4).
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

STEP = """query($sp: Sport!, $m: BoardMode!) { currentUser { setBoard(mode: $m, sport: $sp) { id title
  myCurrentStep { __typename id level state target
    ... on CareerStep { title maxLineupsCount remainingLineupsCount pendingLineupsCount }
    ... on SquadStep { totalLineups totalScore minimumLineupsToStartStep }
    myLineups { ... on TaskLineup { id aasmState taskAppearances { ... on TaskAppearanceInterface { anyPlayer { slug displayName } anyCard { slug } } } } }
    displayedTypedRules { key ... on So5AverageScoresRule { averageType max }
      ... on So5AppearancesRule { appearances { name positions sub } } } } } } }"""
BENCH = """query($st: String!, $after: String) { currentUser { step(id: $st) { myFilteredBench(filters: {}, first: 100, after: $after) {
  pageInfo { hasNextPage endCursor }
  nodes { ... on ComposeTeamBenchCard { position positions anyCard { slug xp }
    anyPlayer { displayName slug ... on NBAPlayer { gameplayTierStars activeInjuries { id } } }
    eligiblePlayerGameScores(stepId: $st) { anyGame { id date } projectedScore } } } } } } }"""
UPSERT = """mutation($input: upsertStepLineupInput!) { upsertStepLineup(input: $input) { errors { message } lineup { id } } }"""


def bench(step_id):
    out, after = [], None
    for _ in range(10):
        d = gql(BENCH, {"st": step_id, "after": after}, token=token())["currentUser"]["step"]["myFilteredBench"]
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


def run(dry=False, sports=("NBA",)):
    now = dt.datetime.now(dt.timezone.utc)
    rep = []
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
            head = f"{label} ({b.get('title')}, nivell {st['level'] + 1}, objectiu {st['target']}, estat {st['state']})"
            if st["state"] not in ("PLAYABLE", "LINEUP_SET"):
                rep.append(f"ℹ️ {head}: no es pot jugar ara")
                continue
            existing = [l for l in st.get("myLineups") or [] if l]
            if mode == "CAREER":
                room = st.get("remainingLineupsCount") or 0
            else:
                room = max(0, 4 - len(existing))
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
                g = max(games, key=lambda g: g.get("projectedScore") or 0, default=None)
                if not g or not (g.get("projectedScore") or 0) > 0:
                    continue
                cands.append({"card": n["anyCard"]["slug"], "xp": n["anyCard"].get("xp") or 0, "player": p["slug"], "name": p["displayName"],
                              "stars": p.get("gameplayTierStars") or 0, "positions": n.get("positions") or [n.get("position")],
                              "proj": g["projectedScore"], "game": g["anyGame"]})
            # una carta per jugador: la de més XP
            byp = {}
            for c in cands:
                if c["player"] not in byp or c["xp"] > byp[c["player"]]["xp"]:
                    byp[c["player"]] = c
            pool = list(byp.values())
            lines = [head + f" · {len(pool)} jugadors que juguen · límit {cap} estrelles" if cap else head]
            made = 0
            for k in range(room):
                r = best(pool, slots, cap)
                if not r:
                    lines.append("   no queden jugadors per a una altra alineació")
                    break
                v, perm = r
                apps = [{"index": i, "cardSlug": c["card"], "gameId": c["game"]["id"].split(":")[-1]} for i, c in enumerate(perm)]
                txt = ", ".join(f"{c['name']} ({c['proj']:.0f}, {c['stars']}★)" for c in perm)
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
                chosen = {c["player"] for c in perm}
                pool = [c for c in pool if c["player"] not in chosen]
            rep.append("\n".join(lines))
    msg = "Sorare · Set" + (" (prova)" if dry else "") + "\n" + "\n".join(rep)
    for k, r in enumerate(rep):
        print(f"::notice title=set {k + 1}::" + r.replace("\n", " ¶ ")[:3900])
    if dry or any("✅ alineació" in r or "❌" in r for r in rep):
        telegram(msg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--sport", nargs="*", default=["NBA"])
    a = ap.parse_args()
    run(a.dry, tuple(a.sport))
