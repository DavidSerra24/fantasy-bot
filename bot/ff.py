"""FutbolFantasy Fantasy✨: omple els onzes buits amb els punts projectats de SorareInside.

Ús:  python -m bot.ff [--max-hours 20] [--only europa-league ...]
Normes (CLAUDE.md): ≥80% titular, respectar usos, tàctica vàlida, cap parella de rivals,
màxims punts projectats; empat → el que surt primer a la llista. Ítems → elegible amb més PS.
"""
import argparse
import json
import datetime as dt
import re
import unicodedata

from playwright.sync_api import sync_playwright

from bot import si
from bot.notify import telegram
from bot.web import ROOT, inject, login_futbolfantasy, login_sorareinside, new_context, save_json, save_session

FF = "https://www.futbolfantasy.com"
# Etiqueta del joc → (pàgina de la competició, país i lliga a SorareInside). L'ordre importa (LaLiga 2 abans que LaLiga).
COMPS = [
    ("LaLiga 2", "laliga2", ("Spain", "Segunda División")),
    ("LaLiga", "laliga", ("Spain", "Primera División")),
    ("Premier League", "premier-league", ("England", "Premier League")),
    ("Serie A", "serie-a", ("Italy", "Serie A")),
    ("Champions", "champions", ("Europe", "UEFA Champions League")),
    ("Europa League", "europa-league", ("Europe", "UEFA Europa League")),
]
ALIAS = json.loads((ROOT / "config" / "futbolfantasy.json").read_text(encoding="utf-8")).get("alias", {})
DEFAULT_TACTICS = ["5-3-2", "5-4-1", "4-5-1", "4-4-2", "4-3-3", "3-5-2", "3-4-3"]
POS = {"POR": "G", "DEF": "D", "MED": "M", "DEL": "F"}


def norm(s):
    return re.sub(r"[^a-z0-9 ]+", " ", unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode().lower()).split()


def name_score(a, b):
    ta, tb = norm(a), norm(b)
    if ta == tb:
        return 100
    sa, sb = set(ta), set(tb)
    if sa and sa <= sb or sb and sb <= sa:
        return 80
    if ta and tb and ta[-1] == tb[-1]:
        return 60
    # noms escurçats: "Rodri" / "Rodrigo" (mínim 4 lletres), el filtre d'equip evita confusions
    if any(len(x) >= 4 and len(y) >= 4 and (x.startswith(y) or y.startswith(x)) for x in ta for y in tb):
        return 60
    return len(sa & sb) * 20


def hours_left(rem):
    d = dict((u, int(n)) for n, u in re.findall(r"(\d+)\s*([dhms])", rem))
    return d.get("d", 0) * 24 + d.get("h", 0) + d.get("m", 0) / 60


def candidates(sidata):
    order = sidata["_order"]
    opp = {}
    for i in range(0, len(order) - 1, 2):
        opp[order[i]], opp[order[i + 1]] = order[i + 1], order[i]
    out = []
    for t in order:
        rows = sidata.get(t)
        if not isinstance(rows, list):
            continue
        for r in rows:
            for p in r:
                if p.get("ps") is not None and (p.get("pct") or 0) >= 80:
                    out.append({"si": p["name"], "team": t, "opp": opp.get(t), "ps": p["ps"], "pct": p["pct"]})
    out.sort(key=lambda x: -x["ps"])  # ordenació estable: en cas d'empat, l'ordre de la llista
    for i, c in enumerate(out):
        c["idx"] = i
    return out


def open_picker(page, jid):
    page.locator(f'a.fantasy-add[data-juego="{jid}"]').first.click()
    page.locator(".modal.show input[type=text]").wait_for(timeout=10000)
    page.wait_for_timeout(600)


def close_modal(page):
    if page.locator(".modal.show").count():
        page.keyboard.press("Escape")
        page.wait_for_timeout(600)
        if page.locator(".modal.show .close").count():
            page.locator(".modal.show .close").first.click()
            page.wait_for_timeout(500)


def lookup(page, jid, cands, limit=60):
    """Busca cada candidat al selector: posició, usos i equip a FutbolFantasy.
    Primer dedueix l'equip de FutbolFantasy de cada equip de SorareInside amb els noms segurs,
    i després només accepta jugadors d'aquell equip (evita confondre Nico Paz amb Yeferson Paz)."""
    from collections import Counter
    open_picker(page, jid)
    raw = []
    for c in cands[:limit]:
        c["si"] = ALIAS.get(f"{c['team']}|{c['si']}", ALIAS.get(c["si"], c["si"]))
        res = page.evaluate("(q) => __ff.search(q)", c["si"]) or []
        if not res and norm(c["si"]):
            res = page.evaluate("(q) => __ff.search(q)", norm(c["si"])[-1]) or []
        raw.append((c, res))
    close_modal(page)
    votes = {}
    for c, res in raw:
        strong = [r for r in res if name_score(c["si"], r["n"]) >= 80]
        if len(strong) == 1 and strong[0]["t"]:
            votes.setdefault(c["team"], Counter())[strong[0]["t"]] += 1
    team_id = {t: v.most_common(1)[0][0] for t, v in votes.items()}
    found, missing = [], []
    for c, res in raw:
        tid = team_id.get(c["team"])
        ok = [r for r in res if r["p"] in POS and (r["t"] == tid if tid else name_score(c["si"], r["n"]) >= 80)]
        best = max(ok, key=lambda r: name_score(c["si"], r["n"]), default=None)
        if not best or name_score(c["si"], best["n"]) < 60:
            if c["ps"] >= (cands[min(15, len(cands) - 1)]["ps"] if cands else 0):
                missing.append(f"{c['si']} ({c['team']}, {c['ps']} PS)")
            continue
        if best["u"] is not None and str(best["u"]) == "0":
            continue  # sense usos
        found.append({**c, "ff": best["n"], "pos": POS[best["p"]], "uses": best["u"]})
    return found, missing


