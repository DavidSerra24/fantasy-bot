"""Predicted11: omple els onzes d'una competició a partir de SorareInside.

Ús:  python -m bot.p11 laliga premier-league ...   [--force] [--max-hours 30]
Només actua si la competició és oberta i tanca d'aquí a menys de --max-hours hores.
"""
import argparse
import hashlib
import datetime as dt
import json
import re
import unicodedata

from playwright.sync_api import sync_playwright

from bot import si
from bot.notify import telegram
from bot.web import (ROOT, inject, load_json, login_predicted11, login_sorareinside,
                     new_context, save_json, save_session)

CFG = json.loads((ROOT / "config" / "predicted11.json").read_text(encoding="utf-8"))
BASE = "https://www.predicted11.com/es/"


def norm(s):
    s = unicodedata.normalize("NFD", s.translate(str.maketrans({"ø": "o", "Ø": "O", "æ": "ae", "ß": "ss", "ł": "l", "đ": "d", "ı": "i"}))).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def league_info(page, comp):
    page.goto(BASE + comp, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    txt = page.inner_text("main")
    hours = None
    end = page.evaluate("() => document.querySelector('[data-countdown-end]')?.dataset.countdownEnd || null")
    if end:
        d = dt.datetime.fromisoformat(end[:19]).replace(tzinfo=dt.timezone.utc)
        hours = (d - dt.datetime.now(dt.timezone.utc)).total_seconds() / 3600
    dates = re.findall(r"\n(\d{2})/(\d{2})\n\d{2}:\d{2}", txt)
    links = page.evaluate("(c) => [...new Set([...document.querySelectorAll('a[href*=\"/'+c+'/equipo/\"]')].map(a => a.getAttribute('href').split('/equipo/')[1]))]", comp)
    first = None
    if dates:
        today = dt.date.today()
        d, mth = map(int, dates[0])
        first = dt.date(today.year + (1 if mth < today.month - 6 else 0), mth, d)
    return {"hours": hours, "first": first, "slugs": links}


def build_entries(comp, sidata, slugs):
    teams = CFG["teams"].get(comp, {})
    alias = CFG["alias"]
    out, missing, waiting = {}, [], []
    for t, rows in sidata.items():
        if t.startswith("_"):
            continue
        slug = teams.get(t)
        if not slug:  # coincidència aproximada amb els slugs de Predicted11
            nt = set(norm(t).split()) - {"fc", "cf", "ac", "sc", "afc", "cd", "ud", "rc", "ss", "us", "calcio"}
            best = max(slugs, key=lambda s: len(nt & set(s.split("-"))), default=None)
            slug = best if best and nt & set(best.split("-")) else None
        if not slug:
            missing.append(f"{t} (sense equip a Predicted11)")
            continue
        if not isinstance(rows, list) or len(sum(rows, [])) < 11:
            waiting.append((t, slug, rows if isinstance(rows, list) else []))  # els experts encara no han penjat l'onze
            continue
        out[slug] = {"team": t, "rows": [[{**p, "name": alias.get(p["name"], p["name"]), "row": i} for p in r] for i, r in enumerate(rows)]}
    return out, missing, waiting


POS = {"Portero": 0, "Defensa": 1, "Mediocampista": 2, "Delantero": 3}


def ff_lineup(page, comp, slug, si_rows, alias):
    """Onze probable de l'usuari «FutbolFantasy» a Predicted11 (rànquing de l'equip → api/p11/jornada/.../FutbolFantasy),
    per als equips que SorareInside encara no té complets. Files com les de SorareInside (porter, defenses, migcampistes,
    davanters; d'esquerra a dreta); el PS, el % i els gols surten de SorareInside si el jugador hi és."""
    got, who = [], ["FutbolFantasy"]
    def on_resp(r):
        if "/api/p11/jornada/" in r.url and f"/{who[0]}/" in r.url:
            try:
                got.append(r.json())
            except Exception:
                pass
    page.on("response", on_resp)
    try:
        page.goto(f"{BASE}{comp}/equipo/{slug}", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        # el primer del rànquing general de l'equip («RANKING BODØ/GLIMT», no el destacat ni el de la jornada; decisió
        # del David, 3/11); si no hi és, l'usuari FutbolFantasy
        best = page.evaluate("""() => { for (const a of document.querySelectorAll('a.ranking-link-block')) {
            let x = a; while (x && !/^\\s*RANKING /i.test(x.innerText || '')) x = x.parentElement;
            const h = x ? x.innerText.trim().split('\\n')[0] : '';
            if (/^RANKING /i.test(h) && !/DESTACADO|JORNADA/i.test(h)) return a.dataset.username; } return null; }""")
        who[0] = best or "FutbolFantasy"
        link = page.locator(f'a.ranking-link-block[data-username="{who[0]}"]')
        if not link.count():
            return None
        link.first.click()
        for _ in range(20):
            if got:
                break
            page.wait_for_timeout(500)
    finally:
        page.remove_listener("response", on_resp)
    part = (got[0] if got else {}).get("participacion") or []
    if len(part) != 11:
        return None
    flat_si = [p for r in si_rows or [] for p in r]
    def si_of(name):
        n = norm(name)
        return next((p for p in flat_si if norm(p["name"]) == n), None) or next(
            (p for p in flat_si if norm(p["name"]).split()[-1:] == n.split()[-1:] and len(n) > 3), None)
    groups = [[], [], [], []]  # POR, DEF, MIG, DAV del primer del rànquing
    for q in part:
        x, _, y = (q.get("jugador_posicion") or "50-50").partition("-")
        groups[POS.get(q.get("posicion"), 2)].append((-float(y or 50), float(x or 50), q))
    for g, r in enumerate(groups):
        r.sort(key=lambda t: (t[0], t[1]) if g == 2 else (t[1],))
    # Primer els jugadors que SorareInside sí que té (decisió del David, 3/11); els que falten, del primer del rànquing.
    # Posició dels de SorareInside: la del mateix jugador al rànquing; si no hi és, per la fila (0 porter, 1 defenses,
    # l'última davanters si hi ha 4 files o més, la resta migcampistes).
    rk = {norm(q["nombre"]): g for g, r in enumerate(groups) for _, _, q in r}
    nrows = len(si_rows or [])
    chosen = [[], [], [], []]
    for ri, r in enumerate(si_rows or []):
        for sp in r:
            g = rk.get(norm(sp["name"]))
            if g is None:
                g = 0 if ri == 0 else 1 if ri == 1 else 3 if (ri == nrows - 1 and nrows >= 4) else 2
            chosen[g].append(dict(sp, src="si"))
    n_si = sum(map(len, chosen))
    taken = {norm(p["name"]) for c in chosen for p in c}
    taken_last = {norm(p["name"]).split()[-1] for c in chosen for p in c if p["name"].split()}
    def add(g, q):
        sp = si_of(q["nombre"]) or {}
        chosen[g].append({"name": alias.get(q["nombre"], q["nombre"]), "pct": sp.get("pct"), "ps": sp.get("ps"), "goals": sp.get("goals", 0),
                          "subs": sp.get("subs") or [], "src": "rk"})
        taken.add(norm(q["nombre"]))
    free = lambda q: norm(q["nombre"]) not in taken and norm(q["nombre"]).split()[-1:] != [] and norm(q["nombre"]).split()[-1] not in taken_last
    for g, r in enumerate(groups):  # cada línia fins a la mida que té al rànquing
        for _, _, q in r:
            if sum(map(len, chosen)) < 11 and len(chosen[g]) < len(r) and free(q):
                add(g, q)
    for g, r in enumerate(groups):  # si encara en falten (SorareInside en té de més en alguna línia)
        for _, _, q in r:
            if sum(map(len, chosen)) < 11 and free(q):
                add(g, q)
    if sum(map(len, chosen)) != 11 or len(chosen[0]) != 1:
        return None
    out = [[dict(p, row=i) for p in c] for i, c in enumerate(x for x in chosen if x)]
    return {"team": None, "rows": out, "src": who[0], "n_si": n_si, "updated": (got[0] or {}).get("fecha_actualizacion")}


def fill_team(page, comp, slug, entry, prev):
    page.goto(f"{BASE}{comp}/equipo/{slug}", wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    inject(page, "p11")
    golov = CFG["goleador_override"].get(f"{comp}/{slug}")
    res = page.evaluate("([e,p,g]) => __p11.runTeam(e,p,g)", [entry, prev, golov])
    # Comprovació: recarregar i mirar què s'ha desat.
    page.goto(f"{BASE}{comp}/equipo/{slug}", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    inject(page, "p11")
    st = page.evaluate("() => __p11.state()")
    if st["tactic"] == "Manual":
        page.evaluate("(f) => __p11.fixTactic(f)", res.get("formation"))
        page.goto(f"{BASE}{comp}/equipo/{slug}", wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        inject(page, "p11")
        st = page.evaluate("() => __p11.state()")
    res["check"] = st
    return res


def run(comps, force=False, max_hours=30.0):
    report = []
    # equivalències confirmades pel David per Telegram («/p11 A = B»; «= no» → es posa el suplent)
    _pa = load_json("p11_alias.json", {})
    for k, v in _pa.items():
        CFG["alias"][k] = f"__no__ {k}" if str(v).lower() == "no" else v
    # (6/11) ja NO s'afegeix l'equivalència al revés: convertia noms de Predicted11 correctes («Nico Paz») en els de
    # SorareInside i el jugador quedava sense posar (Como amb 10, Acheampong al Chelsea)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx_p11 = new_context(b, "predicted11")
        pg = ctx_p11.new_page()
        login_predicted11(pg)
        save_session(ctx_p11, "predicted11")
        ctx_si = None
        for comp in comps:
            lg = CFG["leagues"][comp]
            info = league_info(pg, comp)
            if info["hours"] is None or info["hours"] <= 0:
                report.append(f"⏸️ {comp}: tancat o sense jornada oberta")
                continue
            if not force and info["hours"] > max_hours:
                report.append(f"⏳ {comp}: tanca d'aquí a {info['hours']:.0f} h, encara no")
                continue
            if ctx_si is None:
                ctx_si = new_context(b, "sorareinside")
                spg = ctx_si.new_page()
                login_sorareinside(spg)
                save_session(ctx_si, "sorareinside")
            day = info["first"] or dt.date.today()
            sidata = si.extract_league(spg, lg["si"][0], lg["si"][1], day)
            save_json(f"si_{comp}.json", sidata)
            entries, missing, waiting = build_entries(comp, sidata, info["slugs"])
            ffused = []
            # partits aplaçats: no es fan (Predicted11 els tornarà a obrir el dia que es juguin; decisió del David, 4/11)
            try:
                from bot import fotmob
                pp = fotmob.postponed()
            except Exception:
                pp = set()
            skipped_pp = [t for t, _, _ in waiting if any(fotmob.team_score(t, n) > 0 for n in pp)] if pp else []
            waiting = [w for w in waiting if w[0] not in skipped_pp]
            for t, slug, rows in waiting:  # SorareInside incomplet → onze probable de FutbolFantasy (publicat a Predicted11)
                try:
                    e = ff_lineup(pg, comp, slug, rows, CFG["alias"])
                except Exception as ex:
                    e = None
                    print(f"::warning title=p11 ff::{slug}: {type(ex).__name__} {str(ex)[:120]}")
                if e:
                    e["team"] = t
                    entries[slug] = e
                    ffused.append(f"{t} ({e['n_si']} de SorareInside + {11 - e['n_si']} de {e['src']})")
            waiting = [t for t, slug, _ in waiting if slug not in entries]
            prev_all = load_json(f"p11_{comp}.json")
            ok, bad, pending = 0, [], []
            skipped = 0
            for slug, entry in entries.items():
                # Només compten els jugadors i la seva posició a l'onze (no els punts projectats)
                # (i si ja tenen punts projectats, perquè les icones en depenen: abans de tenir-ne no es poden posar bé)
                h = hashlib.md5(json.dumps([[[p["name"], p.get("ps") is not None] for p in r] for r in entry["rows"]], ensure_ascii=False).encode()).hexdigest()
                pv = prev_all.get(slug) or {}
                c0 = pv.get("check") or {}
                if not force and pv.get("hash") == h and c0.get("n") == 11 and c0.get("icons") == 3 and c0.get("tactic") != "Manual":
                    ok += 1
                    skipped += 1
                    continue  # res no ha canviat des de l'última vegada
                try:
                    res = fill_team(pg, comp, slug, entry, prev_all.get(slug))
                    res["hash"] = h
                    prev_all[slug] = res
                    c = res["check"]
                    nops = sum(1 for r in entry["rows"] for p in r if p.get("ps") is None)
                    if c["n"] == 11 and c["icons"] != 3 and c["tactic"] != "Manual" and nops:
                        pending.append(slug)  # onze posat; falten punts projectats per a les icones
                        ok += 1
                    un = re.search(r"UN:([^()]*?)(?: AMB:| SUBSTITUT:| DUBTE:| FORÇAT:| \(|$)", res.get("msg", ""))
                    sub = re.search(r"SUBSTITUT:([^()]*?)(?: AMB:| UN:| DUBTE:| FORÇAT:| \(|$)", res.get("msg", ""))
                    dub = re.search(r"DUBTE:([^()]*?)(?: AMB:| UN:| SUBSTITUT:| FORÇAT:| \(|$)", res.get("msg", ""))
                    forced = re.search(r"FORÇAT:([^()]*?)(?: AMB:| UN:| SUBSTITUT:| DUBTE:| \(|$)", res.get("msg", ""))
                    forced_si = {x.partition("→")[0] for x in (forced.group(1).strip().split("|") if forced else [])}
                    if dub:  # noms semblants no confirmats: no s'han posat (decisió del David, 4/11)
                        for pair in dub.group(1).strip().split("|"):
                            a, _, b_ = pair.partition("=")
                            if a and b_:
                                done_ = "L'he posat igualment perquè no hi havia cap suplent segur (mai deixo l'onze amb menys d'11)" if a in forced_si else "No l'he posat"
                                bad.append(f"{slug}: ❓ «{a}» (SorareInside) és «{b_}» a Predicted11? {done_}. Respon «/p11 {a} = {b_}» si és el mateix (o «= no»)")
                    if sub:  # s'ha posat el suplent, però cal corregir el nom
                        bad.append(f"{slug}: ❓ no trobo a Predicted11 i hi he posat el suplent ({sub.group(1).strip()}) — digues-me com es diu allà i ho corregeixo")
                    if c["n"] != 11:  # (6/11, Como amb 10) que no passi desapercebut
                        bad.append(f"{slug}: 🚨 l'onze ha quedat amb {c['n']} jugadors: revisa'l!")
                    if un:
                        bad.append(f"{slug}: ❓ no trobo a Predicted11: {un.group(1).strip()} — digues-me com es diu allà i ho corregeixo")
                    elif c["n"] != 11 or c["icons"] != 3 or c["tactic"] == "Manual":
                        bad.append(f"{slug}: {c['n']} jug, {c['icons']} icones, {c['tactic']} {res.get('msg','')[:200]}")
                    elif "UN:" in res.get("msg", "") or "AMB:" in res.get("msg", ""):
                        bad.append(f"{slug}: {res['msg'][:200]}")
                    else:
                        ok += 1
                except Exception as e:  # un equip no ha d'aturar la resta
                    bad.append(f"{slug}: error {type(e).__name__} {str(e)[:80]}")
                save_json(f"p11_{comp}.json", prev_all)
            line = f"✅ {comp} ({sidata.get('_gw')}): {ok}/{len(info['slugs'])} equips correctes ({skipped} sense canvis), tanca d'aquí a {info['hours']:.1f} h"
            if waiting:
                line += f"\n  ⏳ onze encara no disponible a SorareInside: {', '.join(waiting)}"
            if skipped_pp:
                line += f"\n  ⏸️ partit aplaçat, no el faig: {', '.join(skipped_pp)}"
            if ffused:
                line += f"\n  📋 sense onze complet a SorareInside, els que falten, del primer del rànquing de l'equip: {', '.join(ffused)}"
            if pending:
                line += f"\n  ⏳ icones pendents (encara sense punts projectats): {', '.join(pending)}"
            if bad or missing:
                line += "\n  ⚠️ " + "\n  ⚠️ ".join(bad + missing)
            report.append(line)
        save_session(ctx_p11, "predicted11")
        b.close()
    msg = "Predicted11\n" + "\n".join(report)
    print(msg)
    for l in report:
        print("::notice title=p11::" + l.replace("\n", " | "))
    telegram(msg)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("comps", nargs="+")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--max-hours", type=float, default=30.0)
    a = ap.parse_args()
    run(a.comps, a.force, a.max_hours)
