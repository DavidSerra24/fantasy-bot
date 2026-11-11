"""Mister: pujes automàtiques al mercat (jugadors lliures, owner 0) pel preu mínim.

Criteris (CLAUDE.md): jugadors amb % de titularitat ≥ mínim de la lliga; primer la franja més alta
(80–90%, després 70%, després 60%) i, dins de cada franja, del més barat al més car. Sense passar del màxim
que permet el Mister (saldo + negatiu permès) ni de les places lliures de la plantilla.
Ús: python -m bot.mistermarket [--dry]
"""
import argparse
import datetime as dt
import re
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright

from bot import si
from bot.mister import U, login, new_context as mister_context
from bot.misterplan import LEAGUES, TACTICS, band, balance, enrich, read_squad, team_slugs
from bot.notify import telegram
from bot.web import load_json, login_futbolfantasy, login_sorareinside, new_context, save_json, save_session
from bot import sources


def si_next(spg, country, league):
    d = _si_next(spg, country, league)
    if league == "Segunda División":  # PS estimat per als que no en tenen (decisió del David, 6/11)
        from bot import psest
        d = psest.fill(d, source="mister", comp="laliga2")
    return d


def _si_next(spg, country, league):
    """SorareInside de la propera jornada que encara no ha començat. Primer el dia del primer partit d'aquella jornada
    (state/mister_kickoffs.json, el desa el planificador); abans es mirava sempre «d'aquí 4 dies», i el dia que
    començava la jornada (dissabte) agafava la de la setmana següent, encara sense onzes ni PS (error del 31/10)."""
    k = load_json("mister_kickoffs.json", {}).get({"Segunda División": "laliga2", "Primera División": "laliga"}.get(league))
    if k:
        K = dt.datetime.fromisoformat(k)
        if K > dt.datetime.now(dt.timezone.utc):
            try:
                d = si.extract_league(spg, country, league, K.astimezone(dt.timezone.utc).date(), log=lambda *_: None)
                if sum(1 for t in d.get("_order", []) if isinstance(d.get(t), list)) >= 4:  # almenys uns quants equips amb onze
                    return d
            except RuntimeError:
                pass
    for days in (4, 5, 6, 3, 7, 2, 1, 0):
        try:
            return si.extract_league(spg, country, league, dt.date.today() + dt.timedelta(days=days), log=lambda *_: None)
        except RuntimeError:
            continue
    raise RuntimeError("SorareInside encara no té la propera jornada")


def read_free_market(pg):
    pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    return pg.evaluate("""() => [...document.querySelectorAll('li[data-owner="0"]')].map(li => ({
        pos: li.dataset.position, price: +li.dataset.price, pid: li.querySelector('[data-id_player]')?.dataset.id_player,
        href: li.querySelector('a.player')?.getAttribute('href'), short: li.querySelector('.name')?.innerText.trim(),
        tid: ((li.querySelector('img.team-logo')?.getAttribute('src') || '').match(/teams[/]([0-9]+)/) || [])[1],
        mine: !!li.querySelector(".btn-bid.btn--accent") }))""")  # botó verd = ja hi tinc una puja


def squad_slots(pg):
    t = pg.inner_text("body")
    m = re.search(r"(\d+)\s*/\s*(\d+)\s*jugador", t, re.I)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def bid(pg, pid, amount=None):
    """Puja pel preu mínim (o `amount`). Primer per l'API; si falla, amb la finestra (pla B). Retorna (ok, màxim permès)."""
    from bot import misterapi
    r = misterapi.use("bid", pid, amount)
    if r:
        return r
    pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    pg.locator(f'li[data-owner="0"] button.btn-bid[data-id_player="{pid}"]').first.click()
    pg.locator("#form-bid").wait_for(timeout=10000)
    mx = pg.evaluate("() => +document.getElementById('input-range')?.max || null")
    if amount:
        amount = int(min(amount, mx or amount))
        pg.evaluate("""(v) => { const r = document.getElementById('input-range'); r.value = v;
            r.dispatchEvent(new Event('input', {bubbles: true})); r.dispatchEvent(new Event('change', {bubbles: true})); }""", amount)
        pg.wait_for_timeout(500)
        got = int(re.sub(r"[^0-9]", "", pg.input_value("#input-tel")) or 0)
        if abs(got - amount) > max(20000, amount * 0.02):
            pg.keyboard.press("Escape")
            raise RuntimeError(f"la puja no ha quedat a {amount} (surt {got})")
    pg.locator("#btn-send").click()
    pg.wait_for_timeout(2500)
    ok = not pg.locator("#form-bid").is_visible()
    if not ok:
        pg.keyboard.press("Escape")
    return ok, mx


