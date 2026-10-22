"""SorareInside: tria la gameweek i extreu els onzes previstos d'una lliga."""
import datetime as dt
import re

from bot.web import inject

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


def extract_league(page, country, league, day, log=print):
    """Retorna {equip: files} per a la lliga a la gameweek del dia `day`."""
    page.goto("https://sorareinside.com/lineups", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    gw = pick_gameweek(page, day)
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
    return data
