"""Mister (mister.mundodeportivo.com): entrada i utilitats."""
import os

U = "https://mister.mundodeportivo.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"


def new_context(b):
    return b.new_context(locale="es-ES", timezone_id="Europe/Madrid", viewport={"width": 700, "height": 1270}, user_agent=UA)


def logged(pg):
    return "/feed" in pg.url or pg.locator(".btn-balance").count() > 0


def login(pg):
    """Entra al Mister; si alguna pantalla no apareix (la web va lenta), ho torna a provar fins a 3 vegades."""
    for i in range(3):
        try:
            return _login(pg)
        except Exception:
            if i == 2:
                raise
            pg.context.clear_cookies()
            pg.wait_for_timeout(20000)


def _login(pg):
    """Entra amb correu i contrasenya (secrets MISTER_EMAIL / MISTER_PASSWORD). Accepta les galetes (autoritzat pel David)."""
    for i in range(4):  # el Mister de vegades no respon a primera hora: fins a 4 intents en ~6 minuts
        try:
            pg.goto(U + "/feed", wait_until="domcontentloaded", timeout=60000)
            break
        except Exception:
            if i == 3:
                raise
            pg.wait_for_timeout(45000)
    pg.wait_for_timeout(3500)
    try:
        pg.locator("#didomi-notice-agree-button").click(timeout=6000)
        pg.wait_for_timeout(1500)
    except Exception:
        pass
    if logged(pg):
        return True
    for _ in range(4):
        btn = pg.get_by_text("Siguiente", exact=False).first
        if not (btn.count() and btn.is_visible()):
            break
        btn.click()
        pg.wait_for_timeout(1200)
    pg.get_by_text("Empezar", exact=False).first.click()
    pg.wait_for_timeout(2500)
    pg.get_by_text("Continuar con Email").first.click()
    pg.wait_for_timeout(2000)
    pg.locator("input[type=email]:visible").first.fill(os.environ["MISTER_EMAIL"])
    pg.locator("button[type=submit]:visible").last.click()
    pg.wait_for_timeout(2500)
    pg.get_by_text("Continuar con contraseña").first.click()
    pg.wait_for_timeout(2000)
    pg.locator("input[type=password]:visible").first.fill(os.environ["MISTER_PASSWORD"])
    pg.locator("button[type=submit]:visible").last.click()
    pg.wait_for_timeout(5000)
    if not logged(pg):
        raise RuntimeError(f"Mister: no he pogut entrar ({pg.url})")
    return True
