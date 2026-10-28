"""Quiniela del Mister (1 X 2), a partir dels resultats de la quiniela de Predicted11 que envia el David.

- LaLiga  → quiniela «Oficial» i la de la «Comunitat» de Fentaniños.
- LaLiga 2 → quiniela de la «Comunitat» de Quique.
Pronòstic: guanya el local → 1, empat → X, guanya el visitant → 2.
Ús: python -m bot.misterpool laliga "Villarreal 2-1 Espanyol; ..." [--dry]
"""
import re
import sys

from playwright.sync_api import sync_playwright

from bot.ff import team_score
from bot.mister import U, login, new_context

POOLS = {"laliga": [(2519290, "pool-public", "Oficial"), (2519290, "pool-private", "Fentaniños")],
         "laliga2": [(2499621, "pool-private", "Quique")]}

ROWS = """() => { const by = {};
  for (const b of document.querySelectorAll('.sw-content button.btn-pools')) (by[b.dataset.id_match] = by[b.dataset.id_match] || []).push(b);
  return Object.entries(by).map(([id, bs]) => { let row = bs[0];
    while (row && row.querySelectorAll('button.btn-pools').length < 3) row = row.parentElement;
    const parts = row.innerText.split('\\n').map(s => s.trim()).filter(s => s && !/^[1X2]$/.test(s) && !/^\\w{2,4}\\.? \\d{1,2}:\\d{2}$/.test(s) && !/^\\d{1,2}:\\d{2}$/.test(s));
    return { id, home: parts[0] || '', away: parts[parts.length - 1] || '', sel: bs.filter(b => /active|accent|selected|primary/.test(b.className)).map(b => b.dataset.prediction),
             cls: bs.map(b => b.className).join(' / '), locked: bs.every(b => b.disabled) }; }); }"""


def sign(a, b):
    return "1" if a > b else "X" if a == b else "2"


def open_pool(pg, cid, sw):
    pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    pg.goto(U + "/feed", wait_until="domcontentloaded"); pg.wait_for_timeout(3000)
    pg.locator("[data-sw='pool-public']").first.evaluate("e => e.click()"); pg.wait_for_timeout(3500)
    if sw == "pool-private":
        pg.locator("button[data-sw='pool-private']").first.evaluate("e => e.click()"); pg.wait_for_timeout(3500)
    return pg.evaluate(ROWS)


def match(rows, home, away):
    best, bs = None, 0
    for r in rows:
        sc = min(team_score(home, r["home"]), team_score(away, r["away"]))
        if sc > bs:
            best, bs = r, sc
    return best if bs > 0 else None


def run(comp, picks, dry=False):
    """picks: [[local, visitant, gols local, gols visitant], ...] (com bot.quiniela.parse). Retorna línies de resum."""
    if comp not in POOLS or not picks:
        return []
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = new_context(b).new_page()
        login(pg)
        for cid, sw, label in POOLS[comp]:
            try:
                rows = open_pool(pg, cid, sw)
                print("::notice title=rows " + label + "::" + str(rows)[:3000])
                print("::notice title=rowhtml " + label + "::" + pg.evaluate("() => { const b=document.querySelector('.sw-content button.btn-pools'); let r=b; for(let i=0;i<4&&r;i++) r=r.parentElement; return r ? r.outerHTML.replace(/<svg.*?<\\/svg>/gs,'').replace(/<img[^>]*>/g,'').replace(/\\s+/g,' ').slice(0,2500) : 'cap'; }"))
                done, miss, locked = [], [], 0
                for h, a, gh, ga in picks:
                    r = match(rows, h, a)
                    if not r:
                        miss.append(f"{h}-{a}"); continue
                    if r["locked"]:
                        locked += 1; continue
                    s_ = sign(gh, ga)
                    if not dry and s_ not in r["sel"]:
                        pg.locator(f'.sw-content button.btn-pools[data-id_match="{r["id"]}"][data-prediction="{s_}"]').first.click()
                        pg.wait_for_timeout(1200)
                    done.append(f"{r['home']}-{r['away']} {s_}")
                if not dry and done:  # comprovació recarregant
                    after = {r["id"]: r["sel"] for r in open_pool(pg, cid, sw)}
                    print("::notice title=pool classes::" + (rows[0]["cls"] if rows else ""))
                line = f"🎲 Quiniela Mister · {label}" + (" (prova)" if dry else "") + f": {len(done)} posats"
                if dry or done:
                    line += " · " + ", ".join(done)
                if locked:
                    line += f" | {locked} ja començats"
                if miss:
                    line += " | ⚠️ no trobats: " + ", ".join(miss)
                if not dry and done:
                    want = {}
                    for h, a, gh, ga in picks:
                        r = match(rows, h, a)
                        if r and not r["locked"]:
                            want[r["id"]] = sign(gh, ga)
                    bad = [i for i, s_ in want.items() if after.get(i) and s_ not in after[i]]
                    if bad:
                        line += f" | ❗ {len(bad)} no s'han desat bé, revisa-ho"
                out.append(line)
            except Exception as e:
                out.append(f"❌ Quiniela Mister · {label}: {type(e).__name__}: {str(e)[:200]}")
        b.close()
    return out


if __name__ == "__main__":
    from bot.quiniela import parse
    from bot.notify import telegram
    args = [x for x in sys.argv[1:] if x != "--dry"]
    lines = run(args[0], parse(args[1] if len(args) > 1 else ""), dry="--dry" in sys.argv)
    for l in lines:
        print("::notice title=pool::" + l)
    if lines:
        telegram("\n".join(lines))
