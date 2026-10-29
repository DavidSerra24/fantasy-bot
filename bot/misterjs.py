"""Reconeixement (només lectura): com la web del Mister fa les accions (ajaxSetup, puja, venda, ofertes, alineació)."""
import re

import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
B = "https://app-mister.mundodeportivo.com/file/forge-app/786c6e4f/app/dist/js/"
files = ["common.js", "functions.js", "global.js", "listeners.js", "views/market.functions.js", "views/market.js", "views/market.listeners.js",
         "views/team.functions.js", "views/team.js", "views/team.listeners.js", "search-players.js"]
out = []
for f in files:
    t = requests.get(B + f, headers=H, timeout=30).text
    for kw in (r"ajaxSetup", r"#btn-send", r"form-bid", r"popup=|popup:", r"'sale'|\"sale\"", r"captain", r"sw/substitution|substitution", r"beforeSend|headers\s*:", r"X-[A-Za-z-]+"):
        for k, m in enumerate(re.finditer(kw, t)):
            if k >= 2:
                break
            out.append(f"[{f} {kw}] " + t[max(0, m.start() - 500):m.end() + 700].replace("\n", " "))
txt = " ¶¶ ".join(out)
for i in range(0, min(len(txt), 9 * 7000), 7000):
    print(f"::notice title=ctx{i // 7000}::" + txt[i:i + 7000])
