# -*- coding: utf-8 -*-
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\hysoo\Projects\WakeAgain")
TOK = (
    Path(r"C:\Users\hysoo\Projects\RoadLog\.launch\railway.token")
    .read_text(encoding="utf-8-sig")
    .strip()
    .splitlines()[0]
    .strip()
    .replace("\ufeff", "")
)


def gql(q, v=None):
    body = json.dumps({"query": q, "variables": v or {}}).encode()
    req = urllib.request.Request(
        "https://backboard.railway.app/graphql/v2",
        data=body,
        headers={
            "Authorization": f"Bearer {TOK}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("gql fail", e)
        return {}


# cancel queued WA
data = gql(
    """
    query($input: DeploymentListInput!) {
      deployments(input: $input) {
        edges { node { id status } }
      }
    }
    """,
    {
        "input": {
            "projectId": "2977b794-a0a8-42af-8ee5-add128046ae2",
            "environmentId": "2a3b69b2-441f-4369-9582-eaaa8e2c4f39",
            "serviceId": "32c989b1-4e9b-4057-adab-547bc8e2ebf1",
        }
    },
)
edges = (((data.get("data") or data).get("deployments") or {}).get("edges")) or []
for e in edges:
    n = e.get("node") or {}
    print("dep", n.get("status"), n.get("id"))
    if n.get("status") == "QUEUED":
        r = gql(
            "mutation($id: String!) { deploymentCancel(id: $id) }",
            {"id": n["id"]},
        )
        print(" cancel", r)

print("railway up...")
r = subprocess.run(
    ["railway", "up", "--detach", "--message", "ui-sound deploy", "-s", "wakeagain"],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
)
print(r.stdout)
print(r.stderr)
print("exit", r.returncode)

r2 = subprocess.run(
    ["railway", "deployment", "list", "--json", "-s", "wakeagain"],
    cwd=str(ROOT),
    capture_output=True,
    text=True,
)
try:
    d = json.loads(r2.stdout)
    for x in d[:6]:
        print(x.get("status"), x.get("id", "")[:8], x.get("createdAt"))
except Exception:
    print(r2.stdout[:500], r2.stderr[:300])
