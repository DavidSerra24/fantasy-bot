"""Reconeixement (només lectura): plantilla de la finestra de venda (opció de cessió)."""
from bot.misterapi import MisterAPI

api = MisterAPI().login()
r = api.s.get("https://mister.mundodeportivo.com/views/ajax/sale.twig", timeout=20)
t = r.text
for i in range(0, min(len(t), 9 * 3800), 3800):
    print(f"::notice title=sale.twig {i // 3800}::" + t[i:i + 3800].replace("\n", " "))
