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
    if r.status_code >= 400:
        raise RuntimeError(f"Sorare HTTP {r.status_code}: {r.text[:500]}")
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
    if d.get("errors") and not d.get("otpSessionChallenge"):  # «2fa_missing» ve amb el challenge: cal el codi
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


def schema():
    """Exploració (només lectura) de l'esquema de l'API: camps de l'usuari i mutacions d'alineacions."""
    t = token()
    d = gql("""{ cu: __type(name: "CurrentUser") { fields { name args { name } type { name kind ofType { name } } } }
                 m: __schema { mutationType { fields { name args { name type { name ofType { name } } } } } } }""", token=t)
    cu = ", ".join(f["name"] for f in d["cu"]["fields"])
    muts = [f for f in d["m"]["mutationType"]["fields"] if re.search(r"lineup|so5|fantasy|compose|team", f["name"], re.I)]
    print("::notice title=CurrentUser::" + cu[:5000])
    print("::notice title=mutations::" + " | ".join(f["name"] + "(" + ",".join(a["name"] + ":" + str((a["type"] or {}).get("name") or ((a["type"] or {}).get("ofType") or {}).get("name")) for a in f["args"]) + ")" for f in muts)[:5000])


LEADERBOARDS = """query { so5 { futureLeaderboardsPaginated(rarities: [LIMITED, RARE], first: 200) { nodes {
  id slug displayName mainRarityType isArena division gameWeek cutOffDate format { title } canCompose { value reason missingPositions } } } } }"""

BENCH = """query($slug: String!) { so5 { so5Leaderboard(slug: $slug) { displayName myBench(first: 200) { nodes {
  ... on ComposeTeamBenchCard { id averageScore(type: LAST_FIFTEEN_SO5_AVERAGE_SCORE)
    anyCard { slug rarityTyped xp seasonYear inSeasonEligible }
    anyPlayer { displayName slug age activeClub { name slug }
      ... on Player { position nextClassicFixtureProjectedGrade { grade score } nextClassicFixturePlayingStatusOdds { starterOddsBasisPoints } } }
    eligiblePlayerGameScores(so5LeaderboardSlug: $slug) { projection { grade score }
      anyPlayerGameStats { ... on PlayerGameStats { footballPlayingStatusOdds(newVersion: false) { starterOddsBasisPoints reliability } } } } } } } } } }"""


def leaderboards():
    return gql(LEADERBOARDS, token=token())["so5"]["futureLeaderboardsPaginated"]["nodes"]


def bench(slug):
    return gql(BENCH, {"slug": slug}, token=token())["so5"]["so5Leaderboard"]["myBench"]["nodes"]


def explore():
    """Només lectura: competicions Classic de la propera jornada (Limited i Rare) i, per a una, les cartes elegibles."""
    lbs = [l for l in leaderboards() if not l["isArena"] and l["slug"].startswith("football")]
    print("::notice title=leaderboards::" + " ¶ ".join(f"{l['displayName']} | {l['mainRarityType']} | div{l['division']} | GW{l['gameWeek']} | {l['cutOffDate'][:16]} | {l['format']['title']} | compose={l['canCompose']['value']} {l['canCompose'].get('reason') or ''} | {l['slug']}" for l in lbs)[:9000])
    arenas = [l for l in leaderboards() if l["isArena"] and "beginner" in l["slug"]]
    print("::notice title=arenas::" + " ¶ ".join(f"{l['displayName']} | {l['mainRarityType']} | {l['slug']}" for l in arenas)[:3000])
    champ = next((l for l in lbs if l["displayName"].startswith("Champion") and l["mainRarityType"] == "limited"), lbs[0] if lbs else None)
    if champ:
        nodes = [n for n in bench(champ["slug"]) if n]
        rows = []
        for n in nodes:
            p_ = n["anyPlayer"]; g = (p_.get("nextClassicFixtureProjectedGrade") or {}); o = (p_.get("nextClassicFixturePlayingStatusOdds") or {})
            eg = (n.get("eligiblePlayerGameScores") or [{}])[0] or {}
            if not o.get("starterOddsBasisPoints"):
                o = ((eg.get("anyPlayerGameStats") or {}).get("footballPlayingStatusOdds") or {})
            g = g or (eg.get("projection") or {})
            rows.append(f"{p_['displayName']} ({(p_.get('activeClub') or {}).get('name')}, {p_.get('position')}, {p_.get('age')}a) | {g.get('grade')} {g.get('score')} | {(o.get('starterOddsBasisPoints') or 0)/100:.0f}% | mitj {n.get('averageScore')} | xp {n['anyCard']['xp']} | {n['anyCard']['slug']}")
        print(f"::notice title=bench {champ['displayName']}::" + " ¶ ".join(rows)[:9000])
        fx = gql("""query { so5 { so5Fixture(sport: FOOTBALL, type: UPCOMING, eventType: CLASSIC) { slug gameWeek cutOffDate
            so5Leaderboards { displayName mainRarityType isArena slug format { title } } } } }""", token=token())["so5"]["so5Fixture"]
        print("::notice title=fixture::" + f"{fx['slug']} GW{fx['gameWeek']} {fx['cutOffDate']} ¶ " + " ¶ ".join(f"{l['displayName']} | {l['mainRarityType']} | {l['format']['title']} | {l['slug']}" for l in fx["so5Leaderboards"] if not l["isArena"] and l["mainRarityType"] in ("limited", "rare"))[:8000])
        from collections import Counter
        print("::notice title=rarities::" + str(Counter((l["mainRarityType"], l["format"]["title"], l["slug"].split("-")[0]) for l in leaderboards())))


def probe():
    """Diagnosi: què diu FotMob d'un partit futur (lineupType)."""
    from bot import fotmob
    from bot.sorarelineup import GAME
    for gid in ("Game:b2dcee25-00d8-474f-a791-5bfe3ab8b08d", "Game:ef21aa68-0f7e-4b32-a6bf-c423050a82ab"):
        gm = gql(GAME, {"id": gid.split(":", 1)[-1]}, token=token())["football"]["game"]
        import datetime as dt
        when = dt.datetime.fromisoformat(gm["date"].replace("Z", "+00:00"))
        mid = fotmob.find(gm["homeTeam"]["name"], gm["awayTeam"]["name"], when)
        lu = requests.get(f"https://www.fotmob.com/api/data/matchDetails?matchId={mid}", headers=fotmob.H, timeout=20).json()["content"].get("lineup") or {}
        print(f"::notice title={gm['homeTeam']['name']}::{gm['date']} fotmob {mid} type {lu.get('lineupType')!r} source {lu.get('source')!r} keys {list(lu.keys())} filters {lu.get('availableFilters')}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "me"
    try:
        {"login": login, "me": me, "schema": schema, "explore": explore, "probe": probe, "lineups": lambda: __import__("bot.sorarelineup", fromlist=["run"]).run("dry"),
         "fill": lambda: __import__("bot.sorarelineup", fromlist=["run"]).run("fill"),
         "final": lambda: __import__("bot.sorarelineup", fromlist=["run"]).run("final")}[cmd]()
    except Exception as e:
        import traceback
        print("::error title=sorare::" + traceback.format_exc().replace("\n", " | ")[-1500:])
        if cmd == "login":  # les proves (me, schema…) no avisen per Telegram
            telegram(f"❌ Sorare: {type(e).__name__}: {str(e)[:300]}")
        raise
