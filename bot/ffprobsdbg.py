"""Diagnosi (només lectura): què llegeix ff_probs ara."""
from playwright.sync_api import sync_playwright

from bot.sources import ff_probs

with sync_playwright() as p:
    b = p.chromium.launch()
    fp = ff_probs(b.new_page())
    urls = sorted({e["key"].rstrip("/").split("/")[-1] for e in fp})
    print(f"::notice title=ff_probs::{len(fp)} entrades, partits: {' '.join(urls)}")
    print("::notice title=jugadors::" + ", ".join(f"{e['name']}:{e['pct']}" for e in fp if any(k in e["name"] for k in ("Soria", "Dimitri", "Suazo", "Davinchi", "Maffeo", "Jutgl", "Satriano", "Villar", "Soriano"))))
    b.close()
