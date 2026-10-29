"""Prova (només lectura) de l'API del Mister: entrada, saldo i finestres de puja i venda (sense enviar res)."""
import json
import re
import time

from bot.misterapi import MisterAPI

t0 = time.time()
LOG = []
try:
    api = MisterAPI().login()
    LOG.append(f"entrada OK en {time.time() - t0:.1f}s · X-Auth {'sí' if api.auth else 'no'}")
    for cid, name in ((2499621, "Quique"), (2519290, "Fentaniños")):
        api.community(cid)
        LOG.append(f"{name}: saldo {api.balance()}")
        team = api.page("/team")
        market = api.page("/market")
        sq = re.findall(r'href="players/(\d+)/', team)
        mk = re.findall(r'<li[^>]*data-position[^>]*>', market)
        LOG.append(f"{name}: /team {len(team)} B, jugadors {len(set(sq))}; /market {len(market)} B, files {len(mk)}: {mk[:2]}")
        free = re.search(r'<li[^>]*data-owner="0"[^>]*data-id_player="(\d+)"|<li[^>]*data-id_player="(\d+)"[^>]*data-owner="0"', market)
        bid_pid = (free.group(1) or free.group(2)) if free else None
        if not bid_pid:
            m = re.search(r'btn-bid[^>]*data-id_player="(\d+)"|data-id_player="(\d+)"[^>]*class="[^"]*btn-bid', market)
            bid_pid = (m.group(1) or m.group(2)) if m else None
        if bid_pid:
            p = api.popup(bid_pid, "bid")
            act, fields = api.form_of(p)
            LOG.append(f"{name}: finestra de puja ({bid_pid}): acció={act} camps={fields} · {json.dumps(p)[:900]}")
        if sq:
            p = api.popup(sq[0], "sale")
            act, fields = api.form_of(p)
            LOG.append(f"{name}: finestra de venda ({sq[0]}): acció={act} camps={fields} · {json.dumps(p)[:900]}")
        LOG.append(f"{name}: botons d'ofertes/alineació a /team: " + " | ".join(sorted(set(re.findall(r'data-popup="([^"]+)"', team + market))))[:800])
    LOG.append(f"total {time.time() - t0:.1f}s")
except Exception:
    import traceback
    LOG.append("ERR " + traceback.format_exc()[-1500:])
txt = "\n".join(LOG)
for i in range(0, min(len(txt), 9 * 7000), 7000):
    print(f"::notice title=api{i // 7000}::" + txt[i:i + 7000].replace("\n", " ¶ "))
