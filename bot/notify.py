"""Enviament de missatges a Telegram."""
import os
import requests
from dotenv import load_dotenv

load_dotenv()


def telegram(text: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[notify] Telegram no configurat:", text)
        return False
    r = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat, "text": text, "disable_web_page_preview": True},
        timeout=20,
    )
    if not r.ok:
        print("::warning title=telegram::" + r.text[:200])
    return r.ok
