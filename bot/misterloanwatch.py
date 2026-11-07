"""Vigilància de cessions del Mister (només lectura): cada hora, fins a l'hora de config/mister_loanwatch.json, mira els
jugadors cedibles dels altres mànagers i avisa per Telegram només dels NOUS que tinguin el % entre min i max
(80–90% de SorareInside, decisió del David 30/10). No demana cap cessió: les fa el David.
"""
import json

from bot.misterclause import main as scan
from bot.notify import telegram
from bot.web import load_json, save_json

CFG = "config/mister_loanwatch.json"


def run():
    cfg = json.load(open(CFG))
    seen = load_json("mister_loanwatch.json", {})
    for lg in cfg.get("leagues", ["Quique"]):
        ok = scan(lg, "TOT", cfg.get("min", 80), loan_only=True, maxpct=cfg.get("max", 90), send=False)
        old = set(seen.get(lg, []))
        new = [c for c in ok if c["pid"] not in old]
        print(f"::notice title=cessions {lg}::{len(ok)} cedibles del {cfg.get('min')}–{cfg.get('max')}%, nous {len(new)}: "
              + ", ".join(f"{c['name']} ({c['pct']}%)" for c in ok))
        if new:
            P = ["", "POR", "DEF", "MIG", "DAV"]
            telegram(f"🔁 {lg} · cessions noves del {cfg.get('min')}–{cfg.get('max')}%:\n" + "\n".join(
                f"• {P[c['P'] or 0]} {c['name']} ({c['team']}) · {c['pct']}% · PS {c['ps'] if c['ps'] is not None else '-'} · de {c['owner']}" for c in new))
        seen[lg] = sorted(old | {c["pid"] for c in ok})
    save_json("mister_loanwatch.json", seen)
    # i la recomanació: quines cessions millorarien l'onze (decisió del David, 7/11); només si ha canviat
    rec = cfg.get("rec")
    if rec:
        from bot.misterloanrec import run as recommend
        for lg in cfg.get("leagues", ["Quique"]):
            try:
                msg = recommend(lg, rec, send=False)
            except Exception as e:
                print(f"::warning title=cessions recomanades::{type(e).__name__}: {str(e)[:200]}")
                continue
            sig = msg.split("Punts esperats")[0]
            st = load_json("mister_loanrec.json", {})
            if st.get(lg) != sig:
                telegram(msg)
                st[lg] = sig
                save_json("mister_loanrec.json", st)


if __name__ == "__main__":
    run()
