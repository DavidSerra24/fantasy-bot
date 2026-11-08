"""Diagnosi (només lectura): jornada en joc d'una lliga del Mister: onze actual amb punts, candidats de cada casella
(sw/substitution, sense canviar res) i % / PS de SorareInside d'avui per als jugadors de la plantilla.
Ús: python -m bot.misterlive [Quique|Fentaniños]
"""
import datetime as dt
import json
import re
import sys

from playwright.sync_api import sync_playwright

from bot import misterapi, si
from bot.consulta import find
from bot.mister import U, login, new_context as mister_context
from bot.web import login_sorareinside, new_context, save_session

CID = {"Quique": (2499621, ("Spain", "Segunda División")), "Fentaniños": (2519290, ("Spain", "Primera División"))}
name = sys.argv[1] if len(sys.argv) > 1 else "Quique"
cid, (country, league) = CID[name]
out = []
with sync_playwright() as p:
    b = p.chromium.launch()
    sctx = new_context(b, "sorareinside"); spg = sctx.new_page(); login_sorareinside(spg); save_session(sctx, "sorareinside")
    data = si.extract_league(spg, country, league, dt.date.today())
    pg = mister_context(b).new_page()
    login(pg)
    pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
    pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(3500)
    navs = pg.evaluate("() => [...document.querySelectorAll('a.nav__item.gameweek')].map(a => [a.getAttribute('href'), a.innerText.replace(/\\s+/g,' ')])")
    out.append("jornades: " + json.dumps(navs, ensure_ascii=False)[:600])
    xi = pg.evaluate("""() => [...document.querySelectorAll('.lineup-starting button.lineup-player')].map(b => ({
        slot: b.dataset.slot, pos: b.dataset.position, pid: b.dataset.id_player, gwid: b.dataset.gwid, txt: b.innerText.replace(/\\s+/g,' ')}))""")
    out.append("onze: " + " | ".join(f"{x['slot']}/{x['pos']} {x['pid']} {x['txt']}" for x in xi))
    rows = pg.evaluate("""() => [...document.querySelectorAll('.player-row')].map(r => r.innerText.replace(/\\s+/g,' ').slice(0,160))""")
    out.append("plantilla: " + " ¶ ".join(rows))
    api = misterapi.API
    if api and xi:
        api.community(cid)
        html = api.page("/team")
        uc = re.search(r'"id_uc"\s*:\s*"?(\d+)', html)
        gwid = next((x["gwid"] for x in xi if x.get("gwid")), None)
        st = {"slots": [{"slot": x["slot"], "pos": x["pos"], "pid": x["pid"]} for x in xi], "gwid": gwid}
        for x in xi:
            try:
                info = api.slot_info(st, x["slot"])
                lst = info.get("list") or {}
                out.append(f"casella {x['slot']} ({x['txt'][:40]}): isStarted={info.get('isStarted')} candidats: "
                           + json.dumps(lst, ensure_ascii=False)[:700])
            except Exception as e:
                out.append(f"casella {x['slot']}: {e}")
    names = [re.sub(r"^\S*\s*", "", r)[:40] for r in rows]
    b.close()
out.append(f"SorareInside {data.get('_gw')}")
for r in rows:
    nm = " ".join(w for w in r.split() if not re.fullmatch(r"[-\d.,%€+]+|[A-Z]{2,3}", w))[:40]
    f = find(data, nm)
    out.append(f"{nm} → " + (f"{f['name']} ({f['team']}) {f['pct']}% PS {f['ps']}" if f else "—"))
for l in out:
    print("::notice title=live::" + l[:3000])
