"""Sofascore: partits del dia i onzes (confirmats o no), des d'un navegador real per evitar bloquejos."""
import datetime as dt
import json

API = "https://www.sofascore.com/api/v1"
# Noms de torneig a Sofascore per a cada competició
TOURNAMENTS = {"laliga": "LaLiga", "laliga2": "LaLiga 2", "premier-league": "Premier League", "serie-a": "Serie A",
               "champions": "UEFA Champions League", "europa-league": "UEFA Europa League"}
COUNTRY = {"laliga": "Spain", "laliga2": "Spain", "premier-league": "England", "serie-a": "Italy"}


def _get(page, url):
    r = page.evaluate("async (u) => { const r = await fetch(u); return {s: r.status, t: await r.text()}; }", url)
    if r["s"] != 200:
        raise RuntimeError(f"Sofascore {r['s']} {url}")
    return json.loads(r["t"])


def open_page(ctx):
    pg = ctx.new_page()
    pg.goto("https://www.sofascore.com/", wait_until="domcontentloaded")
    pg.wait_for_timeout(3000)
    return pg


def events(page, day, comp):
    data = _get(page, f"{API}/sport/football/scheduled-events/{day.isoformat()}")
    out = []
    for e in data.get("events", []):
        t = e.get("tournament", {})
        ut = t.get("uniqueTournament", {}) or {}
        name = ut.get("name") or t.get("name")
        country = (t.get("category") or {}).get("name")
        if name == TOURNAMENTS[comp] and (comp not in COUNTRY or country == COUNTRY[comp]):
            out.append({"id": e["id"], "start": dt.datetime.fromtimestamp(e["startTimestamp"], dt.timezone.utc),
                        "home": e["homeTeam"]["name"], "away": e["awayTeam"]["name"]})
    return sorted(out, key=lambda x: x["start"])


def lineups(page, event_id):
    """{'confirmed': bool, 'home': [noms titulars], 'away': [...], 'home_subs': [...], 'away_subs': [...]}"""
    d = _get(page, f"{API}/event/{event_id}/lineups")
    res = {"confirmed": bool(d.get("confirmed"))}
    for side in ("home", "away"):
        pl = (d.get(side) or {}).get("players", [])
        res[side] = [p["player"]["name"] for p in pl if not p.get("substitute")]
        res[side + "_subs"] = [p["player"]["name"] for p in pl if p.get("substitute")]
    return res
