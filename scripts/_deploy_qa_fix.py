# -*- coding: utf-8 -*-
"""Deploy RoadLog to Railway at a specific commit SHA."""
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

tok = (
    Path(__file__)
    .resolve()
    .parents[1]
    .joinpath(".launch/railway.token")
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
SHA = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[1], text=True
).strip()
print("SHA", SHA)


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
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        return {"http": e.code, "body": e.read().decode("utf-8", "replace")[:900]}


# Prefer deploy with commitSha
q = """
mutation($e:String!, $s:String!, $c:String!) {
  serviceInstanceDeployV2(environmentId:$e, serviceId:$s, commitSha:$c)
}
"""
print(json.dumps(gql(q, {"e": E, "s": S, "c": SHA}), ensure_ascii=False)[:800])
