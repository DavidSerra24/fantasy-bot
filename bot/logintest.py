"""Prova de configuració: Telegram i inicis de sessió (sense mostrar mai cap secret)."""
import os
from playwright.sync_api import sync_playwright
from bot.notify import telegram
from bot.web import new_context, save_session, login_sorareinside, login_futbolfantasy, login_predicted11


def main():
    lines = []
    for k in ["SI_EMAIL", "SI_PASSWORD", "FF_EMAIL", "FF_PASSWORD", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]:
        lines.append(f"{'✅' if os.getenv(k) else '➖'} secret {k} {'posat' if os.getenv(k) else 'no posat'}")
    os.makedirs("out", exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch()
        for site, fn, need in [("sorareinside", login_sorareinside, "SI_EMAIL"),
                               ("futbolfantasy", login_futbolfantasy, "FF_EMAIL"),
                               ("predicted11", login_predicted11, "FF_EMAIL")]:
            if not os.getenv(need):
                continue
            ctx = new_context(b, site)
            pg = ctx.new_page()
            try:
                r = fn(pg)
                save_session(ctx, site)
                lines.append(f"✅ {site}: {r}")
            except Exception as e:
                lines.append(f"❌ {site}: {type(e).__name__}: {str(e)[:150]}")
                try:
                    pg.screenshot(path=f"out/{site}.png")
                    lines.append(f"   url {site}: {pg.url}  text: {pg.inner_text('body')[:200]!r}")
                    ins = pg.evaluate("() => [...document.querySelectorAll('input,button')].map(e => e.tagName + ':' + (e.type||'') + ':' + (e.name||e.id||'') + ':' + (e.innerText||e.placeholder||'').slice(0,30)).join(' | ')")
                    lines.append(f"   formulari {site}: {ins[:400]}")
                except Exception:
                    pass
            ctx.close()
        b.close()
    ok = telegram("🤖 Hola David! Sóc el teu bot de fantasy. Prova de configuració:\n" + "\n".join(lines))
    lines.append(f"{'✅' if ok else '❌'} Telegram: missatge {'enviat' if ok else 'NO enviat'}")
    print("::notice title=login::" + " || ".join(l for l in lines if "secret" not in l))


if __name__ == "__main__":
    main()
