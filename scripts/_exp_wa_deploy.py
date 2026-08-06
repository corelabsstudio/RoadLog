# -*- coding: utf-8 -*-
"""Experiment: redeploy WakeAgain HEAD and compare status to RoadLog."""
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
WA = ("2a3b69b2-441f-4369-9582-eaaa8e2c4f39", "32c989b1-4e9b-4057-adab-547bc8e2ebf1")
RL = ("367f2cc2-ac64-4daf-b04d-0d28f4ac97c7", "ebf3faf1-2f14-425a-acad-9cc2c67fa633")


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


def list_deps(env, svc, n=4):
    r = gql(
        """
        query($e: String!, $s: String!, $n: Int!) {
          deployments(first: $n, input: { environmentId: $e, serviceId: $s }) {
            edges { node { id status createdAt } }
          }
        }
        """,
        {"e": env, "s": svc, "n": n},
    )
    return [e["node"] for e in r["data"]["deployments"]["edges"]]


sha = subprocess.check_output(
    ["git", "rev-parse", "HEAD"],
    cwd=r"C:\Users\hysoo\projects\WakeAgain",
    text=True,
).strip()
print("WA sha", sha)

for d in list_deps(*WA, 8):
    if d["status"] in (
        "QUEUED",
        "BUILDING",
        "DEPLOYING",
        "INITIALIZING",
        "WAITING",
    ):
        print("cancel WA", d["id"], d["status"])
        print(gql("mutation($id: String!) { deploymentCancel(id: $id) }", {"id": d["id"]}))

r = gql(
    """
    mutation($e: String!, $s: String!, $c: String!) {
      serviceInstanceDeployV2(environmentId: $e, serviceId: $s, commitSha: $c)
    }
    """,
    {"e": WA[0], "s": WA[1], "c": sha},
)
print("deploy", r)

for name, pair in [("WA", WA), ("RL", RL)]:
    print(f"=== {name} ===")
    for d in list_deps(*pair, 4):
        print(f"  {d['status']:12} {d['id'][:8]}  {d['createdAt']}")
