"""Diagnosi (només lectura): busca un text als fitxers de state/ i n'imprimeix el context."""
import pathlib
import sys

pat = " ".join(sys.argv[1:]).lower()
for f in sorted(pathlib.Path("state").glob("*.json")):
    t = f.read_text(encoding="utf-8", errors="ignore")
    i = t.lower().find(pat)
    while i >= 0:
        print(f"::notice title={f.name}::" + t[max(0, i - 1200):i + 600].replace("\n", " ")[:3800])
        i = t.lower().find(pat, i + 2000)
