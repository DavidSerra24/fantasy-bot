"""Diagnosi: cartes d'un jugador al banc del Set de futbol (tauler personal): totes, lliures, partit i % (21/11: Lammens)."""
import sys
import datetime as dt
from bot.sorarefset import gql_step, bench
who = (sys.argv[2] if len(sys.argv) > 2 else "livakovic").lower()
st = gql_step({"m": "CAREER"})["currentUser"]["setBoard"]["myCurrentStep"]
alln = bench(st["id"], {"includeUsed": True})
free = {n["anyCard"]["slug"] for n in bench(st["id"], {})}
hi = {n["anyCard"]["slug"] for n in bench(st["id"], {"starterOddsBasisPointsRange": {"min": 8000}, "includeUsed": True})}
gk = {n["anyCard"]["slug"] for n in bench(st["id"], {"positions": ["Goalkeeper"], "includeUsed": True})}
rows = []
for n in alln + [x for x in bench(st["id"], {"positions": ["Goalkeeper"], "includeUsed": True}) if x]:
    if n and who in n["anyPlayer"]["slug"]:
        gs = [g["anyGame"]["date"] for g in n.get("eligiblePlayerGameScores") or [] if g and g.get("anyGame")]
        rows.append(f"{n['anyPlayer']['displayName']} {n['anyCard']['slug']} · lliure={n['anyCard']['slug'] in free} · ≥80%={n['anyCard']['slug'] in hi} · porter-filtre={n['anyCard']['slug'] in gk} · partits {gs}")
print(f"::notice title=probe3 {who} (banc {len(alln)} cartes)::" + (" ¶ ".join(sorted(set(rows))) or "no surt al banc"))
for m in ("CAREER", "SQUAD"):
    s2 = gql_step({"m": m})["currentUser"]["setBoard"]["myCurrentStep"]
    print(f"::notice title=alineacions {m} nivell {s2.get('level')} {s2.get('state')} (queden {s2.get('remainingLineupsCount')} de {s2.get('maxLineupsCount')})::" + " ¶ ".join(
        f"{l.get('aasmState')} {l.get('score')}: " + ", ".join(f"{a['anyPlayer']['displayName']} ({(a.get('game') or {}).get('date', '')[11:16]}Z)" for a in l.get("taskAppearances") or [] if a)
        for l in s2.get("myLineups") or []))
