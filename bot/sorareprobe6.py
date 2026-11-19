"""Diagnosi (19/11): mode Pro de Sorare (tauler de carrera Pro, «Climb all season long»)."""
import json
from bot.sorare import gql, token

def q(query, v=None):
    try:
        return gql(query, v or {}, token=token())
    except Exception as e:
        return {"error": str(e)[:800]}

p = q("""query { currentUser { anyUserSportProfile(sport: FOOTBALL) { __typename proUnlocked } } }""")
print("::notice title=proUnlocked::" + json.dumps(p, ensure_ascii=False)[:1500])
STEP = """__typename id ... on CareerProStep { level target state ladderPoints
  displayedTypedRules { key descriptions { title items { title } } } myLineups { __typename id } }"""
for rar in (None, "limited", "rare"):
    d = q("""query($r: Rarity) { currentUser { boards(mode: CAREER, sport: FOOTBALL, rarity: $r) {
      __typename id title description featured endDate myCurrentStep { %s } } } }""" % STEP, {"r": rar})
    if rar:
        continue
    for b in ((d.get("currentUser") or {}).get("boards") or []):
        st = b.get("myCurrentStep") or {}
        rules = "; ".join(x["descriptions"][0]["title"] + (" (" + ", ".join(i["title"] for i in x["descriptions"][0]["items"]) + ")" if x["descriptions"][0]["items"] else "")
                          for x in st.get("displayedTypedRules") or [] if x.get("descriptions"))
        print(f"::notice title=Pro {b['title']}::{b['description']} · {st.get('__typename')} nivell {st.get('level')} objectiu {st.get('target')} "
              f"{st.get('state')} · alineacions {len(st.get('myLineups') or [])} · {rules}")
    if d.get("error"):
        print("::notice title=error::" + d["error"])
