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


def player(pos, name, sub="", badge="", badge_col=None, cap=False, warn=False, dim=False, pic=None, pct=""):
    """pos: Goalkeeper/Defender/…/Extra o G/D/M/F/X. badge: lletra d'impacte, % o punts (es pinta en una píndola)."""
    b = str(badge or "")
    col = badge_col or GRADE_COL.get(b[:1].upper(), "#334155") if b else None
    return {"pos": POS.get(pos, "X"), "name": name, "sub": sub, "badge": b, "col": col, "cap": cap, "warn": warn, "dim": dim, "pic": pic, "pct": pct}


def card(title, players, subtitle="", footer="", tag="", tag_col="#2563eb"):
    return {"title": title, "subtitle": subtitle, "footer": footer, "players": players, "tag": tag, "tag_col": tag_col}


_IMG = {}


def _img(url):
    """La imatge com a data: URI (es baixa aquí perquè la captura no depengui de la xarxa del navegador)."""
    if not url:
        return None
    if url not in _IMG:
        try:
            import base64
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            _IMG[url] = "data:" + (r.headers.get("content-type") or "image/png") + ";base64," + base64.b64encode(r.content).decode()
        except Exception as ex:
            print(f"::warning title=imatge carta::{str(ex)[:120]}")
            _IMG[url] = None
    return _IMG[url]


