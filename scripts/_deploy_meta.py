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
E = "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7"
S = "ebf3faf1-2f14-425a-acad-9cc2c67fa633"


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


# richer fields
queries = [
    """
    query {
      deployments(first: 3, input: {
        environmentId: "%s"
        serviceId: "%s"
      }) {
        edges {
          node {
            id status createdAt
            meta
            staticUrl
            canRedeploy
            url
          }
        }
      }
    }
    """
    % (E, S),
    """
    query {
      deployments(first: 2, input: {
        environmentId: "%s"
        serviceId: "%s"
      }) {
        edges {
          node {
            id status
            meta
          }
        }
      }
    }
    """
    % (E, S),
]

for i, q in enumerate(queries):
    print("===", i)
    print(json.dumps(gql(q), indent=2, ensure_ascii=False)[:3000])

# try redeploy mutations that might use cached source
print("=== try deploymentRedeploy latest SUCCESS if any")
r = gql(
    """
    query {
      deployments(first: 15, input: {
        environmentId: "%s"
        serviceId: "%s"
      }) {
        edges { node { id status createdAt } }
      }
    }
    """
    % (E, S)
)
edges = (((r.get("data") or {}).get("deployments") or {}).get("edges")) or []
for e in edges:
    n = e["node"]
    print(n["status"], n["id"][:8], n["createdAt"])
