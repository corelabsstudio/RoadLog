# -*- coding: utf-8 -*-
"""Cancel queued RoadLog deploys except the newest, then deploy HEAD."""
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
E = "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7"
S = "ebf3faf1-2f14-425a-acad-9cc2c67fa633"
GQL = "https://backboard.railway.app/graphql/v2"


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


r = gql(
    """
    query {
      deployments(first: 20, input: {
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
queued = [e["node"] for e in edges if e["node"]["status"] == "QUEUED"]
print("queued", len(queued))
# cancel all but keep none — then fresh deploy
for n in queued:
    print("cancel", n["id"], n["createdAt"])
    print(
        gql(
            "mutation($id: String!) { deploymentCancel(id: $id) }",
            {"id": n["id"]},
        )
    )

sha = subprocess.check_output(
    ["git", "rev-parse", "HEAD"],
    cwd=r"C:\Users\hysoo\projects\RoadLog",
    text=True,
).strip()
print("deploy", sha)
print(
    gql(
        """
        mutation($e:String!, $s:String!, $c:String!) {
          serviceInstanceDeployV2(environmentId:$e, serviceId:$s, commitSha:$c)
        }
        """,
        {"e": E, "s": S, "c": sha},
    )
)
