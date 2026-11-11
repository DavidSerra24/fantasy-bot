"""Diagnosi (només lectura): què diu futbolfantasy.com (alineacions probables) d'uns jugadors.
Ús: python -m bot.ffpct "Gómez" ["altre"…]"""
import sys

from playwright.sync_api import sync_playwright

from bot.extras import match_pages
from bot.ff import norm
from bot.web import login_futbolfantasy, new_context

raw = sys.argv[1:]
qs = [norm(x) for x in raw]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = new_context(b, "futbolfantasy").new_page(); login_futbolfantasy(pg)
    ps = match_pages(pg, None)
    b.close()
urls = sorted({(x.get("j"), x["url"]) for x in ps})
print("::notice title=ff partits::" + " ¶ ".join(f"J{j} {u.split('/')[-1]}" for j, u in urls)[:3900])
from collections import defaultdict
by = defaultdict(list)
for x in ps:
    by[x["url"].split("/")[-1]].append(f"{x['name']} {x['pct']}")
print("::notice title=ff mostra::" + " ¶ ".join(f"{k}: {len(v)} · {', '.join(v[:4])}" for k, v in by.items())[:3900])
for x in ps:
    if any(q in norm(x["name"]) for q in qs) or any(r in x["url"] for r in raw):
        print(f"::notice title=ff jugador::{x['name']} · J{x.get('j')} {x['url'].split('/')[-1]} · {x['pct']}% · suplent {x['suplente']} · lesió {x['lesion']}")
