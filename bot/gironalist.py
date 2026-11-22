"""Manual (22/11): jugadors del Girona (cartes lliures o no) ordenats pels punts previstos de Sorare."""
from bot.sorare import gql, token
from bot import sorarelineup as L
fx = gql(L.FIXTURE_SLUG, {"s": "football-20-24-nov-2026"}, token=token())["so5"]["so5Fixture"]
out = []
for rar, rars in (("limited", L.ARENA_RAR), ("rare", ("rare", "super_rare", "unique"))):
    arena = next(l for l in fx["so5Leaderboards"] if l["isArena"] and "beginner" in l["slug"] and (l.get("mainRarityType") or "").lower() == rar)
    L.GAZZA_KEEP = 0
    qs = [q for q in L.cards(arena, floor=0, rarities=rars) if q["girona"]]
    seen = {}
    for q in qs:
        k = q["player"].split("#")[0]
        if k not in seen:
            seen[k] = q
    rows = sorted(seen.values(), key=lambda q: -(q.get("proj") or 0))
    out.append(f"{rar.upper()}: " + " | ".join(f"{q['name']} ({q['pos'][:3]}) {q.get('proj') or 0:.0f} {q.get('grade') or '?'} mitjana {q.get('avg', 0):.0f}" for q in rows))
print("::notice title=girona::" + " ¶ ".join(out))
