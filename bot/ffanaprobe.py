"""Diagnosi (només lectura): enllaços i selectors de futbolfantasy.com/analytics."""
import re
import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"}
for url in ("https://www.futbolfantasy.com/analytics", "https://www.futbolfantasy.com/analytics/laliga2"):
    try:
        h = requests.get(url, headers=H, timeout=30).text
    except Exception as e:
        print(f"::notice title=err {url}::{e}"); continue
    links = sorted(set(re.findall(r'href="([^"]*analytics[^"]*)"', h)))
    print(f"::notice title=links {url}::len={len(h)} " + " ".join(links)[:3500])
    opts = re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', h)
    print(f"::notice title=opts {url}::" + " | ".join(f"{v}={t.strip()}" for v, t in opts)[:3500])
    for kw in ("fantasy-es", "Fantasy✨", "fantasyes", "puntos"):
        for m in list(re.finditer(re.escape(kw), h))[:2]:
            print(f"::notice title=kw {kw}::" + re.sub(r"\s+", " ", h[max(0, m.start() - 300):m.start() + 300]))
