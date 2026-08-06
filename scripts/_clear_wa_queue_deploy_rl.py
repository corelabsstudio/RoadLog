# -*- coding: utf-8 -*-
"""Cancel WakeAgain QUEUED (free trial slot), ensure RoadLog deploy is building."""
import json
import subprocess
import time
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
RL = ("367f2cc2-ac64-4daf-b04d-0d28f4ac97c7", "ebf3faf1-2f14-425a-acad-9cc2c67fa633")
WA = ("2a3b69b2-441f-4369-9582-eaaa8e2c4f39", "32c989b1-4e9b-4057-adab-547bc8e2ebf1")


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


def list_deps(env, svc):
    r = gql(
        """
        query($e:String!,$s:String!) {
          deployments(first: 8, input: { environmentId: $e, serviceId: $s }) {
            edges { node { id status createdAt } }
          }
        }
        """,
        {"e": env, "s": svc},
    )
    edges = (((r.get("data") or {}).get("deployments") or {}).get("edges")) or []
    return [e["node"] for e in edges]


def cancel(dep_id):
    return gql("mutation($id:String!){ deploymentCancel(id:$id) }", {"id": dep_id})


# Cancel ALL non-terminal on both
for name, (env, svc) in [("RL", RL), ("WA", WA)]:
    deps = list_deps(env, svc)
    print(name, [(d["id"][:8], d["status"]) for d in deps[:5]])
    for d in deps:
        if d["status"] in (
            "QUEUED",
            "BUILDING",
            "DEPLOYING",
            "INITIALIZING",
            "WAITING",
        ):
            print(" cancel", name, d["id"], d["status"], cancel(d["id"]))

time.sleep(3)

sha = subprocess.check_output(
    ["git", "rev-parse", "HEAD"],
    cwd=r"C:\Users\hysoo\projects\RoadLog",
    text=True,
).strip()
print("deploy RL", sha)
r = gql(
    """
    mutation($e:String!,$s:String!,$c:String!) {
      serviceInstanceDeployV2(environmentId:$e, serviceId:$s, commitSha:$c)
    }
    """,
    {"e": RL[0], "s": RL[1], "c": sha},
)
print(r)
new_id = ((r.get("data") or {}).get("serviceInstanceDeployV2"))
print("new_id", new_id)

for i in range(40):
    deps = list_deps(*RL)
    line = " | ".join(f"{d['id'][:8]}:{d['status']}" for d in deps[:4])
    print(f"[{i}] {line}", flush=True)
    if new_id:
        t = next((d for d in deps if d["id"] == new_id), None)
        if t and t["status"] in ("SUCCESS", "FAILED", "CRASHED", "REMOVED"):
            print("FINAL", t)
            break
        if t and t["status"] in ("BUILDING", "DEPLOYING"):
            print("PROGRESS", t["status"])
    # if anything SUCCESS after our trigger time, good
    if any(d["status"] == "SUCCESS" and d["createdAt"] >= "2026-07-29T10:12" for d in deps):
        print("SUCCESS after trigger")
        break
    time.sleep(20)
else:
    print("TIMEOUT")
