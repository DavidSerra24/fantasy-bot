"""Prova: camp de la imatge de la carta a l'API de Sorare (anyCard.pictureUrl)."""
from bot.sorare import gql, token

tries = {
    "bench": """query { so5 { so5Fixture(sport: FOOTBALL, type: UPCOMING, eventType: CLASSIC) { so5Leaderboards { slug } } } }""",
}
fx = gql(tries["bench"], token=token())["so5"]["so5Fixture"]["so5Leaderboards"]
slug = fx[0]["slug"]
for f in ("pictureUrl", "pictureUrl(derivative: \"tinified\")", "avatarImageUrl"):
    q = """query($slug: String!) { so5 { so5Leaderboard(slug: $slug) { myBench(first: 2, includeUsed: true) { nodes {
        ... on ComposeTeamBenchCard { anyCard { slug %s } anyPlayer { displayName ... on Player { pictureUrl } } } } } } } }""" % f
    try:
        d = gql(q, {"slug": slug}, token=token())
        print(f"::notice title=pic {f}::" + str(d)[:1500])
    except Exception as e:
        print(f"::notice title=pic {f} ERR::" + str(e)[:500])
