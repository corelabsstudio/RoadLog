# -*- coding: utf-8 -*-
"""Diagnose why RoadLog deploy stays QUEUED; cancel stuck; re-trigger."""
import json
import subprocess
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
PROJECT = "9d3da15b-b2e6-4790-af3c-b0229e2d1965"
ENV = "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7"
SERVICE = "ebf3faf1-2f14-425a-acad-9cc2c67fa633"
WA_PROJECT = "2977b794-a0a8-42af-8ee5-add128046ae2"
WA_ENV = "2a3b69b2-441f-4369-9582-eaaa8e2c4f39"
WA_SERVICE = "32c989b1-4e9b-4057-adab-547bc8e2ebf1"


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
    with urllib.request.urlopen(req, timeout=90) as res:
        return json.loads(res.read().decode())


def list_svc(name, env, svc):
    r = gql(
        """
        query($e:String!,$s:String!) {
          deployments(first: 12, input: { environmentId: $e, serviceId: $s }) {
            edges {
              node {
                id status createdAt
              }
            }
          }
        }
        """,
        {"e": env, "s": svc},
    )
    edges = (((r.get("data") or {}).get("deployments") or {}).get("edges")) or []
    print(f"\n=== {name} ===")
    for e in edges:
        n = e["node"]
        print(f"  {n['status']:12} {n['id']}  {n['createdAt']}")
    return [e["node"] for e in edges]


# workspace / me
print("me:")
try:
    print(json.dumps(gql("{ me { id name email } }"), indent=2)[:500])
except Exception as ex:
    print(ex)

# project services
print("\nproject services:")
try:
    r = gql(
        """
        query($id: String!) {
          project(id: $id) {
            id name
            services { edges { node { id name } } }
            environments { edges { node { id name } } }
          }
        }
        """,
        {"id": PROJECT},
    )
    print(json.dumps(r, indent=2)[:2000])
except Exception as ex:
    print(ex)

rl = list_svc("RoadLog", ENV, SERVICE)
wa = list_svc("WakeAgain", WA_ENV, WA_SERVICE)

# cancel all non-terminal for RoadLog
active = [n for n in rl if n["status"] in ("QUEUED", "BUILDING", "DEPLOYING", "INITIALIZING", "WAITING")]
print("\nactive RL", len(active))
for n in active:
    print("cancel", n["id"], n["status"])
    print(gql("mutation($id:String!){ deploymentCancel(id:$id) }", {"id": n["id"]}))

sha = subprocess.check_output(
    ["git", "rev-parse", "HEAD"],
    cwd=r"C:\Users\hysoo\projects\RoadLog",
    text=True,
).strip()
print("\nredeploy", sha)
print(
    gql(
        """
        mutation($e:String!,$s:String!,$c:String!) {
          serviceInstanceDeployV2(environmentId:$e, serviceId:$s, commitSha:$c)
        }
        """,
        {"e": ENV, "s": SERVICE, "c": sha},
    )
)

# also try without commitSha
# print(gql('''mutation($e:String!,$s:String!){ serviceInstanceDeployV2(environmentId:$e, serviceId:$s) }''', {"e":ENV,"s":SERVICE}))
