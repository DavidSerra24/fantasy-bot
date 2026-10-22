import requests, json
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36"}
def note(m): print("::notice title=l::"+m[:900])
# ESPN
for lg,day in [("uefa.europa","20261022"),("ita.1","20261023"),("esp.1","20261023"),("esp.2","20261024"),("eng.1","20261024")]:
    try:
        r=requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/scoreboard?dates={day}",headers=H,timeout=20)
        ev=r.json().get("events",[])
        note(f"ESPN {lg} {day}: {r.status_code}, {len(ev)} partits; primer: {ev[0]['name'] if ev else '-'} {ev[0]['date'] if ev else ''}")
        if ev and lg=="uefa.europa":
            s=requests.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{lg}/summary?event={ev[0]['id']}",headers=H,timeout=20).json()
            ro=s.get("rosters",[])
            note(f"  rosters: {len(ro)} equips; " + " | ".join(f"{x['team']['displayName']}: " + ", ".join(p['athlete']['displayName'] for p in x.get('roster',[]) if p.get('starter'))[:200] for x in ro))
    except Exception as e: note(f"ESPN {lg}: ERROR {e}")
# FotMob
try:
    r=requests.get("https://www.fotmob.com/api/matches?date=20261022",headers=H,timeout=20)
    note(f"FotMob matches: {r.status_code} {r.text[:150]}")
except Exception as e: note(f"FotMob: ERROR {e}")
