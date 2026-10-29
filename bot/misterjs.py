"""Reconeixement (només lectura): endpoints /ajax i /api2 del codi JavaScript de la web del Mister (amb sessió)."""
import re

import requests
from playwright.sync_api import sync_playwright

from bot.mister import U, login, new_context

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b).new_page()
    login(pg)
    js = set()
    for path in ("/team", "/market"):
        pg.goto(U + path, wait_until="networkidle"); pg.wait_for_timeout(2000)
        js |= set(pg.evaluate("() => [...document.scripts].map(s => s.src).filter(Boolean)"))
        inline = pg.evaluate("() => [...document.scripts].filter(s => !s.src).map(s => s.textContent).join('\\n')")
    b.close()
print("::notice title=js::" + " ".join(sorted(js))[:3000])
found = {}
for u in sorted(js):
    if not any(k in u for k in ("mundodeportivo", "forge", "mister")):
        continue
    try:
        t = requests.get(u, headers=H, timeout=30).text
    except Exception:
        continue
    for m in re.finditer(r"['\"`](/?(?:ajax|api2|action)/[A-Za-z0-9_\-/]+)['\"`]", t):
        found.setdefault(m.group(1), t[max(0, m.start() - 300):m.end() + 400].replace("\n", " "))
for m in re.finditer(r"['\"`](/?(?:ajax|api2|action)/[A-Za-z0-9_\-/]+)['\"`]", inline):
    found.setdefault(m.group(1), inline[max(0, m.start() - 300):m.end() + 400].replace("\n", " "))
print("::notice title=endpoints::" + " | ".join(sorted(found))[:6000])
out = []
for k in sorted(found):
    if re.search(r"bid|sale|sell|offer|transfer|lineup|formation|captain|substitution|market|clause|pool|balance", k, re.I):
        out.append(f"[{k}] " + found[k][:900])
txt = " ¶¶ ".join(out)
for i in range(0, min(len(txt), 8 * 7000), 7000):
    print(f"::notice title=ctx{i // 7000}::" + txt[i:i + 7000])
