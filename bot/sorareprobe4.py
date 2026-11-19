"""Diagnosi (19/11): competicions de Sorare Pro de la propera jornada (Classic, In Season, Hot Streak…) i si es poden fer
amb les meves cartes (canCompose, cartes elegibles per posició i temporada)."""
from bot.sorare import gql, token

Q = """query($t: So5FixtureEvent!) { so5 { so5Fixture(sport: FOOTBALL, type: UPCOMING, eventType: $t) { slug gameWeek cutOffDate
  so5Leaderboards { rulesSummary slug displayName mainRarityType isArena seasonality format { title }
    canCompose { missingCards missingPositions notEnoughEligibleCards missingAnyRarities }
    eligibleCardsCountByPosition { position seasonality totalCount usedCardsCount }
    so5League { name myThresholdsStreakTasks { id progress currentThreshold { score } } } } } } }"""

for t in ("CLASSIC", "DAILY"):
    try:
        fx = gql(Q, {"t": t}, token=token())["so5"]["so5Fixture"]
    except Exception as e:
        print(f"::notice title={t}::error {e}"[:2000]); continue
    if not fx:
        print(f"::notice title={t}::cap jornada"); continue
    print(f"::notice title={t}::GW{fx['gameWeek']} {fx['slug']} tanca {fx['cutOffDate']} · {len(fx['so5Leaderboards'])} competicions")
    for l in fx["so5Leaderboards"]:
        if l["isArena"]:
            continue
        c = l["canCompose"] or {}
        ok = not (c.get("missingCards") or c.get("notEnoughEligibleCards") or c.get("missingPositions"))
        cnt = ", ".join(f"{x['position'][:3]} {x['seasonality'][:2]} {x['totalCount']}-{x['usedCardsCount']}"
                        for x in l["eligibleCardsCountByPosition"] if x["totalCount"])
        hs = (l.get("so5League") or {}).get("myThresholdsStreakTasks") or []
        hs_ = " · streak " + "; ".join(f"progrés {h['progress']} llindar {(h.get('currentThreshold') or {}).get('score')}" for h in hs) if hs else ""
        print(f"::notice title={'✅' if ok else '❌'} {l['format']['title']} · {l['seasonality']} · {l['mainRarityType']}::"
              f"[{l['format']['title']}] {l['displayName']} ({l['slug']}) · falten {c.get('missingCards')} cartes {c.get('missingPositions')} "
              f"poques={c.get('notEnoughEligibleCards')} · elegibles: {cnt}{hs_}")
        if l["seasonality"] == "IN_SEASON" and ("spain" in l["slug"] or "korea_limited" in l["slug"] or "contenders_limited" in l["slug"]):
            print(f"::notice title=regles {l['displayName']}::{(l.get('rulesSummary') or '')[:900]} ¶ {(l.get('description') or '')[:600]}".replace("\n", " ¶ "))
