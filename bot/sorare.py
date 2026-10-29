"""Sorare: entrada per l'API oficial (api.sorare.com/graphql) i consultes.

Entrada (python -m bot.sorare login):
  1. Correu + contrasenya (secrets SORARE_EMAIL / SORARE_PASSWORD; la contrasenya es xifra amb bcrypt i la sal de Sorare).
  2. Si el compte té 2FA, Sorare torna un «otpSessionChallenge»: el bot demana el codi al David per Telegram i
     l'espera (el David l'escriu al xat; el bot mai el genera ni l'escriu ell).
  3. Sorare retorna un JWT de 30 dies, que es desa XIFRAT a state/sorare_token.enc (clau derivada de la contrasenya).
Seguretat: aquest mòdul només llegeix dades i, més endavant, envia alineacions. Mai compra, ven, fa ofertes ni mou diners.
Ús: python -m bot.sorare login | me
"""
import base64
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time

import requests

from bot.notify import telegram
from bot.web import STATE

API = "https://api.sorare.com/graphql"
AUD = "fantasy-bot-david"
TOKEN_FILE = STATE / "sorare_token.enc"
UA = {"User-Agent": "fantasy-bot (DavidSerra24)", "Content-Type": "application/json"}


def _fernet():
    from cryptography.fernet import Fernet
    key = hashlib.sha256(("fantasy-bot|" + os.environ["SORARE_PASSWORD"]).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def save_token(tok, expires):
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_bytes(_fernet().encrypt(json.dumps({"token": tok, "exp": expires}).encode()))


def load_token():
    if not TOKEN_FILE.exists():
        return None
    try:
        return json.loads(_fernet().decrypt(TOKEN_FILE.read_bytes()))
    except Exception:
        return None


def gql(query, variables=None, token=None):
    h = dict(UA)
    if token:
        h["Authorization"] = f"Bearer {token}"
        h["JWT-AUD"] = AUD
    r = requests.post(API, json={"query": query, "variables": variables or {}}, headers=h, timeout=30)
    r.raise_for_status()
    j = r.json()
    if j.get("errors"):
        raise RuntimeError("Sorare: " + "; ".join(e.get("message", "") for e in j["errors"])[:300])
    return j["data"]


SIGNIN = """mutation SignIn($input: signInInput!) { signIn(input: $input) {
  currentUser { slug nickname } jwtToken(aud: "%s") { token expiredAt } otpSessionChallenge errors { message } } }""" % AUD


def wait_code(minutes=5):
    """Espera un codi de 6 xifres que el David escrigui al xat de Telegram."""
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    base = f"https://api.telegram.org/bot{token}"
    upd = requests.get(f"{base}/getUpdates", params={"timeout": 0}, timeout=20).json().get("result", [])
    offset = (upd[-1]["update_id"] + 1) if upd else 0  # només missatges nous
    end = time.time() + minutes * 60
    while time.time() < end:
        r = requests.get(f"{base}/getUpdates", params={"offset": offset, "timeout": 20}, timeout=30).json()
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            m = u.get("message") or {}
            if str((m.get("chat") or {}).get("id")) != str(chat):
                continue
            c = re.sub(r"\s", "", m.get("text") or "")
            if re.fullmatch(r"\d{6}", c):
                requests.get(f"{base}/getUpdates", params={"offset": offset, "timeout": 0}, timeout=20)  # confirmar
                return c
    return None


def login():
    import bcrypt
    email, pwd = os.environ["SORARE_EMAIL"], os.environ["SORARE_PASSWORD"]
    salt = requests.get(f"https://api.sorare.com/api/v1/users/{email}", headers=UA, timeout=20).json()["salt"]
    hashed = bcrypt.hashpw(pwd.encode(), salt.encode()).decode()
    d = gql(SIGNIN, {"input": {"email": email, "password": hashed}})["signIn"]
    if d.get("errors"):
        raise RuntimeError("Sorare no ha acceptat el correu/contrasenya: " + "; ".join(e["message"] for e in d["errors"]))
    if not d.get("jwtToken") and d.get("otpSessionChallenge"):
        telegram("🔐 Sorare: envia'm aquí el codi de 6 xifres de l'Authenticator (tens 5 minuts).")
        code = wait_code(5)
        if not code:
            telegram("⌛ Sorare: no he rebut el codi. Torna a llançar l'entrada quan vulguis.")
            raise RuntimeError("sense codi")
        d = gql(SIGNIN, {"input": {"otpSessionChallenge": d["otpSessionChallenge"], "otpAttempt": code}})["signIn"]
        if d.get("errors") or not d.get("jwtToken"):
            raise RuntimeError("Sorare no ha acceptat el codi: " + "; ".join(e["message"] for e in (d.get("errors") or [])))
    jt = d["jwtToken"]
    save_token(jt["token"], jt["expiredAt"])
    u = d.get("currentUser") or {}
    msg = f"✅ Sorare: dins com a {u.get('nickname') or u.get('slug')}. La clau caduca el {jt['expiredAt'][:10]}."
    print("::notice title=sorare::" + msg)
    telegram(msg)


def token():
    t = load_token()
    if not t:
        raise RuntimeError("Sorare: no hi ha clau d'accés; cal fer l'entrada (python -m bot.sorare login)")
    exp = dt.datetime.fromisoformat(t["exp"].replace("Z", "+00:00"))
    left = exp - dt.datetime.now(dt.timezone.utc)
    if left.total_seconds() <= 0:
        raise RuntimeError("Sorare: la clau ha caducat; cal tornar a fer l'entrada")
    if left < dt.timedelta(days=3):
        telegram(f"🔐 Sorare: la clau caduca el {t['exp'][:10]}. Llança l'entrada de Sorare i envia'm el codi quan te'l demani.")
    return t["token"]


def me():
    d = gql("query { currentUser { slug nickname } }", token=token())
    msg = f"Sorare: connectat com a {d['currentUser']['nickname']} ({d['currentUser']['slug']})"
    print("::notice title=sorare::" + msg)
    return d


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "me"
    {"login": login, "me": me}[cmd]()
