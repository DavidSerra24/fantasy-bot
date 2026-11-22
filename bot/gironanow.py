"""Manual (22/11): Arenes del Girona ara mateix. «gironanow» = prova (mostra), «gironanow go» = les envia."""
import sys
from bot.sorare import gql, token
from bot import sorarelineup as L
SLUG = "football-20-24-nov-2026"
go = "go" in sys.argv
fx = gql(L.FIXTURE_SLUG, {"s": SLUG}, token=token())["so5"]["so5Fixture"]
out = []
for rar in ("limited", "rare"):
    arena, built, props, dates, gprops = L.arena_props(fx, final=True, approved=[], rar=rar)
    ess = (arena or {}).get("format", {}).get("entryItem") or {}
    out.append(f"{rar}: arena {(arena or {}).get('slug')} · {len(gprops)} del Girona")
    for pick, cap in gprops:
        gir = [q["name"] + (" ✓" if q.get("xi") else " ?") for q in pick if q.get("girona")]
        txt = L.arena_text(pick, cap)
        out.append(f"  {rar.upper()}: {txt} · Girona: {', '.join(gir)} · primer partit {min(L._when(q) for q in pick)}")
        if go:
            try:
                L.save_lineup(arena, pick, cap, entry=ess.get("myEntryItemId"))
                out.append("    ✅ ENVIADA")
                L.telegram(f"✅ Arena {'Rare ' if rar == 'rare' else ''}del Girona enviada: {txt}")
            except Exception as e:
                out.append(f"    ❌ {str(e)[:300]}")
print("::notice title=girona ara::" + " ¶ ".join(out))
