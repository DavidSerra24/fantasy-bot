"""Diagnosi: baixa l'esquema GraphQL de Sorare i en mostra les parts d'alineacions (només lectura)."""
import re
import requests

s = requests.get("https://api.sorare.com/graphql/schema", timeout=60).text
open("state/sorare_schema.graphql", "w").write(s)
print(f"::notice title=size::{len(s)} caràcters")


def block(name):
    m = re.search(r"\n(type|input|enum) " + re.escape(name) + r"\b[^{]*\{(.*?)\n\}", s, re.S)
    return (m.group(0) if m else f"(no {name})").replace("\n", " ¶ ")


mut = block("Mutation")
lines = [l for l in mut.split(" ¶ ") if re.search(r"lineup|so5|fantasy|compose", l, re.I)]
print("::notice title=mutations::" + " ¶ ".join(lines)[:6000])
for n in re.findall(r"input: (\w+Input)", " ".join(lines))[:6]:
    print(f"::notice title={n}::" + block(n)[:3000])
for n in ["CurrentUser", "FootballRoot", "So5Root", "So5Leaderboard", "So5Lineup", "So5Fixture"]:
    b = block(n)
    print(f"::notice title={n}::" + " ¶ ".join(x for x in b.split(" ¶ ") if not x.strip().startswith('"'))[:3500])
