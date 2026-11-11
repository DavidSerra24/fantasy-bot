"""Prova: camps de resultat de les alineacions del Set i de les missions (score, estat…)."""
from bot.sorare import gql, token

base = """query($m: BoardMode!, $sp: Sport!) { currentUser { setBoard(mode: $m, sport: $sp) { id title
  myCurrentStep { id level state target myLineups { ... on TaskLineup { id aasmState %s
    taskAppearances { ... on TaskAppearanceInterface { anyPlayer { displayName } %s } } } } } } } }"""
for lf, af in (("score", ""), ("totalScore", ""), ("", "score"), ("", "status"), ("", "playerGameScore { score }"),
               ("completed", ""), ("succeeded", ""), ("rank", "")):
    try:
        d = gql(base % (lf, af), {"m": "CAREER", "sp": "FOOTBALL"}, token=token())
        print(f"::notice title=set {lf or af}::" + str(d)[:1200])
    except Exception as e:
        print(f"::notice title=set {lf or af} ERR::" + str(e)[:300])
q2 = """query { currentUser { setBoard(mode: CAREER, sport: FOOTBALL) { id steps { id level state target } } } }"""
for q in (q2, q2.replace("steps", "allSteps"), q2.replace("steps { id level state target }", "pastSteps { id level state }")):
    try:
        print("::notice title=steps::" + str(gql(q, token=token()))[:1500])
    except Exception as e:
        print("::notice title=steps ERR::" + str(e)[:300])