def _chip(p):
    e = _h.escape
    badge = f'<span class="b" style="background:{p["col"]}">{e(p["badge"])}</span>' if p["badge"] else ""
    cap = '<span class="c">C</span>' if p["cap"] else ""
    cls = "p" + (" warn" if p["warn"] else "") + (" dim" if p["dim"] else "")
    src = _img(p.get("pic"))
    if src:  # la carta de Sorare (decisió del David, 11/11: «vull veure les cartes»); si no es pot baixar, el nom
        return (f'<div class="{cls} pc"><div class="img"><img src="{src}">'
                + (f'<span class="b ob" style="background:{p["col"]}">{e(p["badge"])}</span>' if p["badge"] else "")
                + ('<span class="c oc">C</span>' if p["cap"] else "")
                + f'</div><div class="s"><span>{e(p["sub"])}</span></div>'
                + (f'<div class="tk">{e(p["name"][-1])}</div>' if p["name"].endswith("✓") else "") + "</div>")
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
.side{width:124px;background:#0f172a;border-radius:10px;padding:6px 4px;display:flex;flex-direction:column;align-items:center;gap:6px}
.lbl{font-size:10px;color:#94a3b8;letter-spacing:1px}
.p{background:#0f172aee;border-radius:9px;padding:5px 7px;min-width:96px;max-width:132px;text-align:center;border:1px solid #ffffff22}
.p.warn{border:2px solid #f59e0b}
.p.dim{opacity:.55}
.n{font-size:12.5px;font-weight:700;color:#f8fafc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.s{font-size:10.5px;color:#cbd5e1;display:flex;gap:4px;justify-content:center;align-items:center;margin-top:3px;white-space:nowrap}
.b{color:#fff;font-weight:800;border-radius:5px;padding:0 5px;font-size:11px}
.c{background:#e11d48;color:#fff;border-radius:50%%;font-size:9px;font-weight:800;padding:1px 4px;margin-right:4px}
.f{font-size:11.5px;color:#94a3b8;padding:0 12px 10px}
.pc{background:transparent;border:none;padding:0;min-width:0;max-width:none;position:relative}
.pc .img{position:relative;width:104px}
.pc img{width:104px;display:block;border-radius:7px}
.pc.warn{border:none}
.pc.warn .img img{outline:3px solid #f59e0b}
.ob{position:absolute;left:4px;top:4px;font-size:13px;padding:1px 6px;box-shadow:0 1px 3px #0008}
.oc{position:absolute;right:4px;top:4px;font-size:11px;padding:2px 6px;margin:0}
.pc .s{background:#0f172add;border-radius:6px;padding:2px 4px;margin-top:3px}
.tk{position:absolute;right:4px;bottom:28px;background:#16a34a;color:#fff;font-weight:800;border-radius:50%%;width:20px;height:20px;
  display:flex;align-items:center;justify-content:center;font-size:12px}
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
        png = render(title, cards, cols)
        if os.getenv("TG_IMG_DIR"):  # còpia per revisar-la (artefacte del workflow)
            os.makedirs(os.environ["TG_IMG_DIR"], exist_ok=True)
            n = len(os.listdir(os.environ["TG_IMG_DIR"]))
            open(os.path.join(os.environ["TG_IMG_DIR"], f"tg{n}.png"), "wb").write(png)
            import base64
            b64 = base64.b64encode(png).decode()
            for i in range(0, len(b64), 4000):
                print(f"IMG64 {n} " + b64[i:i + 4000])
        return send_photo(png, caption)
    except Exception as e:
        print(f"::warning title=telegram imatge::{type(e).__name__}: {str(e)[:200]}")
        return False


# --- Format «alineació de Sorare» (decisió del David, 11/11: «podem fer algo així?», amb una imatge d'exemple):
# fons fosc amb el camp dibuixat, capçalera (jornada, competició, núm. d'alineació), formació, cartes a la seva línia
# (porter a dalt) i peu amb el capità i els punts previstos. Una imatge per alineació; s'envien juntes (àlbum).
PITCH_SVG = """<svg class="lines" viewBox="0 0 520 640" preserveAspectRatio="none"><g fill="none" stroke="#ffffff2e" stroke-width="2">
<path d="M60 8 L460 8 L515 632 L5 632 Z"/><path d="M150 8 L165 92 L355 92 L370 8"/><path d="M205 8 L210 40 L310 40 L315 8"/>
<path d="M35 320 L485 320"/><ellipse cx="260" cy="320" rx="62" ry="40"/><path d="M120 632 L128 560 L392 560 L400 632"/></g></svg>"""

# Pista de bàsquet per a l'NBA (decisió del David, 12/11): parquet, cèrcol a dalt, zona, línia de 3 i cercle central.
COURT_SVG = """<svg class="lines" viewBox="0 0 520 640" preserveAspectRatio="none">
<defs><pattern id="wd" width="40" height="640" patternUnits="userSpaceOnUse"><rect width="40" height="640" fill="#b5793f"/>
<rect x="20" width="20" height="640" fill="#a96f38"/><path d="M0 0V640M20 0V640" stroke="#00000022" stroke-width="1"/></pattern></defs>
<rect x="10" y="8" width="500" height="624" rx="6" fill="url(#wd)" opacity=".55"/>
<g fill="none" stroke="#ffffffcc" stroke-width="3">
<rect x="10" y="8" width="500" height="624" rx="6"/>
<rect x="185" y="8" width="150" height="190" fill="#c2410c66"/><circle cx="260" cy="198" r="75"/>
<path d="M45 8V120A215 215 0 0 0 475 120V8"/><circle cx="260" cy="48" r="11" stroke="#f97316"/><path d="M228 32H292"/>
<path d="M10 632H510"/><path d="M185 632A75 75 0 0 1 335 632"/><circle cx="260" cy="632" r="28"/></g></svg>"""

LCSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0b0b0f;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#f4f4f5;width:560px}
.w{padding:22px 22px 18px;background:radial-gradient(120% 60% at 80% 0%,#1d1d2b 0%,#0b0b0f 60%)}
.top{display:flex;align-items:center;gap:16px}
.brand{font-size:30px;font-weight:800;letter-spacing:-1px;padding-right:16px;border-right:2px solid #ffffff55;line-height:1}
.gw{flex:1}.gw b{font-size:26px;font-weight:800;display:block;line-height:1}
.gw span{font-size:10.5px;letter-spacing:3px;color:#d4d4d8;text-transform:uppercase;display:block;margin-top:5px}
.pill{border:2px solid #f4f4f5;border-radius:22px;padding:6px 14px;font-weight:800;font-size:13px;white-space:nowrap}
.form{display:flex;align-items:center;gap:12px;margin:16px 0 8px;color:#a1a1aa;font-weight:700;font-size:20px}
.form:before,.form:after{content:"";flex:1;height:1px;background:#ffffff40}
.pitch{position:relative;padding:14px 4px 10px}
.lines{position:absolute;inset:0;width:100%;height:100%}
.row{position:relative;display:flex;justify-content:space-evenly;margin:10px 0}
.t{width:104px;text-align:center;position:relative}
.t img{width:104px;display:block;border-radius:8px;box-shadow:0 4px 14px #000a}
.t.warn img{outline:3px solid #f59e0b}
.t.new img{outline:4px solid #22d3ee;box-shadow:0 0 18px #22d3eeaa}
.nw{position:absolute;left:50%;transform:translateX(-50%);top:-9px;background:#22d3ee;color:#0b0b0f;font-weight:800;font-size:10px;
  border-radius:6px;padding:1px 6px;letter-spacing:1px}
.t .nm{background:#18181bee;border:1px solid #ffffff30;border-radius:8px;padding:30px 4px;font-weight:700;font-size:13px}
.t .sub{font-size:10.5px;color:#e4e4e7;text-shadow:0 1px 3px #000,0 0 6px #000;margin-top:4px;width:150px;margin-left:-23px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.g{position:absolute;right:3px;top:4px;color:#fff;font-weight:800;border-radius:6px;padding:1px 6px;font-size:13px;box-shadow:0 1px 3px #000a}
.g.lt{color:#0b0b0f}.pc~.g{top:29px}
.cp{position:absolute;left:4px;top:4px;background:#e11d48;color:#fff;font-weight:800;border-radius:50%;font-size:11px;padding:2px 6px}
.ok{position:absolute;right:4px;bottom:24px;background:#16a34a;color:#fff;font-weight:800;border-radius:50%;width:20px;height:20px;font-size:12px;
  display:flex;align-items:center;justify-content:center}
.pc{position:absolute;right:3px;top:4px;color:#0b0b0f;font-weight:800;border-radius:7px;padding:1px 6px 1px 4px;font-size:12.5px;
  display:flex;align-items:center;gap:2px;box-shadow:0 1px 3px #000a}
.pc svg{width:13px;height:13px}
.pc.xi{background:#fff!important;box-shadow:0 0 6px #fff,0 0 14px #ffffffcc,0 0 22px #ffffff88}
.foot{display:flex;align-items:center;margin-top:12px;border:1px solid #ffffff30;border-radius:14px;padding:12px 16px;background:#111114}
.cap{flex:1;border-right:1px solid #ffffff30}.cap .k{color:#eab308;font-weight:800;font-size:12px;letter-spacing:2px}
.cap .n{font-size:18px;font-weight:800;margin-top:3px}.cap .c{font-size:12.5px;color:#a1a1aa}
.ps{flex:1;padding-left:16px}.ps .k{color:#a1a1aa;font-size:11px;letter-spacing:2px;font-weight:700}.ps .v{font-size:30px;font-weight:800}
.tag{border:2px solid;border-radius:22px;padding:6px 12px;font-weight:800;font-size:13px}
.note{font-size:11.5px;color:#a1a1aa;margin-top:8px}
"""


# com a l'app de Sorare (captura del David, 12/11): samarreta + %, cian ≥80%, groc 60–70%, taronja 40–50%, vermell menys;
# titular confirmat: 100% en blanc brillant. La lletra d'impacte, a sota, amb els colors clars de Sorare.
SHIRT = ('<svg viewBox="0 0 24 24"><path fill="#0b0b0f" d="M8 3 2 6.5 4.5 11 7 10v11h10V10l2.5 1L22 6.5 16 3'
         'c-.5 1.7-2.1 3-4 3s-3.5-1.3-4-3z"/></svg>')
SGRADE = {"A": "#34d399", "B": "#4ade80", "C": "#bef264", "D": "#fde047", "E": "#fdba74", "F": "#f87171"}


def _sg(p):
    """Color clar de Sorare si la píndola és una lletra d'impacte (A–F, o «A 53» al Set)."""
    b = str(p.get("badge") or "")
    return SGRADE.get(b[:1]) if b[:1] in SGRADE and (len(b) == 1 or b[1] == " ") else None


def _pct_col(t):
    try:
        v = int(str(t).strip("<%"))
    except ValueError:
        return "#94a3b8"
    if str(t).startswith("<"):
        v = 70
    return "#ffffff" if v >= 100 else "#67e8f9" if v >= 80 else "#fde047" if v >= 60 else "#fdba74" if v >= 40 else "#f87171"


def render_lineup(gw, comp, num, players, cap_name="", cap_club="", score=None, tag="", tag_col="#a855f7", note="", form=None, left=None, court=False):
    """Una imatge d'alineació. players: player(...) amb pos G/D/M/F (l'Extra ja a la seva línia)."""
    from playwright.sync_api import sync_playwright
    e = _h.escape
    lines = {k: [p for p in players if p["pos"] == k] for k in "GDMF"}
    form = form or "-".join(str(len(lines[k])) for k in "DMF" if lines[k])
    rows = []
    for k in "GDMF":  # porter a dalt, com a l'exemple
        if not lines[k]:
            continue
        tiles = []
        for p in lines[k]:
            src = _img(p.get("pic"))
            body = f'<img src="{src}">' if src else f'<div class="nm">{e(p["name"])}</div>'
            tiles.append(f'<div class="t{" warn" if p["warn"] else ""}{" new" if p.get("new") else ""}">{body}'
                         + (f'<span class="pc{" xi" if p["pct"] == "100%" else ""}" style="background:{_pct_col(p["pct"])}">{SHIRT}{e(p["pct"])}</span>' if p.get("pct") else "")
                         + (f'<span class="g{" lt" if _sg(p) else ""}" style="background:{_sg(p) or p["col"]}">{e(p["badge"])}</span>' if p["badge"] else "")
                         + ('<span class="cp">C</span>' if p["cap"] else "")
                         + ('<span class="ok">✓</span>' if p["name"].endswith("✓") else "")
                         + ('<span class="nw">NOU</span>' if p.get("new") else "")
                         + f'<div class="sub">{e(p["sub"])}</div></div>')
        rows.append('<div class="row">' + "".join(tiles) + "</div>")
    html = (f"<html><head><meta charset='utf-8'><style>{LCSS}</style></head><body><div class='w'>"
            f"<div class='top'><div class='brand'>Sorare</div><div class='gw'><b>{e(("GW " + str(gw)) if str(gw).isdigit() else str(gw))}</b><span>{e(comp)}</span></div>"
            f"<div class='pill'>{e(num)}</div></div>"
            f"<div class='form'>{e(form)}</div><div class='pitch'>{COURT_SVG if court else PITCH_SVG}{''.join(rows)}</div>"
            + (f"<div class='foot'><div class='cap'><div class='k'>{e(left[0])}</div><div class='n'>{e(left[1])}</div><div class='c'>{e(left[2] if len(left) > 2 else '')}</div></div>"
               if left else
               f"<div class='foot'><div class='cap'><div class='k'>👑 CAPITÀ</div><div class='n'>{e(cap_name)}</div><div class='c'>{e(cap_club)}</div></div>")
            + f"<div class='ps'><div class='k'>PUNTS PREVISTOS</div><div class='v'>{'' if score is None else f'{score:.0f}'}</div></div>"
            + (f"<div class='tag' style='color:{tag_col};border-color:{tag_col}'>{e(tag)}</div>" if tag else "") + "</div>"
            + (f"<div class='note'>{e(note)}</div>" if note else "") + "</div></body></html>")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 560, "height": 400}, device_scale_factor=2)
        pg.set_content(html)
        png = pg.locator("body").screenshot(type="png")
        b.close()
    _keep(png)
    return png


def _keep(png):
    if os.getenv("TG_IMG_DIR"):  # còpia per revisar-la
        import base64
        os.makedirs(os.environ["TG_IMG_DIR"], exist_ok=True)
        n = len(os.listdir(os.environ["TG_IMG_DIR"]))
        open(os.path.join(os.environ["TG_IMG_DIR"], f"tg{n}.png"), "wb").write(png)
        b64 = base64.b64encode(png).decode()
        for i in range(0, len(b64), 4000):
            print(f"IMG64 {n} " + b64[i:i + 4000])


def send_album(pngs, caption=""):
    """Diverses imatges en un sol missatge (sendMediaGroup, fins a 10); el text va a la primera."""
    import json
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat or not pngs:
        return False
    if len(pngs) == 1:
        return send_photo(pngs[0], caption)
    ok = True
    for k in range(0, len(pngs), 10):
        part = pngs[k:k + 10]
        media = [{"type": "photo", "media": f"attach://p{i}", **({"caption": caption[:1000]} if k == 0 and i == 0 and caption else {})}
                 for i in range(len(part))]
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMediaGroup", data={"chat_id": chat, "media": json.dumps(media)},
                          files={f"p{i}": (f"p{i}.png", png, "image/png") for i, png in enumerate(part)}, timeout=90)
        if not r.ok:
            print("::warning title=telegram àlbum::" + r.text[:200])
            ok = False
    return ok


def send_lineups(cards, caption=""):
    """Una imatge per alineació (format «alineació de Sorare») en un àlbum. Retorna l'id del missatge o True si ha anat bé."""
    if not cards:
        return False
    _mark_changes(cards)
    try:
        pngs = [render_lineup(c.get("gw") or "", c["title"], c.get("num") or "", c["players"], c.get("cap_name") or "",
                              c.get("cap_club") or "", c.get("score"), c.get("tag") or "", c.get("tag_col") or "#a855f7",
                              " · ".join(x for x in (c.get("subtitle"), c.get("footer")) if x), c.get("form"), c.get("left"), c.get("court", False)) for c in cards]
        return send_album(pngs, caption)
    except Exception as ex:
        print(f"::warning title=telegram imatge::{type(ex).__name__}: {str(ex)[:200]}")
        return False


def _mark_changes(cards):
    """Jugadors nous respecte de l'última imatge de la mateixa alineació → marc blau i «NOU» (decisió del David, 11/11).
    La primera vegada que s'envia una alineació no es marca res. state/tg_lineups.json: clau → noms."""
    from bot.web import load_json, save_json
    st = load_json("tg_lineups.json", {})
    for c in cards:
        key = f"{c.get('gw')}|{c.get('title')}|{c.get('num')}"
        names = [p["name"].rstrip(" ✓") for p in c["players"]]
        prev = st.get(key)
        if prev is not None:
            for p in c["players"]:
                p["new"] = p["name"].rstrip(" ✓") not in prev
            if any(p.get("new") for p in c["players"]):
                c["footer"] = ((c.get("footer") or "") + " · " if c.get("footer") else "") + "marc blau = canvi respecte de l'última"
        st[key] = names
    if len(st) > 300:
        st = dict(list(st.items())[-300:])
    save_json("tg_lineups.json", st)


# --- Missions (decisió del David, 11/11: «m'ho faràs per les missions també? de NBA també»)
RAR_COL = {"limited": "#eab308", "rare": "#ef4444", "super_rare": "#3b82f6", "unique": "#a855f7", "common": "#a1a1aa"}
MCSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#0b0b0f;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#f4f4f5;width:600px}
.w{padding:20px;background:radial-gradient(120% 60% at 80% 0%,#1d1d2b 0%,#0b0b0f 60%)}
h1{font-size:24px;font-weight:800;margin-bottom:12px}
.m{border:1px solid #ffffff26;border-radius:14px;padding:12px;margin-bottom:12px;background:#111114}
.mh{display:flex;align-items:center;gap:8px}.mt{font-size:16px;font-weight:800;flex:1}
.tag{border:2px solid;border-radius:16px;padding:2px 10px;font-weight:800;font-size:11.5px;text-transform:capitalize}
.ms{font-size:11.5px;color:#a1a1aa;margin:3px 0 10px}
.r{display:flex;flex-wrap:wrap;gap:10px}
.t{width:100px;text-align:center;position:relative}
.t img{width:100px;display:block;border-radius:8px;box-shadow:0 4px 12px #000a}
.t .nm{background:#18181b;border:1px solid #ffffff30;border-radius:8px;padding:30px 4px;font-weight:700;font-size:12.5px}
.t.new img{outline:4px solid #22d3ee;box-shadow:0 0 16px #22d3eeaa}
.t.lock{opacity:.5}
.sub{font-size:10.5px;color:#d4d4d8;margin-top:4px}
.b{position:absolute;left:4px;top:4px;background:#16a34a;color:#fff;font-weight:800;border-radius:6px;padding:1px 6px;font-size:12px}
.b.low{background:#64748b}
.nw{position:absolute;left:50%;transform:translateX(-50%);top:-9px;background:#22d3ee;color:#0b0b0f;font-weight:800;font-size:10px;border-radius:6px;padding:1px 6px}
.lk{position:absolute;right:4px;top:4px;font-size:13px}
.lg{font-size:11px;color:#a1a1aa}
"""


def render_missions(title, blocks):
    from playwright.sync_api import sync_playwright
    e = _h.escape
    out = []
    for m in blocks:
        tiles = []
        for p in m["players"]:
            src = _img(p.get("pic"))
            body = f'<img src="{src}">' if src else f'<div class="nm">{e(p["name"])}</div>'
            low = p.get("extra") or str(p.get("badge", "")).startswith(("0", "-"))
            tiles.append(f'<div class="t{" new" if p.get("new") else ""}{" lock" if p.get("locked") else ""}">{body}'
                         + (f'<span class="b{" low" if low else ""}">{e(str(p["badge"]))}</span>' if p.get("badge") else "")
                         + ('<span class="lk">🔒</span>' if p.get("locked") else "")
                         + ('<span class="nw">NOU</span>' if p.get("new") else "")
                         + f'<div class="sub">{e(p.get("sub") or "")}</div></div>')
        col = RAR_COL.get((m.get("tag") or "").lower(), "#a1a1aa")
        out.append(f"<div class='m'><div class='mh'><div class='mt'>{e(m['title'])}</div>"
                   f"<div class='tag' style='color:{col};border-color:{col}'>{e((m.get('tag') or '').replace('_', ' '))}</div></div>"
                   f"<div class='ms'>{e(m.get('sub') or '')}</div><div class='r'>{''.join(tiles)}</div></div>")
    html = (f"<html><head><meta charset='utf-8'><style>{MCSS}</style></head><body><div class='w'><h1>{e(title)}</h1>{''.join(out)}"
            "<div class='lg'>% = opcions (titular × accions decisives als últims 20) · a l'NBA, marge sobre l'objectiu · 🔒 partit començat · marc blau = canvi</div>"
            "</div></body></html>")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 600, "height": 400}, device_scale_factor=2)
        pg.set_content(html)
        png = pg.locator("body").screenshot(type="png")
        b.close()
    _keep(png)
    return png


def send_missions(title, blocks, caption=""):
    try:
        return send_photo(render_missions(title, blocks), caption)
    except Exception as ex:
        print(f"::warning title=telegram imatge::{type(ex).__name__}: {str(ex)[:200]}")
        return False


# --- Resum del matí (decisió del David, 12/11)
DCSS = MCSS + """
.res{font-weight:800;font-size:13px;border-radius:8px;padding:3px 9px}
.won{background:#16a34a}.lost{background:#dc2626}.unk{background:#52525b}
.t.ok img{outline:3px solid #22c55e}.t.ko img{outline:3px solid #ef4444;opacity:.75}
.sc{position:absolute;left:4px;top:4px;background:#0b0b0fdd;color:#fff;font-weight:800;border-radius:6px;padding:1px 6px;font-size:12px}
.mk{position:absolute;right:4px;top:4px;font-size:15px}
"""


def render_digest(title, blocks):
    from playwright.sync_api import sync_playwright
    e = _h.escape
    out = []
    for m in blocks:
        tiles = []
        for p in m["players"]:
            src = _img(p.get("pic"))
            body = f'<img src="{src}">' if src else f'<div class="nm">{e(p["name"])}</div>'
            ok = p.get("ok")
            tiles.append(f'<div class="t{" ok" if ok is True else " ko" if ok is False else ""}">{body}'
                         + (f'<span class="sc">{e(p["badge"])}</span>' if p.get("badge") else "")
                         + (f'<span class="mk">{"✅" if ok else "❌"}</span>' if ok is not None else "")
                         + (f'<div class="sub">{e(str(p.get("status") or "").lower())}</div>' if ok is None and p.get("status") else "")
                         + "</div>")
        w = m.get("won")
        res = ("GUANYADA" if w else "PERDUDA" if w is False else "EN JOC / ?") if m["kind"] == "set" else \
            f"{sum(1 for p in m['players'] if p.get('ok'))}/{len(m['players'])} ENCERTATS"
        score = f"{m['score']:.0f} / {m['target']}" if m.get("score") is not None and m.get("target") is not None else ""
        col = RAR_COL.get((m.get("tag") or "").lower(), "#a1a1aa")
        tag = (f"<div class='tag' style='color:{col};border-color:{col}'>{e(m['tag'].replace('_', ' '))}</div>" if m.get("tag") else "")
        out.append(f"<div class='m'><div class='mh'><div class='mt'>{e(m['title'])}</div>{tag}"
                   f"<div class='res {'won' if w else 'lost' if w is False else 'unk'}'>{res}</div></div>"
                   f"<div class='ms'>{e(score + (' punts' if score else '') + (m.get('desc') or ''))}</div><div class='r'>{''.join(tiles)}</div></div>")
    html = (f"<html><head><meta charset='utf-8'><style>{DCSS}</style></head><body><div class='w'><h1>☀️ {e(title)}</h1>{''.join(out)}"
            "<div class='lg'>Set: punts de cada carta i total / objectiu · Missions: ✅ pick encertat, ❌ fallat</div></div></body></html>")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": 600, "height": 400}, device_scale_factor=2)
        pg.set_content(html)
        png = pg.locator("body").screenshot(type="png")
        b.close()
    _keep(png)
    return png


def send_digest(title, blocks, caption=""):
    try:
        return send_photo(render_digest(title, blocks), caption)
    except Exception as ex:
        print(f"::warning title=telegram imatge::{type(ex).__name__}: {str(ex)[:200]}")
        return False
