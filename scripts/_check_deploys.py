# -*- coding: utf-8 -*-
import json
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


def gql(q, v=None):
    body = json.dumps({"query": q, "variables": v or {}}).encode()
    req = urllib.request.Request(
        GQL,
        data=body,
        headers={
            "Authorization": f"Bearer {tok}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as res:
        return json.loads(res.read().decode())


def main():
    r = gql(
        """
        query($serviceId: String!, $envId: String!) {
          deployments(
            first: 8
            input: { serviceId: $serviceId, environmentId: $envId }
          ) {
            edges {
              node {
                id
                status
                createdAt
                meta
              }
            }
          }
        }
        """,
        {
            "serviceId": "ebf3faf1-2f14-425a-acad-9cc2c67fa633",
            "envId": "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7",
        },
    )
    edges = (((r.get("data") or {}).get("deployments") or {}).get("edges")) or []
    for e in edges:
        n = e.get("node") or {}
        meta = n.get("meta") or {}
        print(
            n.get("status"),
            n.get("createdAt"),
            (meta.get("commitHash") or meta.get("commitMessage") or "")[:60],
            n.get("id", "")[:12],
        )
    if r.get("errors"):
        print("errors", r["errors"])

    # deploy latest main tip without fixed sha
    r2 = gql(
        """
        mutation($environmentId: String!, $serviceId: String!) {
          serviceInstanceDeploy(
            environmentId: $environmentId
            serviceId: $serviceId
          )
        }
        """,
        {
            "environmentId": "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7",
            "serviceId": "ebf3faf1-2f14-425a-acad-9cc2c67fa633",
        },
    )
    print("deploy", json.dumps(r2, ensure_ascii=False)[:400])


if __name__ == "__main__":
    main()
