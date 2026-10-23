"""Jocs extres de FutbolFantasy (LaLiga): Trío revulsivo, Trío antagonista i Resiliencia de portero.

Criteris (acordats amb el David):
  - Revulsivo: jugadors amb la marca "R" de revulsiu de FutbolFantasy, ≤50% de titularitat i sense lesió;
    els de millor mitjana de punts (desempat: menys % de titularitat).
  - Antagonista: els 2 porters titulars (≥80%) amb MENYS punts projectats + el jugador de camp titular (≥80%)
    amb més targetes grogues per partit.
  - Resiliencia de portero: els 3 porters titulars (≥80%) amb MÉS punts projectats.
"""
import datetime as dt
import re

from bot import ff, si
from bot.web import login_sorareinside, new_context, save_json, save_session

FF = "https://www.futbolfantasy.com"


def match_pages(page, jornada):
    """Jugadors de les pàgines de partit de la jornada de LaLiga (alineacions probables de FutbolFantasy)."""
    page.goto(f"{FF}/laliga/posibles-alineaciones", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)
    links = page.evaluate("() => [...new Set([...document.querySelectorAll('a[href*=\"/partidos/\"]')].map(a => a.href.split('#')[0]))]")
    players = []
    seen = 0
    for url in links[:24]:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2500)
        head = page.inner_text("body")[:200]
        m = re.search(r"Jornada (\d+)", head)
        if not m or int(m.group(1)) != jornada:
            continue
        seen += 1
        players += page.evaluate("""(url) => [...document.querySelectorAll('[class*="jugador_"]')].map(e => {
            const a = e.querySelector('a[data-probabilidad]'); if (!a) return null;
            const rv = e.querySelector('.ff-revulsivo');
            const name = e.querySelector('img[alt]')?.alt && e.querySelector('img[alt]').alt !== 'Más info' ? e.querySelector('img[alt]').alt
                         : e.innerText.replace(/\\s+/g, ' ').trim().replace(/^[\\d.]+\\s*/, '').replace(/^\\d+%\\s*/, '');
            const num = k => parseFloat(a.getAttribute('data-' + k)) || 0;
            return { name, url, suplente: e.getAttribute('data-onceff') === 'suplente', revulsivo: !!rv,
                     pct: parseInt(a.getAttribute('data-probabilidad')) || 0, lesion: a.getAttribute('data-lesion'),
                     pj: num('totalpartidosjugados'), amarillas: num('totalamarillas'), media: num('totalpuntosfutmondostatspartido') };
        }).filter(Boolean)""", url)
        if seen >= 10:
            break
    return players


def pick_revulsivo(players):
    c = [p for p in players if p["revulsivo"] and p["pct"] <= 50 and str(p["lesion"]) in ("-1", "", "None")]
    c.sort(key=lambda p: (-p["media"], p["pct"]))
    return c


def gk_list(sidata):
    out = []
    for t in sidata.get("_order", []):
        rows = sidata.get(t)
        if isinstance(rows, list) and rows and rows[0]:
            g = rows[0][0]
            if g.get("ps") is not None and (g.get("pct") or 0) >= 80:
                out.append({"si": g["name"], "team": t, "ps": g["ps"]})
    return out


def fill_names(page, jid, names, report, label):
    """Busca cada nom al selector del joc i el posa (usa la mateixa lògica de noms que el Fantasy)."""
    placed = []
    for n in names:
        if len(placed) >= 3:
            break
        ff.open_picker(page, jid)
        res = page.evaluate("(q) => __ff.search(q)", n) or []
        if not res and ff.norm(n):
            res = page.evaluate("(q) => __ff.search(q)", ff.norm(n)[-1]) or []
        best = max(res, key=lambda r: ff.name_score(n, r["n"]), default=None)
        if not best or ff.name_score(n, best["n"]) < 80 or (best["u"] is not None and str(best["u"]) == "0"):
            ff.close_modal(page)
            continue
        page.locator(".modal.show .sel-item:visible").filter(has=page.locator(".sel-nombre", has_text=best["n"])).first.click()
        page.locator(".modal.show").wait_for(state="hidden", timeout=10000)
        page.wait_for_timeout(800)
        placed.append(best["n"])
    report.append(f"{'✅' if len(placed) == 3 else '⚠️'} {label}: {', '.join(placed) or 'cap'}")
    return placed


def run(page, b, report, max_hours=20.0, dry=False):
    """page: sessió de FutbolFantasy ja iniciada. Omple els extres de LaLiga que estiguin buits i tanquin aviat."""
    cards = ff.cards(page)
    games = [c for c in cards if c["hours"] and 0 < c["hours"] <= max_hours and c["empty"] == 3
             and re.search(r"revulsivo|antagonista|resiliencia", c["title"] + c["label"], re.I)]
    if not games:
        return
    lal = next((c for c in cards if c["label"].startswith("LaLiga ·")), None)
    jornada = int(re.search(r"J(\d+)", games[0]["label"] + " " + games[0]["title"]).group(1)) if re.search(r"J(\d+)", games[0]["label"] + " " + games[0]["title"]) else None
    sctx = new_context(b, "sorareinside")
    spg = sctx.new_page()
    login_sorareinside(spg)
    save_session(sctx, "sorareinside")
    deadline = dt.datetime.now(ff.MADRID) + dt.timedelta(hours=games[0]["hours"])
    sidata = si.extract_league(spg, "Spain", "Primera División", deadline.date())
    gks = gk_list(sidata)
    players = match_pages(page, jornada) if jornada else []
    starters = [p for p in players if not p["suplente"] and p["pct"] >= 80]
    for g in games:
        t = (g["title"] + " " + g["label"]).lower()
        if "revulsivo" in t:
            names = [p["name"] for p in pick_revulsivo(players)]
            label = "Trío revulsivo"
        elif "antagonista" in t:
            low = sorted(gks, key=lambda x: x["ps"])[:2]
            hot = sorted([p for p in starters if p["pj"] > 0], key=lambda p: -(p["amarillas"] / p["pj"]))
            names = [x["si"] for x in low] + [p["name"] for p in hot if not any(ff.name_score(p["name"], x["si"]) >= 80 for x in low)]
            label = "Trío antagonista"
        else:
            names = [x["si"] for x in sorted(gks, key=lambda x: -x["ps"])]
            label = "Resiliencia de portero"
        if dry:
            report.append(f"🧪 {label} [prova]: {', '.join(names[:6])}")
            continue
        page.goto(f"{FF}/fantasy/activas", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        from bot.web import inject
        inject(page, "ff")
        fill_names(page, g["id"], names, report, label)
    save_json("extras_players.json", players)
