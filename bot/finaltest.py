"""Prova de la revisió final amb un onze PLE (Europa League J4, tanca el 5/11).
1) calcula l'onze òptim, 2) omple un onze amb 3 jugadors pitjors, 3) revisió final,
4) comprova que queda l'onze òptim, 5) ho buida tot."""
import datetime as dt
from playwright.sync_api import sync_playwright
from bot import ff, si
from bot.web import new_context, login_futbolfantasy, login_sorareinside, inject

def note(m):
    for i in range(0, len(m), 900):
        print("::notice title=t::" + m[i:i+900])

with sync_playwright() as p:
    b = p.chromium.launch()
    sctx = new_context(b, "sorareinside"); spg = sctx.new_page(); login_sorareinside(spg)
    sidata = si.extract_league(spg, "Europe", "UEFA Europa League", dt.date(2026, 10, 22), use_cache=False)
    cands = ff.candidates(sidata)
    ctx = new_context(b, "futbolfantasy"); pg = ctx.new_page(); login_futbolfantasy(pg)
    g = next(c for c in ff.cards(pg) if c["label"].startswith("Europa League · J4"))
    assert g["empty"] == 11, "el joc de prova no és buit"
    inject(pg, "ff")
    found, _ = ff.lookup(pg, g["id"], cands)
    (_, _), tac, best = ff.optimise(found, ff.DEFAULT_TACTICS)
    best_names = [c["ff"] for c in best]
    note(f"òptim ({tac}): {best_names}")
    # onze pitjor: canviar 3 jugadors (D, M, F) pel candidat més fluix de la mateixa posició
    worse, swapped = list(best), []
    for pos in ["D", "M", "F"]:
        i = next(i for i, c in enumerate(worse) if c["pos"] == pos)
        teams = {c["team"] for c in worse}
        alt = [c for c in found if c["pos"] == pos and c["ff"] not in best_names and c["opp"] not in teams]
        if alt:
            swapped.append((worse[i]["ff"], alt[-1]["ff"]))
            worse[i] = alt[-1]
    note(f"onze de prova (pitjor): canvis {swapped}")
    pg.goto(f"{ff.FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500); inject(pg, "ff")
    ff.fill(pg, g["id"], worse)
    g = next(c for c in ff.cards(pg) if c["id"] == g["id"])
    note(f"omplert: {11 - g['empty']} jugadors; caselles: {[s['name'] for s in ff.read_slots(pg, g['id'])]}")
    report = []
    r = ff.final_review(pg, g, cands, report, "PROVA", dry=False)
    note(f"revisió: {r[3] if r else r} {report}")
    sl = ff.read_slots(pg, g["id"])
    got = [s["name"] for s in sl]
    okn = all(any(ff.name_score(n, s) >= 60 for s in got) for n in best_names)
    note(f"{'✅ PROVA SUPERADA' if okn and len(sl) == 11 else '❌ PROVA FALLIDA'}: {len(sl)} jugadors: {got}")
    for s_ in ff.read_slots(pg, g["id"]):
        ff.remove_slot(pg, g["id"], s_["slot"])
    g = next(c for c in ff.cards(pg) if c["id"] == g["id"])
    note(f"neteja: {g['empty']} caselles buides")
    b.close()
