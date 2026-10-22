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
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def league_info(page, comp):
    page.goto(BASE + comp, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    txt = page.inner_text("main")
    m = re.search(r"Tiempo restante para pron[oó]sticos.*?\n(.*?)(?:Inicia|Quiniela|Alineaciones)", txt, re.S)
    hours = None
    if m:
        part = m.group(1)
        nums = dict((u.upper()[:3], int(n)) for n, u in re.findall(r"(\d+)\s*\n?\s*(D[IÍ]AS?|HORAS?|MIN)", part, re.I))
        hours = nums.get("DÍA", nums.get("DIA", 0)) * 24 + nums.get("HOR", 0) + nums.get("MIN", 0) / 60
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
    out, missing = {}, []
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
        if not isinstance(rows, list):
            missing.append(f"{t} ({rows})")
            continue
        flat = sum(rows, [])
        if len(flat) < 11:
            missing.append(f"{t} (onze incomplet a SorareInside: {len(flat)})")
            continue
        out[slug] = {"team": t, "rows": [[{**p, "name": alias.get(p["name"], p["name"]), "row": i} for p in r] for i, r in enumerate(rows)]}
    return out, missing


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
            entries, missing = build_entries(comp, sidata, info["slugs"])
            prev_all = load_json(f"p11_{comp}.json")
            ok, bad = 0, []
            skipped = 0
            for slug, entry in entries.items():
                h = hashlib.md5(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
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
                    if c["n"] == 11 and c["icons"] == 3 and c["tactic"] != "Manual":
                        ok += 1
                    else:
                        bad.append(f"{slug}: {c['n']} jug, {c['icons']} icones, {c['tactic']} {res.get('msg','')}")
                    if "UN:" in res.get("msg", "") or "AMB:" in res.get("msg", ""):
                        bad.append(f"{slug}: {res['msg']}")
                except Exception as e:  # un equip no ha d'aturar la resta
                    bad.append(f"{slug}: error {type(e).__name__} {str(e)[:80]}")
                save_json(f"p11_{comp}.json", prev_all)
            line = f"✅ {comp} ({sidata.get('_gw')}): {ok}/{len(info['slugs'])} equips correctes ({skipped} sense canvis), tanca d'aquí a {info['hours']:.1f} h"
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
