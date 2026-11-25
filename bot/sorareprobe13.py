"""Quina missió és una tasca (25/11)."""
import json, sys
from bot.sorare import gql, token
tid = sys.argv[2] if len(sys.argv) > 2 else "5aacc768-e69f-415e-b2f6-e1c0d59bdbc6"
Q = """query($id: ID!) { currentUser { task(id: $id) { __typename ... on TaskInterface { id title description aasmState }
  ... on ThresholdPickerTask { taskAppearances { anyPlayer { displayName } status } } } } }"""
try:
    print("::notice title=missió::" + json.dumps(gql(Q, {"id": tid}, token=token()), ensure_ascii=False)[:2500])
except Exception as e:
    Q2 = """query($id: ID!) { currentUser { task(id: $id) { __typename ... on TaskInterface { id title description aasmState } } } }"""
    print("::notice title=missió::" + str(e)[:300] + " ¶ " + json.dumps(gql(Q2, {"id": tid}, token=token()), ensure_ascii=False)[:2000])
