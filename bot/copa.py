"""FutbolFantasy · extra «Goles en la primera ronda de la Copa del Rey» (16 places, gol = 10 punts).

Criteri (David, 27/10): de cada equip de LaLiga, el davanter amb més % de ser titular a la Copa segons les
alineacions probables de FutbolFantasy (/copa-del-rey/posibles-alineaciones). Desempat: més mitjana de punts.
Ús: python -m bot.copa [--dry] [--joc 1051]
"""
import argparse
import re

from playwright.sync_api import sync_playwright

from bot import ff
from bot.ff import FF, name_score
from bot.notify import telegram
from bot.web import inject, load_json, login_futbolfantasy, new_context, save_json, save_session

PLAYERS_JS = """(url) => [...document.querySelectorAll('[class*="jugador_"]')].map(e => {
    const a = e.querySelector('a[data-probabilidad]'); if (!a) return null;
    const name = e.querySelector('img[alt]')?.alt && e.querySelector('img[alt]').alt !== 'Más info' ? e.querySelector('img[alt]').alt
                 : e.innerText.replace(/\\s+/g, ' ').trim().replace(/^[\\d.%\\s]+/, '');
    return { name: name.replace(/^[%\\s]+/, '').trim(), url, pct: parseInt(a.getAttribute('data-probabilidad')) || 0,
             lesion: a.getAttribute('data-lesion'), media: parseFloat(a.getAttribute('data-totalpuntosfutmondostatspartido')) || 0,
             suplente: e.getAttribute('data-onceff') === 'suplente' };
}).filter(Boolean)"""


confirmed = []  # equips amb l'onze oficial ja publicat


