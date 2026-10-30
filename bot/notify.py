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
    parts, cur = [], ""
    for line in text.split("\n"):  # Telegram admet ~4096 caràcters per missatge: es parteix per línies
        while len(line) > 3900:
            parts.append(cur) if cur else None
            cur, parts = "", parts + [line[:3900]]
            line = line[3900:]
        if len(cur) + len(line) + 1 > 3900:
            parts.append(cur)
            cur = ""
        cur = (cur + "\n" + line) if cur else line
    if cur:
        parts.append(cur)
    ok = True
    for part in parts or [""]:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": part, "disable_web_page_preview": True},
            timeout=20,
        )
        if not r.ok:
            print("::warning title=telegram::" + r.text[:200])
        ok = ok and r.ok
    return ok
