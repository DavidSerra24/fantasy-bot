"""ESPN: hora dels partits i onzes oficials (quan ja s'han publicat). No bloqueja GitHub."""
import datetime as dt

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36"}
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
LEAGUE = {"laliga": "esp.1", "laliga2": "esp.2", "premier-league": "eng.1", "serie-a": "ita.1",
          "champions": "uefa.champions", "europa-league": "uefa.europa"}


def events(comp, day):
    out = []
    for d in (day - dt.timedelta(days=1), day, day + dt.timedelta(days=1)):
        r = requests.get(f"{BASE}/{LEAGUE[comp]}/scoreboard?dates={d:%Y%m%d}", headers=H, timeout=20)
        for e in r.json().get("events", []):
            comp_ = e["competitions"][0]
            teams = {c["homeAway"]: c["team"]["displayName"] for c in comp_["competitors"]}
            start = dt.datetime.fromisoformat(e["date"].replace("Z", "+00:00"))
            out.append({"id": e["id"], "start": start, "home": teams.get("home"), "away": teams.get("away")})
    uniq = {e["id"]: e for e in out}
    return sorted(uniq.values(), key=lambda x: x["start"])


def matches_at(comp, kickoff, tol_min=10):
    """Partits que comencen a l'hora `kickoff` (UTC), ±tol_min."""
    return [e for e in events(comp, kickoff.date()) if abs((e["start"] - kickoff).total_seconds()) <= tol_min * 60]


def starters(comp, event_id):
    """{nom_equip: [titulars]} o None si encara no hi ha onzes oficials."""
    s = requests.get(f"{BASE}/{LEAGUE[comp]}/summary?event={event_id}", headers=H, timeout=20).json()
    out = {}
    for ro in s.get("rosters", []):
        names = [p["athlete"]["displayName"] for p in ro.get("roster", []) if p.get("starter")]
        if len(names) >= 11:
            out[ro["team"]["displayName"]] = names
    return out if len(out) == 2 else None
