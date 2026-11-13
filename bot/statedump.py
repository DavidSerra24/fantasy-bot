"""Diagnosi: mostra fitxers d'estat (python -m bot.statedump fitxer1 fitxer2…)."""
import json, os, sys
for f in sys.argv[1:] or ["sorare_fixture.json", "sorare_live.json"]:
    p = os.path.join("state", f)
    try:
        st = os.stat(p)
        print(f"::notice title={f}::{open(p).read()[:1500]} (mtime {st.st_mtime:.0f})")
    except Exception as e:
        print(f"::notice title={f}::{e}")
