# -*- coding: utf-8 -*-
import json
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
SHA = "62d15efc19d9e763e4a3ae310015e506bae794e6"


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


attempts = [
    (
        "deployV2",
        """
        mutation($e:String!, $s:String!) {
          serviceInstanceDeployV2(environmentId:$e, serviceId:$s)
        }
        """,
        {"e": E, "s": S},
    ),
    (
        "deployV2commit",
        """
        mutation($e:String!, $s:String!, $c:String!) {
          serviceInstanceDeployV2(environmentId:$e, serviceId:$s, commitSha:$c)
        }
        """,
        {"e": E, "s": S, "c": SHA},
    ),
    (
        "deploy",
        """
        mutation($e:String!, $s:String!) {
          serviceInstanceDeploy(environmentId:$e, serviceId:$s)
        }
        """,
        {"e": E, "s": S},
    ),
]

for name, q, v in attempts:
    print("==", name)
    print(json.dumps(gql(q, v), ensure_ascii=False)[:500])
