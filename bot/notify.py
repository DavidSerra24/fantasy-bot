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


def ask(text, rows, reply_to=None):
    """Missatge amb botons (decisió del David, 20/11: «confirmar amb botons en comptes de comandes o respostes»).
    rows = [[(etiqueta, ordre), …], …]: en prémer un botó, el planificador (plan.telegram_commands) fa l'ordre com si
    el David l'hagués escrit («/ven Quique», «/nom A = B», «sí» a una Arena…). Les ordres es desen a
    state/tg_buttons.json (el callback_data de Telegram només admet 64 bytes). Torna l'id del missatge."""
    import secrets
    from bot.web import STATE_LOCK, load_json, save_json
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[notify] Telegram no configurat:", text)
        return None
    kb = []
    with STATE_LOCK:
        st = load_json("tg_buttons.json", {})
        for row in rows:
            r_ = []
            for label, cmd in row:
                if len(("c:" + cmd).encode()) <= 64:  # l'ordre va dins del botó (no depèn de l'estat de cap execució)
                    r_.append({"text": label[:60], "callback_data": "c:" + cmd})
                    continue
                k = secrets.token_hex(4)
                st[k] = {"cmd": cmd, "label": label}
                r_.append({"text": label[:60], "callback_data": "b:" + k})
            kb.append(r_)
        if len(st) > 400:  # només els últims
            st = dict(list(st.items())[-400:])
        save_json("tg_buttons.json", st)
    body = {"chat_id": chat, "text": text[:3900], "disable_web_page_preview": True}
    if kb:
        body["reply_markup"] = {"inline_keyboard": kb}
    if reply_to:
        body["reply_to_message_id"] = reply_to
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=body, timeout=20).json()
        if not r.get("ok"):
            print("::warning title=telegram botons::" + str(r)[:200])
        return (r.get("result") or {}).get("message_id")
    except Exception as e:
        print("::warning title=telegram botons::" + str(e)[:200])
        return None