def withdraw(pg, pid):
    """Retira una puja meva (la finestra mostra «Eliminar»). Primer per l'API; si falla, amb la finestra."""
    from bot import misterapi
    if misterapi.use("withdraw", pid):
        return True
    pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    pg.locator(f'li[data-owner="0"] button.btn-bid.btn--accent[data-id_player="{pid}"]').first.click()
    pg.locator("#form-bid input[name=action][value=remove]").wait_for(state="attached", timeout=10000)
    pg.locator("#btn-send").click()
    pg.wait_for_timeout(2500)
    ok = not pg.locator("#form-bid").is_visible()
    if not ok:
        pg.keyboard.press("Escape")
    return ok


def shortage(squad):
    """Jugadors que falten per posició per poder fer l'onze amb la tàctica que en necessiti menys ({} si en sobren)."""
    n = {k: sum(1 for p in squad if p["P"] == k) for k in "GDMF"}
    best = None
    for t in TACTICS:
        d, m, f = map(int, t.split("-"))
        miss = {k: max(0, v - n[k]) for k, v in {"G": 1, "D": d, "M": m, "F": f}.items()}
        if best is None or sum(miss.values()) < sum(best.values()):
            best = miss
    return {k: v for k, v in best.items() if v}


def can_sell(keep, rest):
    """Es pot vendre si, sense el jugador, encara surt una formació completa; o si a la plantilla ja li falta algú
    en una altra posició (p. ex. el porter, que arribarà amb una cessió) i el jugador sobra a la seva."""
    if can_field(rest):
        return True
    return sum(shortage(rest).values()) <= sum(shortage(keep).values())


def can_field(squad):
    """Hi ha alguna tàctica del Mister que es pugui completar amb aquesta plantilla?"""
    n = {k: sum(1 for p in squad if p["P"] == k) for k in "GDMF"}
    return n["G"] >= 1 and any(n["D"] >= d and n["M"] >= m and n["F"] >= f
                               for d, m, f in (map(int, t.split("-")) for t in TACTICS))


def sell(pg, pid):
    """Posa el jugador en venda pel preu mínim (el seu valor). Primer per l'API; si falla, amb la finestra."""
    from bot import misterapi
    if misterapi.use("sell", pid):
        return True
    pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    pg.locator(f'button.btn-popup[data-popup="sale"][data-id_player="{pid}"]').first.click()
    pg.locator("form input[name=action][value=sale]").first.wait_for(state="attached", timeout=10000)
    pg.wait_for_timeout(800)
    pg.locator("#btn-send").click()
    pg.wait_for_timeout(2500)
    ok = not pg.locator("#btn-send").is_visible()
    if not ok:
        pg.keyboard.press("Escape")
    return ok


COMP = {"Quique": "laliga2", "Fentaniños": "laliga"}
MADRID = ZoneInfo("Europe/Madrid")


def kickoff(name):
    """Primer partit de la propera jornada (el desa el planificador a partir de Predicted11/FutbolFantasy)."""
    k = load_json("mister_kickoffs.json", {}).get(COMP.get(name))
    t = dt.datetime.fromisoformat(k) if k else None
    return t if t and t > dt.datetime.now(dt.timezone.utc) else None


def next_resolution():
    """Propera resolució del mercat (5:00 hora de Madrid)."""
    now = dt.datetime.now(MADRID)
    t = now.replace(hour=5, minute=0, second=0, microsecond=0)
    return t if t > now else t + dt.timedelta(days=1)


def debt_day(kick):
    """Dia de vendre per saldar el deute: el dia del primer partit (si és a partir de les 17:30, per tenir l'oferta de
    les 17:00) o el dia abans si el primer partit és abans de les 17:30."""
    k = kick.astimezone(MADRID)
    today = dt.datetime.now(MADRID).date()
    late = (k.hour, k.minute) >= (17, 30)
    return (k.date() == today and late) or (k.date() == today + dt.timedelta(days=1) and not late)


