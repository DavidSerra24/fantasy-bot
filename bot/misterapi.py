"""Mister per l'API interna de la web (sense navegador): més ràpid. Si alguna cosa falla, el bot fa servir el navegador
(pla B, el de sempre).

Com funciona la web (descobert del seu codi, 30/10):
- Entrada: POST /api2/auth/email?state=… {email, password} → token; POST /api2/auth/external/exchange-token {token}
  → galeta de sessió. Totes les crides /ajax/* són POST amb la capçalera X-Auth (= _FG_cfg.auth de la pàgina).
- Finestres: ajax/player-community-info (id_player, popup=bid|sale…) torna l'HTML de la finestra; el botó «#btn-send»
  porta data-ajax = l'acció (ajax/<acció>) i el formulari de la finestra són les dades.
- Ofertes: ajax/offer (dades del botó). Alineació: ajax/sub-do, ajax/formation, capità:
  POST /forge/bemanager/managers/{id}/lineup/captain {slot_index}. Quiniela: ajax/pools (el botó triat porta la classe «mine»).
Seguretat: només fa el que fa el bot amb el navegador (pujes, vendes, ofertes, alineació, quiniela). Mai res de pagament
(crèdits, botiga, compres).
"""
import base64
import json
import os
import re

import requests

U = "https://mister.mundodeportivo.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"
FORBIDDEN = re.compile(r"store|credit|buy|paypal|purchase|video_reward|pool/buy", re.I)  # res de pagament


