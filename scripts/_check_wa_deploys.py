# -*- coding: utf-8 -*-
import json
import urllib.request
from pathlib import Path

tok = (
    Path(r"C:\Users\hysoo\projects\RoadLog\.launch\railway.token")
    .read_text(encoding="utf-8-sig")
    .strip()
    .splitlines()[0]
    .strip()
    .strip('"')
    .strip("'")
)
GQL = "https://backboard.railway.app/graphql/v2"
pairs = [
    ("RL", "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7", "ebf3faf1-2f14-425a-acad-9cc2c67fa633"),
    ("WA", "2a3b69b2-441f-4369-9582-eaaa8e2c4f39", "32c989b1-4e9b-4057-adab-547bc8e2ebf1"),
]


def gql(q, v=None):
    body = json.dumps({"query": q, "variables": v or {}}).encode()
    req = urllib.request.Request(
        GQL,
        data=body,
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read().decode())


for name, e, s in pairs:
    r = gql(
        """
        query($e:String!,$s:String!) {
          deployments(first: 5, input: { environmentId: $e, serviceId: $s }) {
            edges { node { id status createdAt } }
          }
        }
        """,
        {"e": e, "s": s},
    )
    print(f"=== {name} ===")
    for edge in r["data"]["deployments"]["edges"]:
        n = edge["node"]
        print(f"  {n['status']:12} {n['id'][:8]}  {n['createdAt']}")
