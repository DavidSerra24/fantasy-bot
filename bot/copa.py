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
from bot.web import inject, login_futbolfantasy, new_context, save_session

PLAYERS_JS = """(url) => [...document.querySelectorAll('[class*="jugador_"]')].map(e => {
    const a = e.querySelector('a[data-probabilidad]'); if (!a) return null;
    const name = e.querySelector('img[alt]')?.alt && e.querySelector('img[alt]').alt !== 'Más info' ? e.querySelector('img[alt]').alt
                 : e.innerText.replace(/\\s+/g, ' ').trim().replace(/^[\\d.%\\s]+/, '');
    return { name: name.replace(/^[%\\s]+/, '').trim(), url, pct: parseInt(a.getAttribute('data-probabilidad')) || 0,
             lesion: a.getAttribute('data-lesion'), media: parseFloat(a.getAttribute('data-totalpuntosfutmondostatspartido')) || 0,
             suplente: e.getAttribute('data-onceff') === 'suplente' };
}).filter(Boolean)"""


def copa_players(pg):
    pg.goto(f"{FF}/copa-del-rey/posibles-alineaciones", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    links = pg.evaluate("() => [...new Set([...document.querySelectorAll('a[href*=\"/partidos/\"]')].map(a => a.href.split('#')[0]))]")
    out = []
    for url in links[:20]:
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(2500)
        out += pg.evaluate(PLAYERS_JS, url)
    return links, out


def run(dry=False, jid="1051"):
    report = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = new_context(b, "futbolfantasy")
        pg = ctx.new_page()
        login_futbolfantasy(pg)
        links, players = copa_players(pg)
        report.append(f"Partits llegits: {len(links)}, jugadors: {len(players)}")
        # posició i equip de cada jugador al selector del joc
        pg.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
        inject(pg, "ff")
        ff.open_picker(pg, jid)
        cands = []
        for q in sorted([q for q in players if not q["suplente"] and q["pct"] >= 50 and str(q["lesion"]) in ("-1", "", "None")],
                        key=lambda q: -q["pct"]):
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
            if k not in best or (c["pct"], c["media"]) > (best[k]["pct"], best[k]["media"]):
                best[k] = c
        pick = sorted(best.values(), key=lambda c: (-c["pct"], -c["media"]))[:16]
        names = ", ".join(f"{c['ff']} {c['pct']}%" for c in pick)
        report.append(f"Davanters ({len(pick)} equips): {names}")
        if not dry and pick:
            card = next((c for c in ff.cards(pg) if c["id"] == jid), None)
            have = set(card["ids"]) if card else set()
            todo = [c for c in pick if c["ffid"] not in have]
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
    run(a.dry, a.joc)
