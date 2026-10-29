"""Prova (sense enviar res) de l'API del Mister: entrada ràpida passant la sessió al navegador i dades que enviaria
per pujar, retirar, vendre i treure de la venda."""
import re
import time

from playwright.sync_api import sync_playwright

from bot import misterapi
from bot.mister import U, login, new_context

LOG = []
t0 = time.time()
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    try:
        login(pg)
        api = misterapi.API
        LOG.append(f"entrada en {time.time() - t0:.1f}s · per l'API: {'sí' if api else 'NO (pantalles)'}")
        for cid, name in ((2499621, "Quique"), (2519290, "Fentaniños")):
            pg.goto(f"{U}/action/change?id_community={cid}", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            LOG.append(f"{name}: saldo per l'API {api.balance() if api else '-'}")
            pg.goto(U + "/market", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            free = pg.evaluate("() => [...document.querySelectorAll('li[data-owner=\"0\"] button.btn-bid')].map(b => b.dataset.id_player).slice(0, 1)")
            mine = pg.evaluate("() => [...document.querySelectorAll('li[data-owner=\"0\"] button.btn-bid.btn--accent')].map(b => b.dataset.id_player).slice(0, 1)")
            pg.goto(U + "/team", wait_until="domcontentloaded"); pg.wait_for_timeout(2500)
            sq = pg.evaluate("() => [...document.querySelectorAll('button.btn-popup[data-popup=\"sale\"]')].map(b => b.dataset.id_player).slice(0, 1)")
            if api and free:
                LOG.append(f"{name}: pujaria per {free[0]} amb {api.bid(free[0], dry=True)}")
            if api and mine:
                LOG.append(f"{name}: retiraria la puja de {mine[0]} amb {api.withdraw(mine[0], dry=True)} · puja actual {api._pre(mine[0], 'bid').get('bid')}")
                if name == "Quique":  # prova real sense canviar res: tornar a enviar la mateixa puja (update al mateix import)
                    ok, mx = api.bid(mine[0])
                    LOG.append(f"{name}: prova real (mateixa puja) → {ok}; ara {api._pre(mine[0], 'bid').get('bid')}")
            if api and sq:
                LOG.append(f"{name}: vendria {sq[0]} amb {api.sell(sq[0], dry=True)} · trauria de la venda amb {api.unsell(sq[0], dry=True)}")
        LOG.append(f"total {time.time() - t0:.1f}s")
    except Exception:
        import traceback
        LOG.append("ERR " + traceback.format_exc()[-1500:])
    b.close()
txt = "\n".join(LOG)
print("::notice title=api::" + txt.replace("\n", " ¶ ")[:8000])
