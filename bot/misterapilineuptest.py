"""Prova d'escriptura de l'alineació per l'API (Quique): canvia i torna a deixar igual tàctica, capità i un jugador.
La jornada ha de començar d'aquí a dies (abans de començar els canvis són gratuïts). Ús: python -m bot.misterapilineuptest"""
from bot.misterapi import MisterAPI

api = MisterAPI().login()
api.community(2499621)
st0 = api.lineup()
assert st0 and not any(x["off"] for x in st0["slots"]), "jornada començada o bloquejada"
log = [f"inici: {st0['formation']} capità slot {next((x['slot'] for x in st0['slots'] if x['cap']), '?')} gw {st0['gw']} gwid {st0['gwid']} uc {st0['id_uc']}"]
try:
    # 1) capità a un altre i tornar
    cap0 = next((x for x in st0["slots"] if x["cap"]), None)
    other = next(x for x in st0["slots"] if x["pid"] not in ("0", None) and not x["cap"])
    api.captain(st0, other["slot"]); st = api.lineup()
    log.append(f"capità → slot {other['slot']}: {'OK' if any(x['cap'] and x['slot'] == other['slot'] for x in st['slots']) else 'NO'}")
    if cap0:
        api.captain(st, cap0["slot"]); st = api.lineup()
        log.append(f"capità → slot {cap0['slot']} (tornar): {'OK' if any(x['cap'] and x['slot'] == cap0['slot'] for x in st['slots']) else 'NO'}")
    # 2) un defensa per un suplent i tornar
    d = next(x for x in st["slots"] if x["pos"] == "2" and x["pid"] not in ("0", None))
    info = api.slot_info(st, d["slot"])
    cand = [k for k in (info.get("list") or {}) if str(k) != d["pid"]]
    if cand:
        api.put(st, d["slot"], cand[0]); st = api.lineup()
        log.append(f"slot {d['slot']} {d['pid']} → {cand[0]}: {'OK' if any(x['slot'] == d['slot'] and x['pid'] == str(cand[0]) for x in st['slots']) else 'NO'}")
        api.put(st, d["slot"], d["pid"]); st = api.lineup()
        log.append(f"slot {d['slot']} → {d['pid']} (tornar): {'OK' if any(x['slot'] == d['slot'] and x['pid'] == d['pid'] for x in st['slots']) else 'NO'}")
    else:
        log.append("cap suplent de defensa per provar el canvi")
    # 3) tàctica: una altra amb les mateixes línies no és trivial; només es prova tornar a posar la mateixa
    api.set_formation(st, st["formation"]); st = api.lineup()
    log.append(f"tàctica {st['formation']} (mateixa): OK")
except Exception as e:
    log.append(f"ERROR {type(e).__name__}: {e}")
st = api.lineup()
same = [(x["slot"], x["pid"], x["cap"]) for x in st["slots"]] == [(x["slot"], x["pid"], x["cap"]) for x in st0["slots"]] and st["formation"] == st0["formation"]
log.append("final igual que l'inici: " + ("SÍ" if same else "NO ⚠️ " + str([(x['slot'], x['pid'], x['cap']) for x in st['slots']])))
for l in log:
    print("::notice title=prova api alineació::" + l)
