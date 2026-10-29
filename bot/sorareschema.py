"""Diagnosi: baixa l'esquema GraphQL de Sorare i el desa a la branca «sorare-schema» (només lectura de l'API)."""
import os
import subprocess
import requests

s = requests.get("https://api.sorare.com/graphql/schema", timeout=60).text
os.makedirs("docs", exist_ok=True)
open("docs/sorare_schema.graphql", "w").write(s)
cmds = [["git", "config", "user.name", "fantasy-bot"], ["git", "config", "user.email", "bot@users.noreply.github.com"],
        ["git", "checkout", "-B", "sorare-schema"], ["git", "add", "docs/sorare_schema.graphql"],
        ["git", "commit", "-qm", "Esquema de Sorare"], ["git", "push", "-qf", "origin", "sorare-schema"]]
for c in cmds:
    print(c, subprocess.run(c, capture_output=True, text=True).stderr[:200])
print(f"::notice title=schema::{len(s)} caràcters a la branca sorare-schema")