def search_ids(pg, q):
    """Buscador de jugadors del Mister: ids dels jugadors que surten per a `q`."""
    pg.goto(U + "/search", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    inp = pg.locator("input.search-players-input:visible").first
    inp.fill(q); inp.dispatch_event("input"); inp.dispatch_event("keyup"); pg.wait_for_timeout(2500)
    return pg.evaluate("""() => [...document.querySelectorAll('a[href^="players/"]')].filter(a => a.offsetParent !== null)
        .map(a => a.getAttribute('href').split('/')[1])""")


def resolve_by_search(pg, players, entries, field, report, ask=True):
    """Jugadors del Mister que no s'han pogut relacionar amb la font però el seu equip hi és: es busquen al buscador
    del Mister els noms de la font d'aquell equip que han quedat sense parella; si el resultat és el mateix jugador,
    s'hi relaciona (i es recorda a state/mister_alias.json). Si no, s'avisa per corregir-ho."""
    alias = load_json("mister_alias.json", {})
    used = {(q[field].get("name"), q[field].get("key")) for q in players if q.get(field)}
    asked = []
    for q in players:
        if q.get(field) or not q.get("team"):
            continue
        pool = [e for e in entries if sources.team_ok(q["team"], e["key"]) and (e["name"], e["key"]) not in used]
        if not pool:
            continue  # la font no té l'equip
        hit = next((e for e in pool if e["name"] == alias.get(str(q["pid"]))), None)
        # primer els de la font amb el mateix cognom (Kike Ribes = Quique Ribes): només se'n proven 5 al buscador
        _ln = lambda x: (list(sources.norm(x)) or [""])[-1]
        pool.sort(key=lambda e: (e["name"] != q.get("doubt"), _ln(e["name"]) != _ln(q.get("name") or q.get("short") or "")))
        tried = 0
        for e in ([] if hit else pool):
            if tried >= 5:
                break
            tried += 1
            try:
                same = _ln(e["name"]) == _ln(q.get("name") or q.get("short") or "")
                # «Quique Ribes» no surt al buscador si el Mister li diu «Kike Ribes»: amb el mateix cognom, també pel cognom sol
                if str(q["pid"]) in search_ids(pg, e["name"])[:6] or (same and str(q["pid"]) in search_ids(pg, e["name"].split()[-1])[:10]):
                    hit = e
                    break
            except Exception:
                break
        if hit:
            q[field] = hit; used.add((hit["name"], hit["key"])); alias[str(q["pid"])] = hit["name"]; q.pop("doubt", None)
        elif ask and q.get("in_squad"):
            asked.append(f"{q['short']} ({q['team']})" + (f": és «{q['doubt']}»? → /mister {q['name']} = {q['doubt']}" if q.get("doubt") else ""))
    save_json("mister_alias.json", alias)
    doubt = [a for a in asked if "/mister" in a]
    absent = [a for a in asked if "/mister" not in a]
    if doubt:  # nom semblant: es pregunta (sense % fins que el David respongui)
        report.append("❓ Noms dubtosos (sense % fins que em responguis «/mister Nom Mister = Nom font» o «= no»): " + "; ".join(doubt))
    if absent:  # cap nom semblant a la font: no són a l'onze previst ni als suplents (4/11: Ramón Martínez i Tomeo)
        report.append("ℹ️ No surten a l'onze previst ni entre els suplents de la font (compten com a 0%): " + ", ".join(absent)
                      + ". Si creus que hi són amb un altre nom, digues-m'ho.")


def ff_profile_pct(fpage, href):
    """% de «Titular J<n>» de la fitxa del jugador a futbolfantasy.com (slug del Mister: players/<id>/<slug>), o None."""
    import re
    slug = (href or "").rstrip("/").split("/")[-1]
    if not fpage or not slug:
        return None
    try:
        fpage.goto(f"https://www.futbolfantasy.com/jugadores/{slug}/laliga-26-27", wait_until="domcontentloaded", timeout=45000)
        fpage.wait_for_timeout(2000)
        m = re.search(r"Titular J\d+\s*(\d{1,3})\s?%", re.sub(r"\s+", " ", fpage.inner_text("body")))
        return int(m.group(1)) if m else None
    except Exception as e:
        print(f"::warning title=fitxa FF::{slug}: {str(e)[:150]}")
        return None


def league_data(b, pg, spg, cid, country, league, report, cache):
    """Saldo, plantilla i mercat lliure d'una lliga, amb el % de titularitat de la font que toca."""
    pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    bal = balance(pg) or 0
    try:
        sidata = si_next(spg, country, league)
    except RuntimeError:
        # aturada de seleccions (decisió del David, 10/11): a Fentaniños el % és de FutbolFantasy i el PS de SorareInside;
        # si SorareInside encara no té la propera jornada, es continua sense PS (compres del més barat al més car dins
        # de la franja, vendes i ofertes pel %; l'alineació es refà quan surti el PS). Quique (Segona) segueix igual.
        if league != "Primera División":
            raise
        sidata = {"_order": []}
        if not cache.get("nops:" + league):
            report.append("ℹ️ Fentaniños: SorareInside encara no té la propera jornada → mercat i ofertes només amb el % de FutbolFantasy (sense PS)")
            cache["nops:" + league] = True
    cache["sid:" + league] = sidata
    squad = read_squad(pg)
    have, cap = squad_slots(pg)
    market = [m for m in read_free_market(pg) if m["href"] and m["pid"]]
    team_slugs(pg, squad + market)
    enrich(squad, sidata); enrich(market, sidata)
    for q in squad:
        q["in_squad"] = True
    if league == "Primera División":  # Fentaniños: el % de FutbolFantasy (alineacions probables / Mis equipos)
        if cache.get('ffp') is None:
            fpage = new_context(b, "futbolfantasy").new_page(); login_futbolfantasy(fpage)
            cache['ffp'] = sources.ff_probs(fpage)
            cache['fpage'] = fpage
        sources.assign(squad + market, cache['ffp'], "ff")
        resolve_by_search(pg, squad + [m for m in market if not m.get("ff")][:5], cache['ffp'], "ff", report)
        for q in squad + market:
            q["pct"] = q["ff"]["pct"] if q["ff"] else None
            q["src"] = "FF"
            q["bmode"] = "ff"  # alineació: del 70 al 95% és la mateixa franja (mana el PS)
    else:  # Quique: SorareInside i, si l'equip no hi és, Jornada Perfecta (si surt a l'onze, compta com a titular)
        resolve_by_search(pg, squad + [m for m in market if not m.get("si")][:5], sources.si_entries(sidata), "si", report)
        for q in squad + market:
            if q.get("si") and q["pct"] is None:
                q["pct"], q["ps"], q["src"] = q["si"].get("pct"), q["si"].get("ps"), "SI"
        if any(q["pct"] is None for q in squad + market):
            if cache.get('jp') is None:
                try:
                    cache['jp'] = sources.jp_starters(new_context(b, "jp").new_page())
                except Exception as e:
                    cache['jp'] = []; report.append(f"⚠️ Jornada Perfecta: {type(e).__name__}")
            si_teams = [t for t in sidata.get("_order", []) if isinstance(sidata.get(t), list) and sidata.get(t)]
            # Jornada Perfecta només per als equips que SorareInside no té (si l'equip hi és, mana SorareInside)
            nodata = [q for q in squad + market if q["pct"] is None
                      and not (q.get("team") and any(sources.team_ok(q["team"], t) for t in si_teams))]
            sources.assign(nodata, cache['jp'], "jp")
            for q in nodata:
                if q["jp"]:
                    q["pct"], q["src"] = 70, "JP"
    # Jugadors de la plantilla que no surten a la font (ni titulars ni suplents) però el seu equip sí: compten com a 0%
    # (p. ex. Solozábal a l'Andorra). Si no hi ha dades de l'equip, es queden sense % (no es venen).
    keys = {e["key"] for e in (cache.get("ffp") or [])} if league == "Primera División" else \
           {t for t in sidata.get("_order", []) if isinstance(sidata.get(t), list) and sidata.get(t)}
    def covered(team):
        """La font té dades d'AQUEST equip. A futbolfantasy.com la clau és el partit («22548-osasuna-malaga») i pot tenir
        només els jugadors del rival (7/11: Rosier sortia a 0% perquè del Osasuna–Málaga només hi havia el Málaga):
        cal que hi surti algun jugador de l'equip segons la plantilla de SorareInside."""
        ks = [k for k in keys if sources.team_ok(team, k)]
        if not ks or league != "Primera División":
            return bool(ks)
        from bot.ff import name_score
        mates = [p["name"] for t in sidata.get("_order", []) if sources.team_ok(team, t) and isinstance(sidata.get(t), list)
                 for r in sidata[t] for p in r] + [n for t in sidata.get("_order", []) if sources.team_ok(team, t)
                                                  for n in (sidata.get("_bench", {}).get(t, []) + sidata.get("_dnp", {}).get(t, []))]
        if not mates:
            return True  # sense plantilla per comprovar-ho: com abans
        ents = [e for e in (cache.get("ffp") or []) if e["key"] in ks]
        return any(name_score(m, e["name"]) >= 75 for m in mates for e in ents)
    _cov = {}
    for q in squad + market:
        if q["pct"] is None and not q.get("doubt") and q.get("team"):
            if q["team"] not in _cov:
                _cov[q["team"]] = covered(q["team"])
            if _cov[q["team"]]:
                q["pct"], q["src"], q["absent"] = 0, (q.get("src") or "SI") + " (no hi surt)", True
    # equips que ja han jugat (o juguen ara) aquesta jornada: si la font encara és la de la jornada en joc, els que no hi
    # surten no són «0%» sinó suplents d'aquell partit (7/11: Quagliata, Amatucci i Soriano a Fentaniños mentre jugava el Deportivo: futbolfantasy.com encara no tenia l'alineació següent).
    # Queden sense % (no es venen ni es compren per això) fins que la font tingui la jornada següent.
    if True:  # Quique (SorareInside) i Fentaniños (FutbolFantasy): totes dues fonts mostren el partit en joc
        if cache.get("started") is None:
            try:
                from bot import fotmob
                cache["started"] = fotmob.started()
            except Exception as e:
                cache["started"] = set(); print(f"::warning title=partits començats::{str(e)[:150]}")
        gone = []
        for q in squad + market:
            if q.get("absent") and any(q.get("team") and sources.team_ok(q["team"], n) for n in cache["started"]):
                q["pct"], q["src"], q["absent"] = None, "partit ja començat", False
                if q.get("in_squad"):
                    gone.append(q["short"])
        if gone:
            report.append("🕒 Partit ja començat o jugat (" + ", ".join(gone) + "): la font encara és la d'aquesta jornada; queden sense % fins a la següent (no es venen per això).")
    # l'avís «no surten a la font» només amb els que de debò compten com a 0% (no els de partits començats ni els
    # d'equips dels quals la font no té jugadors)
    really = {q["short"] for q in squad if q.get("absent")}
    for i, l in enumerate(report):
        if l.startswith("ℹ️ No surten a l'onze previst"):
            keep = [x for x in l.split(": ", 1)[1].split(". Si creus")[0].split(", ") if x.split(" (")[0] in really]
            report[i] = ("ℹ️ No surten a l'onze previst ni entre els suplents de la font (compten com a 0%): " + ", ".join(keep)
                         + ". Si creus que hi són amb un altre nom, digues-m'ho.") if keep else ""
    report[:] = [l for l in report if l]
    # partits aplaçats (4/11: Tenerife i Andorra): els jugadors d'aquells equips i dels seus rivals queden sense %
    # (no es venen ni es compren per això, i a l'alineació van al final perquè no jugaran)
    if cache.get("pp") is None:
        try:
            from bot import fotmob
            cache["pp"] = fotmob.postponed()
        except Exception as e:
            cache["pp"] = set(); print(f"::warning title=aplaçats::{str(e)[:150]}")
    if cache["pp"]:
        hit = set()
        for q in squad + market:
            t = next((n for n in cache["pp"] if q.get("team") and sources.team_ok(q["team"], n)), None)
            if t:
                q["pct"], q["src"], q["postponed"] = None, f"aplaçat ({t})", True
                hit.add(t)
        if hit:
            report.append("⏸️ Partits aplaçats (" + ", ".join(sorted(hit)) + "): els seus jugadors queden sense %, no es venen ni es compren i a l'alineació van al final.")
    return bal, squad, market, have, cap


def run(dry=False, retira=(), force=()):
    report = []
    done = load_json("mister_bids.json", {})
    sold = load_json("mister_sales.json", {})
    cache = {}
    fent_squad = None
    with sync_playwright() as p:
        b = p.chromium.launch()
        sctx = new_context(b, "sorareinside"); spg = sctx.new_page(); login_sorareinside(spg); save_session(sctx, "sorareinside")
        pg = mister_context(b).new_page()
        login(pg)
        for name, cid, (country, league), minimum in LEAGUES:
            try:
                bal, squad, market, have, cap = league_data(b, pg, spg, cid, country, league, report, cache)
                if league == "Primera División":
                    fent_squad = squad
                # Jugadors en venda que han tornat a arribar al mínim: es treuen de la venda (també a la revisió de les 4:15,
                # abans de les ofertes de les 5:00). Les vendes per saldar el deute es mantenen.
                back = []
                for q in [q for q in squad if q["onsale"] and q["pct"] is not None and q["pct"] >= minimum
                          and f"{cid}:{q['pid']}" not in load_json("mister_debt_sales.json", {})]:
                    if dry:
                        back.append(q["short"]); continue
                    try:
                        from bot import misterapi
                        from bot.misteroffers import REMOVE, click_text, open_sale
                        ok = misterapi.use("unsell", q["pid"])
                        if not ok:
                            open_sale(pg, q["pid"])
                            ok = click_text(pg, REMOVE) == 1
                        if ok:
                            back.append(q["short"]); q["onsale"] = False
                            sold.pop(f"{cid}:{q['pid']}", None)
                    except Exception as e:
                        report.append(f"⚠️ {name}: no he pogut treure {q['short']} de la venda ({type(e).__name__})")
                # Vendes: per sota del mínim de titularitat, sense deixar la plantilla sense onze possible
                keep = [q for q in squad if not q["onsale"] and f"{cid}:{q['pid']}" not in sold]
                sales, nosale = [], []
                below = [q for q in keep if q["pct"] is not None and q["pct"] < minimum and not q["loaned"] and not q.get("loanin")]
                # Salvaguarda (2/11): si de cop surten molts jugadors per sota del mínim (p. ex. 4 o més, o més d'un terç
                # de la plantilla), segurament la font està malament (jornada acabada, dades encara no publicades):
                # no es ven ningú i s'avisa el David.
                if len(below) >= 4 or len(below) * 3 > len(keep):
                    report.append(f"⚠️ {name}: {len(below)} jugadors surten per sota del {minimum}% ({', '.join(q['short'] + ' ' + str(q['pct']) + '%' for q in below[:8])}); "
                                  "sembla un error de la font i NO en venc cap. Si de debò cal vendre'n, digues-m'ho.")
                    below = []
                # vendes que el David demana a mà (--ven=Nom,Nom; 9/11): sí o sí, encara que salti la salvaguarda
                below += [q for q in keep if q["short"].replace(" ", "") in force and q not in below and not q["loaned"] and not q.get("loanin")]
                for q in sorted(below, key=lambda q: (q["pct"] if q["pct"] is not None else 0, q["ps"] or 0)):
                    # Fentaniños: abans de vendre, segona comprovació a la fitxa del jugador de futbolfantasy.com
                    # («Titular J13 70%»; 11/11: Sergio Gómez es va vendre amb un 0% mal llegit)
                    if league == "Primera División" and q["short"].replace(" ", "") not in force:
                        fp = ff_profile_pct(cache.get("fpage"), q.get("href"))
                        if fp is not None and fp >= minimum:
                            nosale.append(f"{q['short']} (la fitxa de futbolfantasy.com diu {fp}%; no el venc)")
                            continue
                    rest = [x for x in keep if x is not q]
                    if not can_sell(keep, rest):
                        nosale.append(f"{q['short']} (cal per fer l'onze)")
                        continue
                    if dry or sell(pg, q["pid"]):
                        sales.append(q); keep = rest
                        if not dry:
                            sold[f"{cid}:{q['pid']}"] = dt.date.today().isoformat()
                    else:
                        nosale.append(f"{q['short']} (error en posar-lo a la venda)")
                # Dia de la jornada: el saldo no pot ser negatiu quan comença (0 punts). Les pujes es resolen a les 5:00;
                # si la propera resolució és abans del primer partit, les pujes pendents també compten.
                kick = kickoff(name)
                early = bool(kick and next_resolution() < kick)  # les pujes d'avui es resolen abans de començar
                onsale_val = sum(q["value"] for q in squad if q["onsale"]) + sum(q["value"] for q in sales)
                bids_val = sum(m["price"] for m in market if m["mine"])
                projected = bal + onsale_val - (bids_val if early else 0)
                debt = []
                if kick and debt_day(kick) and projected < 0:
                    order = sorted([q for q in keep if not q["loaned"] and not q.get("loanin")], key=lambda q: (q["ps"] or 0, q["pct"] or 0))
                    extra = 0
                    for q in order:
                        if projected >= 0:
                            if extra:
                                break
                            extra = 1  # un jugador de marge
                        rest = [x for x in keep if x is not q]
                        if not can_sell(keep, rest):
                            continue
                        if dry or sell(pg, q["pid"]):
                            debt.append(q); keep = rest; projected += q["value"]
                            if not dry:
                                sold[f"{cid}:{q['pid']}"] = dt.date.today().isoformat()
                                dsold = load_json("mister_debt_sales.json", {})
                                dsold[f"{cid}:{q['pid']}"] = dt.date.today().isoformat()
                                save_json("mister_debt_sales.json", dsold)
                free = (cap - have) if have is not None else 3
                # Pujes que el bot ja havia fet: si el jugador ja no compleix el mínim (o el bot l'havia confós), es retiren
                gone, kept = [], []
                for m in [m for m in market if m["mine"] and (f"{cid}:{m['pid']}" in done or m["short"].replace(" ", "") in retira)]:
                    src = m.get("si") or m.get("ff") or m.get("jp") or {}
                    if m["pct"] is not None and m["pct"] >= minimum and m["short"].replace(" ", "") not in retira:
                        kept.append(f"{m['short']} = {src.get('name')} ({str(src.get('key', '')).split('/')[-1][:25]}, {m['pct']}%)")
                    else:
                        if dry:
                            gone.append(m["short"])
                        elif withdraw(pg, m["pid"]):
                            gone.append(m["short"]); done.pop(f"{cid}:{m['pid']}", None)
                # Si amb la plantilla (sense els que estan en venda) i les pujes pendents no surt l'onze, es puja per jugadors
                # de les posicions que falten (primer que la resta), però també amb el mínim de % i pel preu mínim:
                # els que falten el David els aconsegueix amb cessions el divendres al matí.
                urgent_done = load_json("mister_urgent.json", {})
                team = keep + [m for m in market if m["mine"]]
                short = shortage(team)
                urgent, uplaced = [], []
                for P, k in short.items():
                    pool = sorted([m for m in market if m["P"] == P and not m["mine"] and m["pct"] is not None and m["pct"] >= minimum],
                                  key=lambda m: (band(m["pct"]), -(m["pct"] or 0), m["price"]))
                    urgent += pool[:k]
                ulimit = max(0, projected) if early else None
                for m in urgent:
                    amount = None  # sempre el preu mínim
                    if early:
                        if m["price"] > ulimit:
                            uplaced.append(f"{m['short']} (sense diners)"); continue
                        ulimit -= m["price"]
                    if dry:
                        uplaced.append(f"{m['short']} ({m['P']}, {m['pct'] if m['pct'] is not None else '?'}%, {(amount or m['price'])/1e6:.2f}M)")
                        continue
                    try:
                        pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
                        ok, mx = bid(pg, m["pid"], amount)
                    except Exception as e:
                        ok = False; uplaced.append(f"{m['short']} (error: {str(e)[:60]})"); continue
                    if ok:
                        m["mine"] = True
                        uplaced.append(f"{m['short']} ({m['P']}, {m['pct'] if m['pct'] is not None else '?'}%, {(amount or m['price'])/1e6:.2f}M)")
                        done[f"{cid}:{m['pid']}"] = dt.date.today().isoformat()
                        urgent_done[f"{cid}:{m['pid']}"] = dt.date.today().isoformat()
                if not dry:
                    save_json("mister_urgent.json", {k: v for k, v in urgent_done.items() if v >= (dt.date.today() - dt.timedelta(days=3)).isoformat()})
                if early and not dry:
                    projected -= sum(m["price"] for m in urgent if m["mine"])
                cands = sorted([m for m in market if m["pct"] is not None and m["pct"] >= minimum and not m["mine"]
                                and f"{cid}:{m['pid']}" not in done], key=lambda m: (band(m["pct"]), m["price"]))
                placed, skipped, limit, spent = [], [], None, 0
                if early:
                    limit = max(0, projected)  # aquestes pujes es resolen abans del primer partit: sense deute
                for m in cands:
                    if len(placed) >= free:
                        skipped.append(f"{m['short']} (plantilla plena)")
                        continue
                    if limit is not None and spent + m["price"] > limit:
                        skipped.append(f"{m['short']} (sense diners)")
                        continue
                    if dry:
                        placed.append(m); spent += m["price"]
                        continue
                    pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
                    ok, mx = bid(pg, m["pid"])
                    if mx:
                        limit = mx if limit is None else min(limit, mx)
                    if ok:
                        placed.append(m); spent += m["price"]
                        done[f"{cid}:{m['pid']}"] = dt.date.today().isoformat()
                    else:
                        skipped.append(f"{m['short']} (error en pujar)")
                line = f"🧢 {name} (saldo {bal/1e6:.1f}M, plantilla {have}/{cap}): "
                line += ("pujaria per " if dry else "pujes: ") + (", ".join(f"{m['short']} ({m['P']}, {m['pct']}%{' JP' if m.get('src') == 'JP' else ''}, {m['price']/1e6:.2f}M)" for m in placed) or "cap")
                if short:
                    line += " | ⚠️ falten per fer l'onze: " + ", ".join(f"{k} {v}" for k, v in short.items()) + " → " + ("pujaria per " if dry else "pujes urgents: ") + (", ".join(uplaced) or "cap amb el % mínim; caldrà una cessió")
                if skipped:
                    line += " | no: " + ", ".join(skipped[:6])
                if back:
                    line += " | ↩️ tornen a arribar al mínim, " + ("els trauria" if dry else "trets") + " de la venda: " + ", ".join(back)
                if kept:
                    line += " | pujes que mantinc: " + ", ".join(kept)
                if gone:
                    line += " | " + ("retiraria" if dry else "pujes retirades") + ": " + ", ".join(gone)
                line += " | " + ("vendria: " if dry else "en venda: ") + (", ".join(f"{q['short']} ({q['pct']}%)" for q in sales) or "cap")
                if nosale:
                    line += " | no venc: " + ", ".join(nosale)
                if debt:
                    line += " | " + ("per saldar el deute vendria: " if dry else "en venda per saldar el deute: ") + ", ".join(f"{q['short']} ({q['value']/1e6:.2f}M)" for q in debt)
                if kick and debt_day(kick):
                    line += f" | saldo previst en començar: {projected/1e6:.1f}M"
                report.append(line)
            except Exception as e:
                report.append(f"❌ Mister · {name}: {type(e).__name__}: {str(e)[:200]}")
        if fent_squad:  # "Mis equipos" de FutbolFantasy = plantilla de Fentaniños
            try:
                from bot import misterff
                report.append(misterff.sync(b, fent_squad, dry))
            except Exception as e:
                report.append(f"❌ Mis equipos: {type(e).__name__}: {str(e)[:200]}")
        save_json("mister_sales.json", {k: v for k, v in sold.items() if v >= (dt.date.today() - dt.timedelta(days=2)).isoformat()})
        save_json("mister_bids.json", {k: v for k, v in done.items() if v >= (dt.date.today() - dt.timedelta(days=3)).isoformat()})
        b.close()
    msg = "Mister · mercat" + (" (prova, sense pujar)" if dry else "") + "\n" + "\n".join(report)
    print(msg)
    for l in report:
        print("::notice title=mister::" + l)
    telegram(msg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--retira", default="", help="pujes meves a retirar sí o sí (noms curts separats per comes)")
    ap.add_argument("--ven", default="", help="jugadors a posar en venda sí o sí (noms curts separats per comes)")
    a = ap.parse_args()
    run(a.dry, tuple(x.replace(" ", "") for x in a.retira.split(",") if x.strip()),
        tuple(x.replace(" ", "") for x in a.ven.split(",") if x.strip()))
