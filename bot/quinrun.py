"""Manual: posa una quiniela com si el David l'hagués enviat per Telegram (Predicted11 + Mister si toca).
Ús: python -m bot.quinrun laliga "Sevilla 2-0 Alavés; Málaga 1-1 Racing" """
import sys

from bot import misterpool, quiniela
from bot.notify import telegram

comp, text = sys.argv[1], " ".join(sys.argv[2:])
quiniela.run(comp, text)
if comp in misterpool.POOLS:
    lines = misterpool.run(comp, quiniela.parse(text))
    for l in lines:
        print("::notice title=pool::" + l)
    if lines:
        telegram("\n".join(lines))
