"""Quiniela de Predicted11.

Ús:  python -m bot.quiniela laliga                       → llista els partits i el que hi ha posat
     python -m bot.quiniela laliga "Barcelona 2-1 Real Madrid; Sevilla 1-0 Osasuna"
Formats acceptats per partit: "Local 2-1 Visitant" o "Local - Visitant 2-1". Separats per ';' o salts de línia.
"""
import re
import sys

from playwright.sync_api import sync_playwright

from bot.notify import telegram
from bot.web import inject, login_predicted11, new_context, save_session

BASE = "https://www.predicted11.com/es/"


def parse(text):
    picks = []
    for part in re.split(r"[;\n]+", text):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+)$", part) or None
        if m:
            picks.append([m.group(1).strip(), m.group(4).strip(), int(m.group(2)), int(m.group(3))])
            continue
        m = re.match(r"^(.+?)\s*[-–]\s*(.+?)\s+(\d+)\s*-\s*(\d+)$", part)
        if m:
            picks.append([m.group(1).strip(), m.group(2).strip(), int(m.group(3)), int(m.group(4))])
    return picks


def state(page):
    return page.evaluate("""() => [...document.querySelectorAll('.partido-quiniela')].map(b => {
        const ins = [...b.querySelectorAll('.stepper-container input')];
        return b.querySelector('.equipo-local .equipo-nombre').textContent.trim() + ' ' + ins.map(i => i.value).join('-') + ' '
             + b.querySelector('.equipo-visitante .equipo-nombre').textContent.trim() + (ins.some(i => i.disabled) ? ' 🔒' : ''); })""")


def main():
    comp = sys.argv[1]
    text = sys.argv[2] if len(sys.argv) > 2 else ""
    picks = parse(text)
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = new_context(b, "predicted11")
        pg = ctx.new_page()
        login_predicted11(pg)
        save_session(ctx, "predicted11")
        url = f"{BASE}{comp}/quiniela"
        pg.goto(url, wait_until="domcontentloaded")
        pg.wait_for_timeout(2500)
        inject(pg, "p11")
        log = []
        if picks:
            log = pg.evaluate("(p) => __p11.quiniela(p)", picks)
            pg.wait_for_timeout(5000)
            pg.goto(url, wait_until="domcontentloaded")
            pg.wait_for_timeout(2500)
        st = state(pg)
        b.close()
    lines = [f"🎯 Quiniela {comp}" + (" (desada, comprovat recarregant)" if picks else "") + ":"] + st
    bad = [l for l in log if l.startswith("NOMATCH")]
    if bad:
        lines.append("⚠️ No he trobat: " + ", ".join(x.replace("NOMATCH ", "") for x in bad))
    if text and not picks:
        lines.append("⚠️ No he entès cap resultat. Format: «Local 2-1 Visitant; ...»")
    msg = "\n".join(lines)
    print(msg)
    print("::notice title=q::" + " | ".join(lines))
    telegram(msg)


if __name__ == "__main__":
    main()
