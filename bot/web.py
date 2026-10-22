"""Navegador (Playwright), sessions desades i inicis de sessió.

Les credencials vénen de variables d'entorn (GitHub Secrets o .env del servidor):
  SI_EMAIL / SI_PASSWORD   -> SorareInside
  FF_EMAIL / FF_PASSWORD   -> FutbolFantasy i Predicted11 (mateix compte)
"""
import json
import os
import pathlib

from dotenv import load_dotenv

load_dotenv()
ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = ROOT / "state"
STATE.mkdir(exist_ok=True)
JS = ROOT / "bot" / "js"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")


class LoginError(RuntimeError):
    pass


def new_context(browser, site):
    path = STATE / f"session_{site}.json"
    kw = dict(locale="es-ES", timezone_id="Europe/Madrid", user_agent=UA,
              viewport={"width": 1280, "height": 900})
    if path.exists():
        kw["storage_state"] = str(path)
    return browser.new_context(**kw)


def save_session(ctx, site):
    ctx.storage_state(path=str(STATE / f"session_{site}.json"))


def inject(page, name):
    page.evaluate((JS / f"{name}.js").read_text(encoding="utf-8"))


def _fill_login(page, user, pwd):
    """Omple un formulari d'usuari + contrasenya genèric i l'envia."""
    pw = page.locator("input[type=password]").first
    pw.wait_for(timeout=20000)
    form = pw.locator("xpath=ancestor::form[1]")
    scope = form if form.count() else page
    user_in = scope.locator("input[type=email], input[name*=mail i], input[name*=user i], input[type=text]").first
    user_in.fill(user)
    pw.fill(pwd)
    btn = scope.locator("button[type=submit], input[type=submit]").first
    if btn.count():
        btn.click()
    else:
        pw.press("Enter")
    page.wait_for_timeout(4000)


def login_sorareinside(page):
    page.goto("https://sorareinside.com/lineups", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    if page.locator("text=Manage Lineups").count() or page.locator("text=Account").count():
        return "ja connectat"
    user, pwd = os.getenv("SI_EMAIL"), os.getenv("SI_PASSWORD")
    if not user or not pwd:
        raise LoginError("Falten SI_EMAIL / SI_PASSWORD")
    page.goto("https://sorareinside.com/login", wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    _fill_login(page, user, pwd)
    page.goto("https://sorareinside.com/lineups", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    if not (page.locator("text=Manage Lineups").count() or page.locator("text=Account").count()):
        raise LoginError("No s'ha pogut entrar a SorareInside")
    return "connectat"


def login_predicted11(page):
    page.goto("https://www.predicted11.com/es/login", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    if "login" not in page.url:
        return "ja connectat"
    user, pwd = os.getenv("FF_EMAIL"), os.getenv("FF_PASSWORD")
    if not user or not pwd:
        raise LoginError("Falten FF_EMAIL / FF_PASSWORD")
    _fill_login(page, user, pwd)
    if "login" in page.url and page.locator("input[type=password]").count():
        raise LoginError("No s'ha pogut entrar a Predicted11")
    return "connectat"


def login_futbolfantasy(page):
    page.goto("https://www.futbolfantasy.com/fantasy/perfil", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    if "login" not in page.url and not page.locator("input[type=password]").count():
        return "ja connectat"
    user, pwd = os.getenv("FF_EMAIL"), os.getenv("FF_PASSWORD")
    if not user or not pwd:
        raise LoginError("Falten FF_EMAIL / FF_PASSWORD")
    page.goto("https://www.futbolfantasy.com/login", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    _fill_login(page, user, pwd)
    page.goto("https://www.futbolfantasy.com/fantasy/perfil", wait_until="domcontentloaded")
    if "login" in page.url:
        raise LoginError("No s'ha pogut entrar a FutbolFantasy")
    return "connectat"


def load_json(name, default=None):
    p = STATE / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else (default if default is not None else {})


def save_json(name, data):
    (STATE / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
