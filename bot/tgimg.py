"""Imatges per a Telegram (decisió del David, 11/11: «veure tant text em torna boig»).

Cada alineació es dibuixa com una targeta amb un camp de futbol (porter a baix, davanters a dalt; l'Extra al costat) i
s'envien totes juntes en una sola imatge (sendPhoto) amb un text curt a sota. Si alguna cosa falla, no passa res: el
bot continua enviant el text de sempre.

Ús: send_cards("Sorare · GW12", [card(...), ...], caption="...")
"""
import html as _h
import os

import requests

LINES = {"G": 0, "D": 1, "M": 2, "F": 3}  # de baix a dalt
POS = {"Goalkeeper": "G", "Defender": "D", "Midfielder": "M", "Forward": "F", "Extra": "X",
       "POR": "G", "DEF": "D", "MIG": "M", "DAV": "F", "EXT": "X", "G": "G", "D": "D", "M": "M", "F": "F", "X": "X"}
GRADE_COL = {"A": "#16a34a", "B": "#65a30d", "C": "#ca8a04", "D": "#ea580c", "E": "#dc2626", "F": "#991b1b"}


def player(pos, name, sub="", badge="", badge_col=None, cap=False, warn=False, dim=False):
    """pos: Goalkeeper/Defender/…/Extra o G/D/M/F/X. badge: lletra d'impacte, % o punts (es pinta en una píndola)."""
    b = str(badge or "")
    col = badge_col or GRADE_COL.get(b[:1].upper(), "#334155") if b else None
    return {"pos": POS.get(pos, "X"), "name": name, "sub": sub, "badge": b, "col": col, "cap": cap, "warn": warn, "dim": dim}


def card(title, players, subtitle="", footer="", tag="", tag_col="#2563eb"):
    return {"title": title, "subtitle": subtitle, "footer": footer, "players": players, "tag": tag, "tag_col": tag_col}


def _chip(p):
    e = _h.escape
    badge = f'<span class="b" style="background:{p["col"]}">{e(p["badge"])}</span>' if p["badge"] else ""
    cap = '<span class="c">C</span>' if p["cap"] else ""
    cls = "p" + (" warn" if p["warn"] else "") + (" dim" if p["dim"] else "")
    return (f'<div class="{cls}"><div class="n">{cap}{e(p["name"])}</div>'
            f'<div class="s">{badge}<span>{e(p["sub"])}</span></div></div>')


def _card_html(c):
    e = _h.escape
    rows = []
    for ln in sorted(LINES, key=lambda k: -LINES[k]):  # davanters a dalt
        ps = [p for p in c["players"] if p["pos"] == ln]
        if ps:
            rows.append('<div class="row">' + "".join(_chip(p) for p in ps) + "</div>")
    extra = [p for p in c["players"] if p["pos"] == "X"]
    side = ('<div class="side"><div class="lbl">EXTRA</div>' + "".join(_chip(p) for p in extra) + "</div>") if extra else ""
    tag = f'<span class="tag" style="background:{c["tag_col"]}">{e(c["tag"])}</span>' if c.get("tag") else ""
    return (f'<div class="card"><div class="h"><div class="t">{e(c["title"])}{tag}</div>'
            f'<div class="st">{e(c.get("subtitle") or "")}</div></div>'
            f'<div class="body"><div class="pitch">{"".join(rows)}</div>{side}</div>'
            + (f'<div class="f">{e(c["footer"])}</div>' if c.get("footer") else "") + "</div>")


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0f172a;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#e2e8f0;padding:18px;width:%dpx}
h1{font-size:22px;font-weight:700;margin-bottom:12px;color:#f8fafc}
.grid{display:grid;grid-template-columns:repeat(%d,1fr);gap:14px}
.card{background:#1e293b;border-radius:14px;overflow:hidden;border:1px solid #334155}
.h{padding:10px 12px 6px}
.t{font-size:16px;font-weight:700;color:#f8fafc;display:flex;align-items:center;gap:8px}
.st{font-size:12px;color:#94a3b8;margin-top:2px}
.tag{font-size:11px;font-weight:700;color:#fff;border-radius:6px;padding:2px 6px}
.body{display:flex;gap:8px;padding:0 10px 10px}
.pitch{flex:1;background:linear-gradient(#166534,#15803d);border-radius:10px;padding:8px 4px;display:flex;flex-direction:column;gap:8px;
  border:2px solid #22c55e33;position:relative}
.row{display:flex;justify-content:space-evenly;gap:4px}
.side{width:118px;background:#0f172a;border-radius:10px;padding:6px 4px;display:flex;flex-direction:column;align-items:center;gap:6px}
.lbl{font-size:10px;color:#94a3b8;letter-spacing:1px}
.p{background:#0f172aee;border-radius:9px;padding:5px 7px;min-width:96px;max-width:132px;text-align:center;border:1px solid #ffffff22}
.p.warn{border:2px solid #f59e0b}
.p.dim{opacity:.55}
.n{font-size:12.5px;font-weight:700;color:#f8fafc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.s{font-size:10.5px;color:#cbd5e1;display:flex;gap:4px;justify-content:center;align-items:center;margin-top:3px;white-space:nowrap}
.b{color:#fff;font-weight:800;border-radius:5px;padding:0 5px;font-size:11px}
.c{background:#e11d48;color:#fff;border-radius:50%%;font-size:9px;font-weight:800;padding:1px 4px;margin-right:4px}
.f{font-size:11.5px;color:#94a3b8;padding:0 12px 10px}
"""


def render(title, cards, cols=None):
    """PNG (bytes) amb totes les targetes."""
    from playwright.sync_api import sync_playwright
    cols = cols or (1 if len(cards) == 1 else 2)
    width = 560 if cols == 1 else 1060
    html = (f"<html><head><meta charset='utf-8'><style>{CSS % (width, cols)}</style></head><body>"
            f"<h1>{_h.escape(title)}</h1><div class='grid'>{''.join(_card_html(c) for c in cards)}</div></body></html>")
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": width + 36, "height": 400}, device_scale_factor=2)
        pg.set_content(html)
        png = pg.locator("body").screenshot(type="png")
        b.close()
    return png


def send_photo(png, caption=""):
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return False
    r = requests.post(f"https://api.telegram.org/bot{tok}/sendPhoto", data={"chat_id": chat, "caption": caption[:1000]},
                      files={"photo": ("alineacions.png", png, "image/png")}, timeout=60)
    if not r.ok:  # massa gran per a foto: com a document
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendDocument", data={"chat_id": chat, "caption": caption[:1000]},
                          files={"document": ("alineacions.png", png, "image/png")}, timeout=60)
    if not r.ok:
        print("::warning title=telegram foto::" + r.text[:200])
        return False
    return (r.json().get("result") or {}).get("message_id") or True


def send_cards(title, cards, caption="", cols=None):
    """Envia la imatge; retorna l'id del missatge (o True) si ha anat bé, False si no (el cridador envia el text)."""
    if not cards:
        return False
    try:
        return send_photo(render(title, cards, cols), caption)
    except Exception as e:
        print(f"::warning title=telegram imatge::{type(e).__name__}: {str(e)[:200]}")
        return False
