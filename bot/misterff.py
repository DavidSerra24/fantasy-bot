"""Sincronitza "Mis equipos" de FutbolFantasy (/seguimiento/laliga/1) amb la plantilla de Fentaniños al Mister.

- Jugadors del Mister que no hi són → s'afegeixen (buscador «Titular +», només si el nom és clar i únic).
- Jugadors de la llista que ja no són al Mister → es treuen.
Ús: python -m bot.misterff [--dry]
"""
import argparse

from playwright.sync_api import sync_playwright

from bot.ff import name_score, plain
from bot.web import login_futbolfantasy, new_context

URL = "https://www.futbolfantasy.com/seguimiento/laliga/1"

LIST = """() => { const seen = {}; return [...document.querySelectorAll('a.juggador')].sort((a, b) => (b.offsetParent !== null) - (a.offsetParent !== null)).map(a => ({
    n: (a.innerText.trim().split(/\\n|\\s{2,}|🕘/)[0] || '').trim(), id: ((a.getAttribute('onclick') || '').match(/jugador_seleccionado = (\\d+)/) || [])[1] }))
    .filter(x => x.id && !seen[x.id] && (seen[x.id] = 1)); }"""


def ff_list(pg):
    pg.goto(URL, wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
    return pg.evaluate(LIST)


def search(pg, q):
    pg.evaluate("""() => [...document.querySelectorAll('a.select-option-link')].find(a => a.offsetParent !== null && /Titular/.test(a.innerText)).click()""")
    pg.locator("#seleccionar-respuesta-input").wait_for(state="visible", timeout=10000)
    pg.wait_for_timeout(500)
    inp = pg.locator("#seleccionar-respuesta-input")
    inp.fill(q); inp.dispatch_event("keyup"); pg.wait_for_timeout(2500)
    return pg.evaluate("""() => [...document.querySelectorAll('#buscador-selector a.ls-follow')].filter(a => a.offsetParent !== null)
        .map(a => ({ n: a.innerText.trim(), id: a.dataset.jugador }))""")


def close(pg):
    pg.keyboard.press("Escape"); pg.wait_for_timeout(800)


def matches(full, short):
    """El nom curt de la llista (p. ex. «Mario», «Jon Martín») és el jugador del Mister (nom complet)?"""
    f, s = plain(full).lower().split(), plain(short).lower().split()
    if not s:
        return False
    return name_score(full, short) >= 60 or (len(s) == 1 and s[0] in f) or all(w in f for w in s)


def sync(b, squad, dry=False):
    """squad: jugadors del Mister amb 'name' (nom complet) i 'short'. Retorna una línia de resum."""
    pg = new_context(b, "futbolfantasy").new_page()
    login_futbolfantasy(pg)
    cur = ff_list(pg)
    have = {}  # id FF → jugador del Mister
    missing = []
    for q in squad:
        hit = [x for x in cur if x["id"] not in have and matches(q["name"], x["n"])]
        if len(hit) == 1:
            have[hit[0]["id"]] = q
        else:
            missing.append(q)
    added, notfound = [], []
    for q in missing:
        res, used = [], None
        for term in dict.fromkeys([plain(q["name"]), plain(q["name"]).split()[-1]]):
            res = [r for r in search(pg, term) if name_score(q["name"], r["n"]) >= 60]
            close(pg)
            if res:
                used = term
                break
        if len(res) != 1:
            notfound.append(f"{q['short']} ({len(res)} resultats)")
            continue
        if not dry:
            search(pg, used)
            pg.locator(f'#buscador-selector a.ls-follow[data-jugador="{res[0]["id"]}"]').first.click()
            pg.wait_for_timeout(2500)
            close(pg)
        added.append(res[0]["n"])
    gone = [x for x in cur if x["id"] not in have]
    removed = []
    for x in gone:
        if not dry:
            pg.goto(URL, wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
            pg.evaluate("(id) => { $('.once-actions .ls-unfollow').attr('data-jugador', id); $('.once-actions .ls-unfollow').click(); }", x["id"])
            pg.wait_for_timeout(2500)
        removed.append(x["n"])
    if not dry and (added or removed):  # comprovació
        now = {x["id"] for x in ff_list(pg)}
        bad = [x["n"] for x in gone if x["id"] in now]
        if bad:
            removed = [n for n in removed if n not in bad]
            notfound += [f"{n} (no s'ha pogut treure)" for n in bad]
    pg.close()
    line = "📋 Mis equipos: " + ("afegiria " if dry else "afegits ") + (", ".join(added) or "cap")
    line += " | " + ("trauria " if dry else "trets ") + (", ".join(removed) or "cap")
    if notfound:
        line += " | ⚠️ no trobats: " + ", ".join(notfound)
    return line


if __name__ == "__main__":
    from bot.mister import U, login, new_context as mister_context
    from bot.misterplan import full_name, read_squad
    from bot.notify import telegram
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    dry = ap.parse_args().dry
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = mister_context(b).new_page()
        login(pg)
        pg.goto(f"{U}/action/change?id_community=2519290", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
        squad = read_squad(pg)
        for q in squad:
            q["name"] = full_name(q["href"])
        print("::notice title=squad::" + ", ".join(f"{q['href']}={q['name']}{' (cedit)' if q.get('loaned') else ''}" for q in squad))
        line = sync(b, squad, dry)
        b.close()
    print("::notice title=misterff::" + line)
    telegram("Fentaniños · " + line + (" (prova)" if dry else ""))
