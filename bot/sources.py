"""Fonts extra de titularitat per al Mister.

- FutbolFantasy (LaLiga): probabilitat de titularitat de cada jugador a les alineacions probables de la jornada
  (la mateixa dada que "Mis equipos" amb el filtre de forma i probabilitat).
- Jornada Perfecta (LaLiga Hypermotion): onzes probables, per als equips que SorareInside encara no té.
"""
import re

from bot.ff import name_score, norm

JP = "https://www.jornadaperfecta.com/segunda/onces-posibles/"


def best_name(full, names):
    """Nom de la llista que correspon a `full` (nom complet del Mister). Exigeix nom complet, o cognom igual
    amb la mateixa inicial, o un sol mot (p. ex. "Villar") que coincideixi amb el cognom."""
    nf = norm(full)
    best, bs = None, 0
    for n in names:
        sc = name_score(full, n)
        nn = norm(n)
        if sc == 60 and not (nn and nf and nn[-1] == nf[-1] and nn[0][0] == nf[0][0]):
            sc = 0
        if sc > bs:
            best, bs = n, sc
    return best if bs >= 60 else None


def ff_probs(page):
    """{nom FutbolFantasy: % titularitat} dels partits de la propera jornada de LaLiga."""
    from bot.extras import match_pages
    out = {}
    for p in match_pages(page, None):
        if p.get("name"):
            out[p["name"]] = max(out.get(p["name"], 0), p.get("pct") or 0)
    return out


def jp_starters(page, log=print):
    """Noms dels onzes probables de LaLiga Hypermotion a Jornada Perfecta (propera jornada sense jugar)."""
    page.goto(JP, wait_until="domcontentloaded", timeout=45000)
    page.wait_for_timeout(3000)
    txt = page.inner_text("body")
    if txt.count("Finalizado") >= 8:  # la pàgina encara mostra la jornada jugada: passar a la següent
        m = re.search(r"Jornada (\d+)", txt)
        if m:
            nxt = str(int(m.group(1)) + 1)
            try:
                page.select_option("select", nxt)
                page.wait_for_timeout(3500)
            except Exception:
                page.goto(f"{JP}?jornada={nxt}", wait_until="domcontentloaded"); page.wait_for_timeout(3000)
    links = page.evaluate("() => [...new Set([...document.querySelectorAll('a.jp-ui-fixture-card__link')].map(a => a.href))]")
    names = set()
    for url in links[:11]:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2000)
        cols = page.evaluate("""() => { const cs = [...document.querySelectorAll('.column-mobile.x2 > div')];
            const groups = cs.length >= 2 ? cs : [document.body];
            return groups.map(g => [...g.querySelectorAll('a[href*="/segunda/jugador/"]')].map(a => a.innerText.trim()).filter(Boolean)); }""")
        for c in cols[:2]:
            names.update(c[:11])
    log(f"Jornada Perfecta: {len(links)} partits, {len(names)} titulars")
    return names
