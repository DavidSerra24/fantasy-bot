"""Comprova si les webs responen des d'aquest ordinador (GitHub Actions o servidor)."""
import os
from playwright.sync_api import sync_playwright
from bot.notify import telegram

SITES = {
    "Predicted11": "https://www.predicted11.com/es/champions",
    "FutbolFantasy": "https://www.futbolfantasy.com/fantasy",
    "SorareInside": "https://sorareinside.com/lineups",
    "Sorare": "https://sorare.com/football",
    "Mister Fantasy": "https://mister.mundodeportivo.com",
    "SorareScore": "https://www.sorarescore.com",
}


def main():
    os.makedirs("out", exist_ok=True)
    lines = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(locale="es-ES", timezone_id="Europe/Madrid",
                            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                        "(KHTML, like Gecko) Chrome/129.0 Safari/537.36"))
        for name, url in SITES.items():
            pg = ctx.new_page()
            try:
                r = pg.goto(url, timeout=45000, wait_until="domcontentloaded")
                pg.wait_for_timeout(4000)
                title = pg.title()
                body = pg.inner_text("body")[:300].replace("\n", " ")
                blocked = any(w in (title + body).lower() for w in
                              ["just a moment", "access denied", "attention required", "captcha", "forbidden"])
                status = r.status if r else "?"
                lines.append(f"{'❌' if blocked or (isinstance(status,int) and status>=400) else '✅'} {name}: {status} · {title[:60]}")
                pg.screenshot(path=f"out/{name}.png")
            except Exception as e:
                lines.append(f"❌ {name}: {type(e).__name__} {str(e)[:120]}")
            pg.close()
        b.close()
    msg = "🔎 Prova d'accés des de GitHub:\n" + "\n".join(lines)
    print(msg)
    telegram(msg)


if __name__ == "__main__":
    main()
