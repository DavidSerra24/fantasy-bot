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
    return [{"name": p["name"], "key": p["url"], "pct": p.get("pct") or 0, "ps": None}
            for p in match_pages(page, None) if p.get("name")]


def si_entries(sidata):
    """Entrades {name, key (equip), pct, ps} de SorareInside (titulars i suplents)."""
    out = []
    for t in sidata.get("_order", []):
        rows = sidata.get(t)
        if not isinstance(rows, list):
            continue
        for r in rows:
            for q in r:
                out.append({"name": q.get("name") or "", "key": t, "pct": q.get("pct"), "ps": q.get("ps")})
                for sub in q.get("subs") or []:
                    out.append({"name": sub.get("name") or "", "key": t, "pct": sub.get("pct"), "ps": None})
    return out


def assign(players, entries, field="src"):
    """Relaciona cada jugador del Mister (name, tid = id d'equip del Mister) amb una entrada de la font.
    1) Coincidències de nom exactes i úniques → cada tid "vota" la clau (equip/partit) de la font.
    2) Només s'accepta una coincidència si la clau és la que ha votat el seu equip; si l'equip no té vot,
       només s'accepta un nom exacte i únic. Així no es confon David López (Girona) amb el del Mallorca."""
    from collections import Counter
    votes = {}
    for p in players:
        exact = [e for e in entries if name_score(p["name"], e["name"]) == 100]
        if len({e["key"] for e in exact}) == 1 and p.get("tid"):
            votes.setdefault(p["tid"], Counter())[exact[0]["key"]] += 1
    team_key = {t: c.most_common(1)[0][0] for t, c in votes.items()}
    for p in players:
        key = team_key.get(p.get("tid"))
        pool = [e for e in entries if e["key"] == key] if key else entries
        n = best_name(p["name"], [e["name"] for e in pool])
        cand = [e for e in pool if e["name"] == n] if n else []
        if not key and not (len(cand) == 1 and name_score(p["name"], n) == 100):
            cand = []  # sense equip conegut: només nom exacte i únic
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
