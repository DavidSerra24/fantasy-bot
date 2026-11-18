"""Diagnosi: mostra fitxers d'estat (python -m bot.statedump fitxer1 fitxer2…)."""
import json, os, sys
for f in [a for a in sys.argv[1:] if a.endswith(".json")] or ["sorare_fixture.json", "sorare_live.json", "mister_kickoffs.json", "tries.json", "postponed_manual.json", "extras_unusable.json", "extra_resiliencia.json"]:
    p = os.path.join("state", f)
    try:
        st = os.stat(p)
        txt = open(p).read()
        try:
            txt = json.dumps(json.loads(txt), ensure_ascii=False)
        except Exception:
            txt = txt.replace("\n", " ")
        print(f"::notice title={f}::{txt[:3000]} (mtime {st.st_mtime:.0f})")
    except Exception as e:
        print(f"::notice title={f}::{e}")
try:
    d = json.load(open("state/done.json"))
    print("::notice title=done (últims)::" + " | ".join(d[-60:]))
    print("::notice title=fitxers::" + ", ".join(sorted(os.listdir("state"))))
except Exception as e:
    print(f"::notice title=done::{e}")