def copa_players(pg):
    pg.goto(f"{FF}/copa-del-rey/posibles-alineaciones", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    links = pg.evaluate("() => [...new Set([...document.querySelectorAll('a[href*=\"/partidos/\"]')].map(a => a.href.split('#')[0]))]")
    teams = ("espanyol", "elche", "villarreal", "rayo", "malaga", "alaves", "levante", "betis", "celta", "valencia",
             "getafe", "osasuna", "athletic", "sevilla", "racing", "deportivo")
    links = [u for u in links if u.rstrip("/").split("-")[-1] in teams]
    out, copa = [], []
    confirmed.clear()
    for url in links[:40]:
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(2500)
        if "copa" not in pg.inner_text("body")[:600].lower():
            continue  # partit de LaLiga, no de Copa
        copa.append(url)
        if re.search(r"alineaci[oó]n (oficial|confirmada)", pg.inner_text("body")[:3000], re.I):
            confirmed.append(url.rstrip("/").split("-")[-1])
        rows = pg.evaluate(PLAYERS_JS, url)
        for i, r in enumerate(rows):
            r["idx"] = len(out) + i  # ordre a la pàgina (la Copa no té %)
        out += rows
    return copa, out


def run(dry=False, jid="1051"):
    report = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = new_context(b, "futbolfantasy")
        pg = ctx.new_page()
        login_futbolfantasy(pg)
        links, players = copa_players(pg)
        report.append(f"Partits llegits: {len(links)}, jugadors: {len(players)}; onzes oficials: {', '.join(confirmed) or 'cap encara'}")
        print("::notice title=links::" + " | ".join(links))
        # posició i equip de cada jugador al selector del joc
        pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
        inject(pg, "ff")
        cards0 = ff.cards(pg)
        me = next((c for c in cards0 if c["id"] == jid), None)
        look = jid
        if not me or not me["empty"]:  # joc ple (revisió): es busca amb el selector d'un altre joc de LaLiga amb places lliures
            look = next((c["id"] for c in cards0 if c["empty"] and re.search(r"Trío|revulsivo|antagonista", c["label"] + c["title"], re.I)), None)
            if not look:
                raise RuntimeError("no hi ha cap joc amb places lliures per buscar jugadors")
            pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            inject(pg, "ff")
        ff.open_picker(pg, look)
        cands = []
        for q in sorted([q for q in players if not q["suplente"] and str(q["lesion"]) in ("-1", "", "None")],
                        key=lambda q: (-q["pct"], q["idx"])):
            res = pg.evaluate("(s) => __ff.search(s)", q["name"]) or []
            if not res:
                res = pg.evaluate("(s) => __ff.search(s)", ff.plain(q["name"]).split()[-1]) or []
            res = [r for r in res if name_score(q["name"], r["n"]) >= 80]
            if len(res) == 1 and res[0]["p"] == "DEL":
                cands.append({**q, "ff": res[0]["n"], "ffid": res[0]["id"], "team": res[0]["t"]})
        ff.close_modal(pg)
        best = {}
        for c in cands:
            k = c["team"]
            if k not in best or (c["pct"], c["media"], -c["idx"]) > (best[k]["pct"], best[k]["media"], -best[k]["idx"]):
                best[k] = c
        pick = sorted(best.values(), key=lambda c: (-c["pct"], -c["media"]))[:16]
        names = ", ".join(f"{c['ff']} ({c['url'].rstrip('/').split('-')[-1]})" for c in pick)
        got = {c['url'] for c in pick}
        report.append("Sense davanter a l'onze probable: " + (", ".join(u.rstrip('/').split('-')[-1] for u in links if u not in got) or "cap"))
        report.append(f"Davanters ({len(pick)} equips): {names}")
        if dry and pick:
            card = next((c for c in ff.cards(pg) if c["id"] == jid), None)
            names = load_json("copa_pick.json", {})
            report.append("Canviaria: surten " + (", ".join(names.get(i, i) for i in card["ids"] if i not in {c["ffid"] for c in pick}) or "cap")
                          + " | entren " + (", ".join(c["ff"] for c in pick if c["ffid"] not in set(card["ids"])) or "cap"))
        if not dry and pick:
            card = next((c for c in ff.cards(pg) if c["id"] == jid), None)
            have = set(card["ids"]) if card else set()
            out_ids = [i for i in card["ids"] if i not in {c["ffid"] for c in pick}] if card else []
            todo = [c for c in pick if c["ffid"] not in have]
            names = load_json("copa_pick.json", {})
            if out_ids:  # revisió: es canvia directament a la casella (clic → buscador → nou jugador)
                swaps = []
                for oid, new in zip(out_ids, todo):
                    pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
                    inject(pg, "ff")
                    cur = next(c for c in ff.cards(pg) if c["id"] == jid)
                    slot = sorted(cur["slots"])[cur["ids"].index(oid)]
                    ff.click(pg, f'#juego-{jid} a.fantasy-slot[data-posicion="{slot}"]')
                    pg.locator(".modal.show").wait_for(timeout=10000); pg.wait_for_timeout(800)
                    print("::notice title=slotmodal::" + pg.evaluate("() => document.querySelector('.modal.show').innerText.replace(/\\s+/g,' ').slice(0,400)"))
                    if pg.locator(".modal.show input[type=text]").count():
                        pg.evaluate("(q) => __ff.search(q)", new["ff"])
                        item = pg.locator(".modal.show .sel-item:visible").filter(has=pg.locator(".sel-nombre", has_text=new["ff"])).first
                        item.click()
                        pg.wait_for_timeout(2000)
                    else:
                        q = pg.locator(".modal.show").get_by_text(re.compile("Quitar|Eliminar|Cambiar", re.I)).first
                        q.click(); pg.wait_for_timeout(1500)
                        if pg.locator(".modal.show input[type=text]").count():
                            pg.evaluate("(q) => __ff.search(q)", new["ff"])
                            pg.locator(".modal.show .sel-item:visible").filter(has=pg.locator(".sel-nombre", has_text=new["ff"])).first.click()
                            pg.wait_for_timeout(2000)
                    ff.close_modal(pg)
                    swaps.append(f"{names.get(oid, oid)} → {new['ff']}")
                report.append("Canvis: " + ", ".join(swaps))
                card = next((c for c in ff.cards(pg) if c["id"] == jid), None)
                have = set(card["ids"]) if card else set()
                todo = [c for c in pick if c["ffid"] not in have]
            save_json("copa_pick.json", {c["ffid"]: c["ff"] for c in pick})
            pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            inject(pg, "ff")
            ff.fill(pg, jid, todo)
            after = next((c for c in ff.cards(pg) if c["id"] == jid), {"ids": [], "empty": 16})
            report.append(f"{'✅' if after['empty'] == 16 - len(pick) else '⚠️'} posats: {len(after['ids'])}, buits: {after['empty']}")
        save_session(ctx, "futbolfantasy")
        b.close()
    msg = "FutbolFantasy · Copa del Rey" + (" (prova)" if dry else "") + "\n" + "\n".join(report)
    for l in report:
        print("::notice title=copa::" + l)
    telegram(msg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--joc", default="1051")
    a = ap.parse_args()
    try:
        run(a.dry, a.joc)
    except Exception:
        import traceback
        print("::notice title=tb::" + traceback.format_exc().replace("\n", " | ")[-1500:])
        raise