class MisterAPI:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "ca,es;q=0.9"})
        self.auth = None

    def login(self):
        self.s.get(U + "/feed", timeout=30)
        state = base64.b64encode(json.dumps({"method": "email", "platform": "web", "userAgent": UA}).encode()).decode()
        r = self.s.post(f"{U}/api2/auth/email?state={state}", json={"email": os.environ["MISTER_EMAIL"], "password": os.environ["MISTER_PASSWORD"]},
                        headers={"X-Requested-With": "XMLHttpRequest"}, timeout=30)
        r.raise_for_status()
        tok = r.json().get("token")
        if not tok:
            raise RuntimeError("Mister API: l'entrada no ha tornat cap token")
        r = self.s.post(f"{U}/api2/auth/external/exchange-token", json={"token": tok}, headers={"X-Requested-With": "XMLHttpRequest"}, timeout=30)
        r.raise_for_status()
        self.page("/feed")
        if not self.auth:
            raise RuntimeError("Mister API: sense X-Auth després d'entrar")
        return self

    def page(self, path):
        """HTML d'una pàgina (i n'actualitza la clau X-Auth)."""
        r = self.s.get(U + path, timeout=30)
        r.raise_for_status()
        m = re.search(r'"auth"\s*:\s*"([^"]+)"', r.text)
        if m:
            self.auth = m.group(1)
        return r.text

    def community(self, cid):
        self.page(f"/action/change?id_community={cid}")

    def sync(self):
        """Quan el navegador comparteix la sessió, la web pot renovar-ne la galeta i la clau: es copien del navegador."""
        pg = getattr(self, "pg", None)
        if pg is None:
            return
        for c in pg.context.cookies():
            if "mundodeportivo" in c.get("domain", ""):
                self.s.cookies.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
        try:
            a = pg.evaluate("() => (window._FG_cfg && _FG_cfg.auth) || null")
            if a:
                self.auth = a
        except Exception:
            pass

    def ajax(self, action, data=None, retry=True):
        if FORBIDDEN.search(action):
            raise RuntimeError(f"Mister API: acció prohibida ({action})")
        self.sync()
        r = self.s.post(f"{U}/ajax/{action.lstrip('/')}", data=data or {}, timeout=30,
                        headers={"X-Auth": self.auth or "", "X-Requested-With": "XMLHttpRequest", "Referer": U + "/market"})
        if r.status_code == 401 and retry:
            self.page("/feed")  # clau nova
            return self.ajax(action, data, retry=False)
        if r.status_code >= 400:
            raise RuntimeError(f"Mister API {action}: HTTP {r.status_code} {r.text[:200]}")
        try:
            return r.json()
        except ValueError:
            return {"status": "html", "html": r.text}

    def cookies_for_browser(self):
        """Galetes per passar la sessió al navegador (entrada ràpida sense pantalles)."""
        return [{"name": c.name, "value": c.value, "domain": c.domain or "mister.mundodeportivo.com", "path": c.path or "/",
                 "secure": bool(c.secure), "httpOnly": False} for c in self.s.cookies]

    # -- lectures --
    def balance(self):
        d = self.ajax("balance").get("data") or {}
        return d  # {current, future, maxDebt}

    def popup(self, pid, kind):
        """HTML de la finestra d'un jugador (bid, sale…), sense enviar res."""
        d = self.ajax("player-community-info", {"id_player": pid, "popup": kind})
        return d.get("data") if isinstance(d.get("data"), (str, dict)) else d

    # -- accions (finestra + #btn-send) --
    @staticmethod
    def form_of(html):
        """Dades del formulari de la finestra (inputs) i l'acció del botó «#btn-send» (data-ajax)."""
        html = html if isinstance(html, str) else json.dumps(html)
        act = re.search(r'id="btn-send"[^>]*data-ajax="([^"]+)"|data-ajax="([^"]+)"[^>]*id="btn-send"', html)
        fields = {}
        for m in re.finditer(r"<input[^>]*>", html):
            tag = m.group(0)
            n = re.search(r'name="([^"]+)"', tag)
            v = re.search(r'value="([^"]*)"', tag)
            if n:
                fields[n.group(1)] = v.group(1) if v else ""
        return (act.group(1) or act.group(2)) if act else None, fields

    # -- accions del mercat (mateixos formularis que la web: bid.twig, sale.twig, offers) --
    def _pre(self, pid, kind):
        d = self.ajax("player-community-info", {"id_player": pid, "popup": kind})
        pre = d.get("data")
        if not isinstance(pre, dict):
            raise RuntimeError(f"Mister API: finestra {kind} de {pid} sense dades")
        return pre

    @staticmethod
    def _ok(d, what):
        if not isinstance(d, dict) or d.get("status") != "ok":
            raise RuntimeError(f"Mister API {what}: {str(d)[:200]}")
        return d

    def bid(self, pid, amount=None, dry=False):
        """Puja (pel preu mínim si no es diu l'import). Retorna (True, màxim permès)."""
        pre = self._pre(pid, "bid")
        market = pre.get("market") or {}
        b = pre.get("bid") or {}
        price = int(amount or (b.get("input") if b.get("isActive") == 1 else 0) or market.get("price") or pre.get("value"))
        action = "remove" if (b.get("type") == "normal" and b.get("isActive") == 1 and False) else ("update" if b.get("isActive") == 1 else "bid")
        data = {"offeree_id": (pre.get("owner") or {}).get("id") or "", "id_market": market.get("id") or 0, "id_player": pid,
                "action": action, "barter": "", "bid": price, "bid_range": price}
        mx = (self.balance() or {}).get("maxDebt")
        if dry:
            return True, mx, data
        self._ok(self.ajax("bid", data), "puja")
        return True, mx

    def withdraw(self, pid, dry=False):
        """Retira la meva puja."""
        pre = self._pre(pid, "bid")
        market = pre.get("market") or {}
        data = {"offeree_id": (pre.get("owner") or {}).get("id") or "", "id_market": market.get("id") or 0, "id_player": pid,
                "action": "remove", "barter": "", "bid": market.get("price") or 0}
        if dry:
            return data
        self._ok(self.ajax("bid", data), "retirar la puja")
        return True

    def sell(self, pid, price=None, dry=False):
        """Posa en venda pel preu mínim (= valor)."""
        pre = self._pre(pid, "sale")
        if (pre.get("market") or {}).get("id"):
            return True  # ja és en venda
        data = {"id_player": pid, "action": "sale", "price": int(price or pre.get("value"))}
        if dry:
            return data
        self._ok(self.ajax("sale", data), "posar en venda")
        return True

    def unsell(self, pid, dry=False):
        """Treu de la venda."""
        pre = self._pre(pid, "sale")
        if not (pre.get("market") or {}).get("id"):
            return True
        data = {"id_player": pid, "action": "remove", "price": (pre.get("market") or {}).get("price") or pre.get("value")}
        if dry:
            return data
        self._ok(self.ajax("sale", data), "treure de la venda")
        return True

    def loanable(self, pid, on=True, dry=False):
        """Marca (o desmarca) un jugador meu com a cedible durant 72 h (finestra «Ceder»: ajax/loanable, action add|remove)."""
        pre = self._pre(pid, "loanable")
        cur = bool((pre.get("market") or {}).get("loanable"))
        if cur == on:
            return "ja"
        data = {"id_player": pid, "action": "add" if on else "remove"}
        if dry:
            return data
        self._ok(self.ajax("loanable", data), "marcar com a cedible")
        return True

    def accept_offer(self, id_bid, amount, dry=False):
        data = {"id_bid": id_bid, "type": "accept", "amount": int(amount)}
        if dry:
            return data
        self._ok(self.ajax("offer", data), "acceptar l'oferta")
        return True


API = None  # sessió compartida (la crea bot.mister.login); si és None, tot es fa amb el navegador


def use(fn_name, *a, **k):
    """Fa una acció per l'API; si no hi ha API o falla, torna None (i el bot fa servir el navegador, pla B)."""
    if API is None:
        return None
    try:
        return getattr(API, fn_name)(*a, **k)
    except Exception as e:
        print(f"::warning title=Mister API {fn_name}::{str(e)[:300]} → faig servir el navegador")
        return None
