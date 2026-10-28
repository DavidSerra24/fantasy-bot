"""Quiniela de Predicted11.

Ús:  python -m bot.quiniela laliga                       → llista els partits i el que hi ha posat
     python -m bot.quiniela laliga "Barcelona 2-1 Real Madrid; Sevilla 1-0 Osasuna"
Formats acceptats per partit: "Local 2-1 Visitant" o "Local - Visitant 2-1". Separats per ';' o salts de línia.
"""
import re
import sys


from bot.notify import telegram

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


NAMES = {"laliga": "LaLiga", "laliga2": "LaLiga 2", "premier-league": "Premier", "serie-a": "Serie A", "champions": "Champions"}
ALIASES = {"laliga": "laliga", "liga": "laliga", "laliga2": "laliga2", "laliga 2": "laliga2", "segunda": "laliga2", "hypermotion": "laliga2",
           "premier": "premier-league", "premier-league": "premier-league", "seriea": "serie-a", "serie-a": "serie-a", "serie a": "serie-a",
           "champions": "champions", "ucl": "champions"}


HEADERS = [(r"hypermotion|laliga\s*2|segunda", "laliga2"), (r"laliga|la liga|primera", "laliga"), (r"premier", "premier-league"),
           (r"serie\s*a", "serie-a"), (r"champions", "champions")]
GROK = re.compile(r"(?:previst|\n|\t|^|(?<=\d-\d))\s*([^\n\t–]+?)\s+–\s+([^\n\t]+?)\s*([12X])\s*(\d{1,2})\s*-\s*(\d{1,2})(?!\d)")


def parse_grok(text):
    """Taula del Grok enganxada («Torino – Monza12-0…», amb capçaleres «🇮🇹 Serie A – Jornada 8»).
    Retorna {competició: [[local, visitant, gols local, gols visitant], ...]}. El pronòstic 1/X/2 es descarta."""
    out, comp = {}, None
    text = re.sub(r"\*+", "", text).replace("|", " ")  # taula en Markdown: «| **Torino – Monza** | **1** | **2-0** |»
    for line in text.splitlines():
        if re.search(r"\d{1,2}-\d{1,2}\s+d[’']", line) or line.strip().startswith(("Aquí", "Resum")):
            continue  # «(23-26 d’octubre)», resum 1·X·2
        if "–" in line and not re.search(r"\d-\d", line) and len(line) < 80:  # capçalera de competició
            for rx, c in HEADERS:
                if re.search(rx, line, re.I):
                    comp = c
                    break
            continue
        for m in GROK.finditer(line):
            if comp:
                home = re.sub(r"^.*(Resultado previsto|previsto|previst)\s*", "", m.group(1).strip()).strip()
                out.setdefault(comp, []).append([home, m.group(2).strip(), int(m.group(4)), int(m.group(5))])
    return out


def split_comp(text):
    """«serie a Bologna 2-1 Monza; ...» → ('serie-a', 'Bologna 2-1 Monza; ...'). Sense competició → (None, text)."""
    t = text.strip()
    for k in sorted(ALIASES, key=len, reverse=True):
        if t.lower().startswith(k) and (len(t) == len(k) or not t[len(k)].isalnum()):
            return ALIASES[k], t[len(k):].strip(" :\n")
    return None, t


def run(comp, text="", remind=None):
    """Omple (o només llegeix) la quiniela. remind = text del tancament: només avisa per Telegram si està buida."""
    from playwright.sync_api import sync_playwright  # aquí dins: el planificador importa aquest mòdul sense navegador
    from bot.web import inject, login_predicted11, new_context, save_session
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
    if remind is not None:
        empty = [l for l in st if "---" in l and "🔒" not in l]
        if empty:
            telegram(f"📝 Falta la Quiniela de {NAMES.get(comp, comp)} (tanca {remind}).\n\n"
                     + "\n".join(l.replace(" --- ", " - ") for l in empty)
                     + f"\n\nEnvia-me-la responent aquí, un partit per línia:\n/quiniela {comp}\n"
                     + "\n".join(l.replace(" --- ", " 1-0 ").replace(" 1-0 ", " 1-0 ", 1) for l in empty[:2]) + "\n...")
        print("::notice title=q::" + (" | ".join(empty) if empty else "quiniela ja feta"))
        return
    lines = [f"🎯 Quiniela {NAMES.get(comp, comp)}" + (" (desada, comprovat recarregant)" if picks else "") + ":"] + st
    bad = [l for l in log if l.startswith("NOMATCH")]
    if bad:
        lines.append("⚠️ No he trobat: " + ", ".join(x.replace("NOMATCH ", "") for x in bad))
    if text and not picks:
        lines.append("⚠️ No he entès cap resultat. Format: «Local 2-1 Visitant; ...»")
    msg = "\n".join(lines)
    print(msg)
    print("::notice title=q::" + " | ".join(lines))
    telegram(msg)


def main():
    if len(sys.argv) > 2 and sys.argv[2].startswith("--recorda"):
        return run(sys.argv[1], remind=(" ".join(sys.argv[2:])[len("--recorda"):].strip() or "aviat"))
    run(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "")


if __name__ == "__main__":
    main()
