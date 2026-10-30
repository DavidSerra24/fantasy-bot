"""Consulta (només lectura) per a una clàusula al Mister: jugadors d'una posició que tenen els altres mànagers,
amb el % de titularitat i els punts projectats de SorareInside (o Jornada Perfecta si SI no té l'equip).
No fa cap clàusula: només envia la llista per Telegram.
Ús: python -m bot.misterclause [Quique|Fentaniños] [POR|DEF|MIG|DAV] [mínim %]
"""
import re
import sys

from bot.notify import telegram

LEAGUE = {"Quique": (2499621, "Spain", "Segunda División"), "Fentaniños": (2519290, "Spain", "Primera División")}
LOANDBG = []
POS = {"POR": 1, "DEF": 2, "MIG": 3, "DAV": 4}


def main(league="Quique", pos="POR", minimum=60):
    from playwright.sync_api import sync_playwright
    from bot.ff import name_score, team_score
    from bot.misterapi import MisterAPI
    from bot.mistermarket import si_next
    from bot.sources import si_entries
    from bot.web import login_sorareinside, new_context, save_session
    cid, country, sil = LEAGUE[league]
    api = MisterAPI().login()
    api.community(cid)
    me = None
    html = api.page("/standings")
    users = []
    for m in re.finditer(r'href="(users/(\d+)/[^"]+)"', html):
        if m.group(1) not in [u[0] for u in users]:
            users.append((m.group(1), m.group(2)))
    feed = api.page("/feed")
    mm = re.search(r'"id_uc"\s*:\s*(\d+)', feed) or re.search(r'"id_user"\s*:\s*(\d+)', feed)
    me = mm.group(1) if mm else None
    cands, seen = [], set()
    loan_only = "--cedibles" in sys.argv
    sources = [api.page("/" + path) for path, uid in users]
    loanable = set()
    market = api.page("/market")
    for li in re.findall(r"<li[^>]*data-loanable=\"1\"[^>]*>.*?</li>", market, re.S):
        loanable |= set(re.findall(r'data-id_player="(\d+)"', li)) | set(re.findall(r'players/(\d+)/', li))
    if loan_only:
        sources = sources + [market]
    keys_dbg = None
    for page in sources:
        for pid in dict.fromkeys(re.findall(r'players/(\d+)/', page) + re.findall(r'data-id_player="(\d+)"', page)):
            if pid in seen:
                continue
            seen.add(pid)
            try:
                d = api.ajax("player-community-info", {"id_player": pid, "popup": "bid"}).get("data") or {}
            except Exception:
                continue
            keys_dbg = keys_dbg or sorted(d.keys())
            if d.get("position") != POS[pos]:
                continue
            ln = d.get("loan")
            if pos and d.get("position") == POS[pos] and len(LOANDBG) < 6:
                LOANDBG.append(f"{d.get('name')}: {ln}")
            is_loan = pid in loanable or (isinstance(ln, dict) and any(ln.get(k) for k in ("loanable", "isLoanable", "available", "enabled", "price")))
            if loan_only and not is_loan:
                continue
            owner = d.get("owner") or {}
            if not owner or str(owner.get("id")) == str(me) or owner.get("name") == "David Serra":
                continue
            cands.append({"pid": pid, "name": d.get("name"), "team": (d.get("team") or {}).get("name"), "owner": owner.get("name"),
                          "value": d.get("value"), "clause": (d.get("clause") or {}).get("value"), "shield": (d.get("clause") or {}).get("shield"),
                          "price": (d.get("market") or {}).get("price"), "loan": d.get("loan")})
    bal = api.balance()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = new_context(b, "sorareinside"); spg = ctx.new_page(); login_sorareinside(spg); save_session(ctx, "sorareinside")
        ents = si_entries(si_next(spg, country, sil))
        b.close()
    for c in cands:
        best = None
        for e in ents:
            if team_score(c["team"] or "", e["key"]) <= 0:
                continue
            if pos == "POR" and e.get("line") != "G":
                continue
            sc = name_score(c["name"] or "", e["name"])
            if sc >= 60 and (best is None or (sc, e["starter"]) > (best[0], best[1]["starter"])):
                best = (sc, e)
        e = best[1] if best else {}
        c["pct"], c["ps"], c["si"] = e.get("pct"), e.get("ps"), e.get("name")
    ok = sorted([c for c in cands if (c["pct"] or 0) >= minimum], key=lambda c: (-(c["ps"] or 0), -(c["pct"] or 0)))
    rest = [c for c in cands if (c["pct"] or 0) < minimum]
    lines = [f"🔎 {league} · {pos} {'CEDIBLES ' if loan_only else ''}dels altres mànagers amb ≥{minimum}% (SorareInside), per punts projectats",
             f"Saldo: {bal.get('current', 0) / 1e6:.2f}M (màx. deute {bal.get('maxDebt', 0) / 1e6:.2f}M)"]
    for c in ok:
        lines.append(f"• {c['name']} ({c['team']}) · {c['pct']}% · PS {c['ps'] if c['ps'] is not None else '-'} · "
                     + (f"preu al mercat {(c['price'] or 0) / 1e6:.2f}M · cessió {c['loan']}" if loan_only else f"clàusula {(c['clause'] or 0) / 1e6:.2f}M")
                     + f"{' 🛡️ blindat' if c['shield'] else ''} · de {c['owner']}")
    if not ok:
        lines.append("Cap amb aquest %.")
    if rest:
        lines.append("Per sota del mínim: " + ", ".join(f"{c['name']} ({c['team']}, {c['pct'] if c['pct'] is not None else '?'}%)" for c in rest))
    msg = "\n".join(lines)
    print("::notice title=clausula::" + msg.replace("\n", " ¶ ")[:8000])
    print(f"::notice title=debug::usuaris {len(users)}, jugadors mirats {len(seen)}, candidats {len(cands)}, cedibles al mercat {len(loanable)}, camps {keys_dbg} · loan: {LOANDBG}")
    telegram(msg)


if __name__ == "__main__":
    a = sys.argv[1:]
    a = [x for x in a if not x.startswith("--")]
    main(a[0] if a else "Quique", a[1] if len(a) > 1 else "POR", int(a[2]) if len(a) > 2 else 60)
