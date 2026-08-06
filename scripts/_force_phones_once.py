# -*- coding: utf-8 -*-
"""Cancel stuck queues on RL+WA, deploy RoadLog HEAD once, check after short wait."""
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


def list_deps(env, svc, n=6):
    r = gql(
        """
        query($e:String!,$s:String!,$n:Int!) {
          deployments(first: $n, input: { environmentId: $e, serviceId: $s }) {
            edges { node { id status createdAt } }
          }
        }
        """,
        {"e": env, "s": svc, "n": n},
    )
    edges = (((r.get("data") or {}).get("deployments") or {}).get("edges")) or []
    return [e["node"] for e in edges]


def cancel_active(name, env, svc):
    deps = list_deps(env, svc, 10)
    print(name, [(d["id"][:8], d["status"]) for d in deps[:5]])
    for d in deps:
        if d["status"] in (
            "QUEUED",
            "BUILDING",
            "DEPLOYING",
            "INITIALIZING",
            "WAITING",
        ):
            print(" cancel", d["id"], d["status"])
            print(
                " ",
                gql(
                    "mutation($id:String!){ deploymentCancel(id:$id) }",
                    {"id": d["id"]},
                ),
            )


cancel_active("WA", *WA)
cancel_active("RL", *RL)
time.sleep(2)

sha = subprocess.check_output(
    ["git", "rev-parse", "HEAD"],
    cwd=r"C:\Users\hysoo\projects\RoadLog",
    text=True,
).strip()
print("deploy", sha)
r = gql(
    """
    mutation($e:String!,$s:String!,$c:String!) {
      serviceInstanceDeployV2(environmentId:$e, serviceId:$s, commitSha:$c)
    }
    """,
    {"e": RL[0], "s": RL[1], "c": sha},
)
print(r)
new_id = (r.get("data") or {}).get("serviceInstanceDeployV2")
print("new_id", new_id)

# short fixed checks: 20s x 6 = 2 min max, not endless
for i in range(6):
    time.sleep(20)
    deps = list_deps(*RL, 4)
    line = " | ".join(f"{d['id'][:8]}:{d['status']}" for d in deps)
    print(f"t+{(i+1)*20}s {line}", flush=True)
    if new_id:
        t = next((d for d in deps if d["id"] == new_id), None)
        if t and t["status"] in ("SUCCESS", "FAILED", "CRASHED", "REMOVED"):
            print("FINAL", t)
            break
        if t and t["status"] in ("BUILDING", "DEPLOYING"):
            print("PROGRESS", t["status"])

# live probe
import urllib.request as u

print("LIVE build.json", u.urlopen("https://roadlog.co.kr/build.json", timeout=15).read().decode())
html = u.urlopen("https://roadlog.co.kr/", timeout=15).read().decode("utf-8", "replace")
print("TEL", "ok" if "033-818" in html else "missing")
print("HP", "ok" if "010-5583" in html else "missing")
