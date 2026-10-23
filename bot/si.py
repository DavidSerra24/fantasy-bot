"""SorareInside: tria la gameweek i extreu els onzes previstos d'una lliga."""
import datetime as dt
import re

from bot.web import inject, load_json, save_json

MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def gameweeks(page, year):
    """Llista de (nom, inici, fi) a partir del selector de gameweeks."""
    cards = page.evaluate("""() => [...document.querySelectorAll('main *')]
      .filter(e => /^GW\\d+$/.test(e.textContent.trim()) && e.childElementCount === 0)
      .map(e => { let c = e; for (let i = 0; i < 4; i++) { if (/[A-Z][a-z]{2}/.test(c.innerText.replace(/GW\\d+/, '')) && c.innerText.length < 60) break; c = c.parentElement; }
                  return c.innerText.replace(/\\s+/g, ' ').trim(); })""")
    out = []
    for t in cards:
        m = re.match(r"(GW\d+) (\d+) - (\d+) ([A-Z][a-z]{2})(?: - ([A-Z][a-z]{2}))?", t)
        if not m:
            continue
        name, d1, d2, m1, m2 = m.groups()
        mo1 = MONTHS[m1]
        mo2 = MONTHS[m2] if m2 else mo1
        y1 = year if not (mo1 == 12 and mo2 == 1) else year
        start = dt.date(y1, mo1, int(d1))
        end = dt.date(y1 + (1 if mo2 < mo1 else 0), mo2, int(d2))
        out.append((name, start, end))
    return out


def pick_gameweek(page, day):
    """Clica la gameweek que conté el dia `day` (el dia de canvi pertany a la nova)."""
    gws = gameweeks(page, day.year)
    cands = [g for g in gws if g[1] <= day < g[2]] or [g for g in gws if g[1] <= day <= g[2]]
    if not cands:
        raise RuntimeError(f"No trobo cap gameweek per al {day}: {gws}")
    name = cands[-1][0]
    page.evaluate("""(n) => { const e = [...document.querySelectorAll('main *')].find(x => x.childElementCount === 0 && x.textContent.trim() === n);
                              let c = e; for (let i = 0; i < 4; i++) { c = c.parentElement; if (c.onclick || c.getAttribute('role') || c.tagName === 'BUTTON' || c.tagName === 'A') break; } (c || e).click(); }""", name)
    page.wait_for_timeout(4000)
    return name


def league_age_minutes(page, country, league):
    """Minuts (com a mínim) des de l'última actualització de la lliga a SorareInside ("Updated X ago")."""
    txt = page.evaluate("""([c, l]) => { const all = [...document.querySelectorAll('main *')].filter(e => e.childElementCount === 0).map(e => e.textContent.trim()).filter(Boolean);
        let cur = null; for (let i = 0; i < all.length; i++) { if (all[i] === c) cur = c; else if (cur === c && all[i] === l) { return all.slice(i + 1, i + 4).find(t => /^Updated /.test(t)) || null; } } return null; }""", [country, league])
    if not txt:
        return None
    t = txt.lower()
    if "second" in t or "just now" in t:
        return 0
    m = re.search(r"(\d+|an?) (minute|hour|day)", t)
    if not m:
        return None
    n = 1 if m.group(1) in ("a", "an") else int(m.group(1))
    unit = {"minute": 1, "hour": 60, "day": 1440}[m.group(2)]
    # límit inferior ("an hour ago" = 45-89 min, "3 hours" = 2,5-3,5 h): així mai es fa servir una dada antiga per error
    if unit == 1:
        return n
    return 45 if (unit == 60 and n == 1) else n * unit - unit // 2


def extract_league(page, country, league, day, log=print, use_cache=True):
    """Retorna {equip: files} per a la lliga a la gameweek del dia `day`.
    Si SorareInside diu que la lliga no s'ha actualitzat des de l'última lectura, retorna les dades guardades."""
    page.goto("https://sorareinside.com/lineups", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    gw = pick_gameweek(page, day)
    key = f"si_cache_{re.sub(r'[^a-z0-9]+', '_', (league + '_' + gw).lower())}.json"
    now = dt.datetime.now(dt.timezone.utc)
    age = league_age_minutes(page, country, league)
    cache = load_json(key)
    if use_cache and cache and age is not None:
        updated_at = now - dt.timedelta(minutes=age)
        read_at = dt.datetime.fromisoformat(cache["read_at"])
        if updated_at < read_at - dt.timedelta(minutes=5):
            log(f"SorareInside {league} {gw}: sense canvis des de la darrera lectura (actualitzada fa {age}+ min)")
            return cache["data"]
    inject(page, "si")
    r = page.evaluate("([c,l]) => __si.league(c,l)", [country, league])
    if r != "ok":
        raise RuntimeError(f"SorareInside: no trobo {country}/{league} a {gw}")
    page.wait_for_timeout(2500)
    teams = page.evaluate("() => __si.anchors()")
    log(f"SorareInside {league} {gw}: {len(teams)} equips")
    data = {"_gw": gw, "_order": teams}
    for t in teams:
        data[t] = page.evaluate("(t) => __si2.team(t)", t)
    save_json(key, {"read_at": now.isoformat(), "data": data})
    return data
