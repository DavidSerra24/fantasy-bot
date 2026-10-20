"""Prova que el servidor funciona: obre Chromium i envia un Telegram."""
from playwright.sync_api import sync_playwright
from bot.notify import telegram


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto("https://www.predicted11.com", timeout=60000)
        title = pg.title()
        b.close()
    msg = f"✅ fantasy-bot funciona. Predicted11 respon: {title}"
    print(msg)
    telegram(msg)


if __name__ == "__main__":
    main()
