"""Consulta (només lectura): la plantilla d'una lliga del Mister amb % i PS, i l'onze que faria el bot
(també afegint jugadors que el David pensa fitxar). Ús: python -m bot.mistersquad Quique "Nom:POS:%:PS" ...
"""
import sys
import traceback

from playwright.sync_api import sync_playwright

from bot.mister import login, new_context as mister_context
from bot.misterlineup import best_lineup, match_keys
from bot.misterplan import LEAGUES
from bot.mistermarket import league_data
from bot.notify import telegram
from bot.web import login_sorareinside, new_context, save_session

name = sys.argv[1] if len(sys.argv) > 1 else "Quique"
extra = [a for a in sys.argv[2:] if a != "--quiet"]
def main():
  with sync_playwright() as p:
      b = p.chromium.launch()
      sctx = new_context(b, "sorareinside"); spg = sctx.new_page(); login_sorareinside(spg); save_session(sctx, "sorareinside")
      pg = mister_context(b).new_page()
      login(pg)
      rep, cache = [], {}
      for n, cid, (country, league), minimum in LEAGUES:
          if n != name:
              continue
          bal, squad, market, have, cap = league_data(b, pg, spg, cid, country, league, rep, cache)
          match_keys(squad, cache.get("sid:" + league))
          for e in extra:
              nm, P, pct, ps = (e.split(":") + ["", "", "", ""])[:4]
              squad.append({"pid": "new-" + nm, "name": nm, "short": nm + " (nou)", "P": {"POR": "G", "DEF": "D", "MIG": "M", "DAV": "F"}[P],
                            "pct": int(pct) if pct else None, "si": {"ps": int(ps) if ps else None}, "onsale": False, "loaned": False, "team": None})
          o = {"G": 0, "D": 1, "M": 2, "F": 3}
          lines = [f"👥 {name} · plantilla ({len(squad)}) per posició, % i PS:"]
          for q in sorted(squad, key=lambda q: (o[q["P"]], -(q["pct"] or -1), -((q.get("si") or {}).get("ps") or 0))):
              lines.append(f"  {'POR DEF MIG DAV'.split()[o[q['P']]]} {q['short']} · {q['pct'] if q['pct'] is not None else '?'}% · PS {(q.get('si') or {}).get('ps') if (q.get('si') or {}).get('ps') is not None else '-'}"
                           + (" · en venda" if q.get("onsale") else "") + (" · cedit" if q.get("loaned") else ""))
          res = best_lineup(squad)
          if res:
              tac, pick, capn = res
              lines.append(f"🧢 Onze que faria el bot ({tac}): " + ", ".join(f"{q['short']}{' ©' if q is capn else ''} ({q['xpct'] if q['xpct'] is not None else '?'}%/{q['xps'] if q['xps'] is not None else '-'})"
                                                                            for q in sorted(pick, key=lambda q: o[q['P']])) + (f" · ⚠️ falten {11 - len(pick)}" if len(pick) < 11 else ""))
          msg = "\n".join(lines)
          print("::notice title=plantilla::" + msg.replace("\n", " ¶ ")[:8000])
          if "--quiet" not in sys.argv:
              telegram(msg)
      b.close()


try:
    main()
except Exception:
    print("::error title=mistersquad::" + traceback.format_exc().replace("\n", " | ")[-2000:])
    raise