def optimise(found, tactics):
    best = None
    for tac in tactics:
        d, m, f = map(int, tac.split("-"))
        need = {"G": 1, "D": d, "M": m, "F": f}
        pick, teams = [], set()
        for c in found:  # ja ordenats per PS (i ordre de la llista en cas d'empat)
            if need[c["pos"]] and c["opp"] not in teams:
                pick.append(c)
                need[c["pos"]] -= 1
                teams.add(c["team"])
        if any(need.values()):
            continue
        key = (sum(c["ps"] for c in pick), -sum(c["idx"] for c in pick))
        if best is None or key > best[0]:
            best = (key, tac, pick)
    return best


def fill(page, jid, pick):
    for c in pick:
        open_picker(page, jid)
        page.evaluate("(q) => __ff.search(q)", c["ff"])
        item = page.locator(".modal.show .sel-item:visible").filter(has=page.locator(".sel-nombre", has_text=c["ff"])).first
        item.click()
        page.locator(".modal.show").wait_for(state="hidden", timeout=10000)
        page.wait_for_timeout(800)


def use_items(page, comp_slug, pick, report):
    page.goto(f"{FF}/fantasy/{comp_slug}", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    btn = page.locator("a, button").filter(has_text=re.compile(r"Ítems")).first
    if not btn.count():
        return
    for _ in range(5):
        btn.click()
        page.wait_for_timeout(1500)
        cards = page.locator(".modal.show .item-card")
        n = cards.count()
        done = False
        for i in range(n):
            card = cards.nth(i)
            name = card.get_attribute("data-nombre")
            card.click()
            page.wait_for_timeout(1500)
            txt = page.locator(".modal.show").inner_text()
            if "Elige un jugador" not in txt:
                continue
            eligible = [c for c in pick if c["ff"] in txt]
            if not eligible:
                continue
            target = max(eligible, key=lambda c: (c["ps"], -c["idx"]))
            page.locator(".modal.show").get_by_text(target["ff"], exact=True).first.click()
            page.wait_for_timeout(2000)
            report.append(f"   🎁 {name} → {target['ff']}")
            done = True
            break
        close_modal(page)
        if not done:
            return


def run(max_hours=20.0, only=None, dry=False):
    report = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = new_context(b, "futbolfantasy")
        pg = ctx.new_page()
        login_futbolfantasy(pg)
        save_session(ctx, "futbolfantasy")
        pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
        pg.wait_for_timeout(3000)
        inject(pg, "ff")
        games = pg.evaluate("() => __ff.games()")
        sctx = spg = None
        for g in games:
            comp = next((c for c in COMPS if g["label"].startswith(c[0] + " ·")), None)
            if not comp:
                if g["empty"]:
                    report.append(f"✋ {g['label'] or g['title']}: pendent (joc especial, encara no automatitzat)")
                continue
            label, slug, (country, league) = comp
            if only and slug not in only:
                continue
            h = hours_left(g["rem"])
            if g["empty"] < 11:
                continue  # ja fet (o a mitges: no el toquem)
            if h > max_hours:
                report.append(f"⏳ {g['label']}: tanca d'aquí a {h:.0f} h, encara no")
                continue
            if spg is None:
                sctx = new_context(b, "sorareinside")
                spg = sctx.new_page()
                login_sorareinside(spg)
                save_session(sctx, "sorareinside")
            deadline = dt.datetime.now() + dt.timedelta(hours=h)
            sidata = si.extract_league(spg, country, league, deadline.date())
            save_json(f"si_ff_{slug}.json", sidata)
            cands = candidates(sidata)
            # Regles del joc: tàctiques permeses.
            pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
            pg.wait_for_timeout(2500)
            inject(pg, "ff")
            found, missing = lookup(pg, g["id"], cands)
            tactics = DEFAULT_TACTICS
            best = optimise(found, tactics)
            if not best:
                report.append(f"❌ {g['label']}: no he trobat un onze vàlid")
                continue
            (total, _), tac, pick = best
            order = {"G": 0, "D": 1, "M": 2, "F": 3}
            names = ", ".join(f"{c['ff']} {c['ps']}" for c in sorted(pick, key=lambda c: order[c["pos"]]))
            if dry:
                report.append(f"🧪 {g['label']} ({tac}, {total} PS) [prova, no desat]: {names}" + (f" | ⚠️ no trobats a FutbolFantasy: {', '.join(missing)}" if missing else ""))
                continue
            fill(pg, g["id"], pick)
            # Comprovació
            pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
            pg.wait_for_timeout(3000)
            inject(pg, "ff")
            left = next((x["empty"] for x in pg.evaluate("() => __ff.games()") if x["id"] == g["id"]), 0)
            report.append(f"{'✅' if left == 0 else '⚠️'} {g['label']} ({tac}, {total} PS): {names}" + ("" if left == 0 else f" — falten {left}") + (f" | ⚠️ no trobats a FutbolFantasy: {', '.join(missing)}" if missing else ""))
            use_items(pg, slug, pick, report)
        save_session(ctx, "futbolfantasy")
        b.close()
    msg = "FutbolFantasy Fantasy✨\n" + ("\n".join(report) or "Res a fer ara.")
    print(msg)
    for l in report:
        print("::notice title=ff::" + l)
    telegram(msg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-hours", type=float, default=20.0)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    run(a.max_hours, a.only, a.dry)
