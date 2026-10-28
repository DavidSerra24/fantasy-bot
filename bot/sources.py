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
    """Entrades {name, key (URL del partit), pct} de les alineacions probables de FutbolFantasy (LaLiga)."""
    from bot.extras import match_pages
    ps = [p for p in match_pages(page, None) if p.get("name")]
    js = [p["j"] for p in ps if p.get("j") and (p.get("pct") or 0) > 0]  # les jornades ja jugades surten amb 0%
    j = min(js) if js else None  # la propera jornada (la pàgina també pot mostrar la següent)
    return [{"name": p["name"], "key": p["url"], "pct": p.get("pct") or 0, "ps": None}
            for p in ps if j is None or p.get("j") == j]


def si_entries(sidata):
    """Entrades {name, key (equip), pct, ps} de SorareInside (titulars i suplents)."""
    out = []
    for t in sidata.get("_order", []):
        rows = sidata.get(t)
        if not isinstance(rows, list):
            continue
        for i, r in enumerate(rows):
            line = "G" if i == 0 else "X"  # la primera fila de SorareInside és la del porter
            for q in r:
                out.append({"name": q.get("name") or "", "key": t, "pct": q.get("pct"), "ps": q.get("ps"), "line": line, "starter": True})
                for sub in q.get("subs") or []:
                    out.append({"name": sub.get("name") or "", "key": t, "pct": sub.get("pct"), "ps": None, "line": line, "starter": False})
    return out


STOP = {"real", "club", "deportivo", "sporting", "union", "athletic", "atletico", "cd", "cf", "ud", "sd", "fc", "rcd", "ca"}


# Slug de l'equip al Mister → nom curt a les URL de partit de FutbolFantasy (quan el nom és una paraula «genèrica»)
URL_TEAM = {"deportivo-da-coruna": "deportivo", "deportivo": "deportivo", "athletic-club": "athletic", "athletic": "athletic",
            "atletico-madrid": "atletico", "atletico": "atletico", "real-madrid": "madrid", "real-sociedad": "sociedad",
            "real-betis": "betis", "real-oviedo": "oviedo", "real-zaragoza": "zaragoza", "real-valladolid": "valladolid",
            "real-racing-club": "racing", "racing-santander": "racing"}


def team_ok(slug, key):
    """L'equip del Mister (slug, p. ex. 'real-valladolid') correspon a la clau de la font?
    La clau és el nom de l'equip (SorareInside) o l'URL del partit (Jornada Perfecta / FutbolFantasy)."""
    from bot.ff import team_score
    if not slug or not key:
        return False
    if "/" in key:  # URL del partit: el slug ha d'aparèixer a l'últim tros
        last = key.rstrip("/").split("/")[-1]
        short = URL_TEAM.get(slug)
        if short:
            return short in last.split("-")
        toks = [t for t in slug.split("-") if len(t) >= 4 and t not in STOP] or [t for t in slug.split("-") if len(t) >= 3]
        return any(t in last.split("-") for t in toks)
    return team_score(key, slug.replace("-", " ")) > 0


def assign(players, entries, field="src"):
    """Relaciona cada jugador del Mister (name, team = slug de l'equip al Mister) amb una entrada de la font,
    només dins del seu equip. Així no es confon David López (Girona) amb el del Mallorca.
    Si no se sap l'equip, només s'accepta un nom exacte i únic."""
    for p in players:
        slug = p.get("team")
        pool = [e for e in entries if team_ok(slug, e["key"])] if slug else entries
        # porter només amb porter (no confondre Higinio Marín, davanter, amb el porter suplent «Marín»)
        if p.get("P") in ("G", "D", "M", "F"):
            pool = [e for e in pool if "line" not in e or (e["line"] == "G") == (p["P"] == "G")]
        pool = sorted(pool, key=lambda e: not e.get("starter", True))  # a igualtat de nom, primer el titular
        n = best_name(p["name"], [e["name"] for e in pool])
        cand = [e for e in pool if e["name"] == n] if n else []
        if not slug and not (len(cand) == 1 and name_score(p["name"], n) == 100):
            cand = []
        p[field] = cand[0] if cand else None
    return players


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
    names = []
    for url in links[:11]:
        page.goto(url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(2000)
        cols = page.evaluate("""() => { const cs = [...document.querySelectorAll('.column-mobile.x2 > div')];
            const groups = cs.length >= 2 ? cs : [document.body];
            return groups.map(g => [...g.querySelectorAll('a[href*="/segunda/jugador/"]')].map(a => a.innerText.trim()).filter(Boolean)); }""")
        for c in cols[:2]:
            names += [{"name": n, "key": url, "pct": 70, "ps": None} for n in c[:11]]
    log(f"Jornada Perfecta: {len(links)} partits, {len(names)} titulars")
    return names
