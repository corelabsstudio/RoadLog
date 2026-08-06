# -*- coding: utf-8 -*-
"""Poll RoadLog Railway deploy for phones commit until terminal state."""
import json
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
E = "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7"
S = "ebf3faf1-2f14-425a-acad-9cc2c67fa633"
WANT = "1e596703-f1b4-4687-8b4b-4dcc2d148729"
GQL = "https://backboard.railway.app/graphql/v2"
Q = """
query {
  deployments(first: 6, input: {
    environmentId: "%s"
    serviceId: "%s"
  }) {
    edges { node { id status createdAt } }
  }
}
""" % (E, S)


def gql():
    body = json.dumps({"query": Q}).encode()
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


for i in range(30):
    r = gql()
    edges = (((r.get("data") or {}).get("deployments") or {}).get("edges")) or []
    nodes = [e["node"] for e in edges]
    line = " | ".join(f"{n['id'][:8]}:{n['status']}" for n in nodes[:5])
    print(f"[{i}] {line}", flush=True)
    target = next((n for n in nodes if n["id"] == WANT), None)
    if target and target["status"] in (
        "SUCCESS",
        "FAILED",
        "CRASHED",
        "REMOVED",
    ):
        print("FINAL", json.dumps(target), flush=True)
        break
    # any active build of HEAD is fine too
    if any(n["status"] == "SUCCESS" and n["createdAt"] >= "2026-07-29T10:10" for n in nodes):
        print("SUCCESS newer deploy seen", flush=True)
        break
    time.sleep(15)
else:
    print("TIMEOUT still waiting", flush=True)
