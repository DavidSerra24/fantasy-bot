"""Manual: llegeix ara les respostes de Telegram (/nom, /p11, /mister…) i torna a fer el que digui `args`
(p. ex. «p11 laliga» o «ff laliga»), perquè les respostes entrin abans del tancament."""
import datetime as dt
import sys

from bot import plan

now = dt.datetime.now(dt.timezone.utc)
acts = plan.telegram_commands(now)
print(f"::notice title=respostes::llegides; accions noves: {[a['do'] for a in acts]}")
args = sys.argv[1:]
for i in range(0, len(args), 2):
    what, comp = args[i], args[i + 1] if i + 1 < len(args) else None
    if what == "p11":
        from bot import p11
        p11.run([comp], force=False, max_hours=99)
    elif what == "ff":
        from bot import ff
        ff.run(max_hours=6, only=[comp], final=True)
