import datetime as dt
from bot import ff
sid = {"_order": ["Ararat-Armenia FC", "AZ", "Juventus FC", "Stade Rennais F.C."],
       "AZ": [[{"name": "Jari De Busser", "ps": 53, "pct": 90}], [{"name": "Peer Koopmeiners", "ps": 59, "pct": 90}, {"name": "Ro-Zangelo Daal", "ps": 62, "pct": 80}, {"name": "Dave Kwakman", "ps": 57, "pct": 70}]],
       "Ararat-Armenia FC": [[{"name": "Some Player", "ps": 40, "pct": 90}]]}
log = []
off = ff.official_lineups("europa-league", dt.datetime(2026, 10, 22, 16, 45, tzinfo=dt.timezone.utc), sid, log=log)
print("::notice title=e::" + str({k: v[:5] for k, v in off.items()}) + " " + str(log))
c = ff.candidates(sid, off)
print("::notice title=e::candidats amb onzes oficials: " + ", ".join(f"{x['si']} {x['ps']} ({x['pct']}%)" for x in c))
