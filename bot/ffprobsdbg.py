"""Diagnosi (només lectura): què llegeix ff_probs de futbolfantasy.com ara mateix."""
from collections import defaultdict

from playwright.sync_api import sync_playwright

from bot.extras import match_pages
from bot.sources import ff_probs

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    ps = match_pages(pg, None)
    by = defaultdict(list)
    for x in ps:
        by[(x.get("j"), x["url"].rstrip("/").split("/")[-1])].append(x)
    for (j, u), xs in sorted(by.items(), key=lambda k: (k[0][0] or 0, k[0][1])):
        print(f"::notice title=ff {j} {u}::n={len(xs)} amb%={sum(1 for x in xs if x['pct'] > 0)} " + ", ".join(f"{x['name']}:{x['pct']}" for x in xs if any(k in x['name'] for k in ("Soria", "Dimitri", "Suazo", "Davinchi", "Maffeo", "Jutgl", "Satriano")))[:500])
    fp = ff_probs(pg)
    print(f"::notice title=ff_probs::{len(fp)} entrades; jornades triades: " + str(sorted({k['key'].rstrip('/').split('/')[-1] for k in fp}))[:2000])
    b.close()
