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
PROJECT = "9d3da15b-b2e6-4790-af3c-b0229e2d1965"
ENV = "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7"
SERVICE = "ebf3faf1-2f14-425a-acad-9cc2c67fa633"


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
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode("utf-8", "replace")[:800]}


def main():
    # env-level vars (no service)
    r1 = gql(
        """
        query($p: String!, $e: String!) {
          variables(projectId: $p, environmentId: $e)
        }
        """,
        {"p": PROJECT, "e": ENV},
    )
    d1 = (r1.get("data") or {}).get("variables") or {}
    print("=== ENV-LEVEL ===")
    if isinstance(d1, dict):
        for k in sorted(d1):
            if "PAY" in k.upper() or "PRO_" in k or "ENTERPRISE" in k:
                print(k, "=", d1[k])
    else:
        print(r1)

    r2 = gql(
        """
        query($p: String!, $e: String!, $s: String!) {
          variables(projectId: $p, environmentId: $e, serviceId: $s)
        }
        """,
        {"p": PROJECT, "e": ENV, "s": SERVICE},
    )
    d2 = (r2.get("data") or {}).get("variables") or {}
    print("=== SERVICE-LEVEL ===")
    if isinstance(d2, dict):
        for k in sorted(d2):
            if "PAY" in k.upper() or "PRO_" in k or "ENTERPRISE" in k or k in (
                "APP_ENV",
                "DATA_DIR",
            ):
                print(k, "=", d2[k])
    else:
        print(r2)

    # domains
    r3 = gql(
        """
        query($id: String!) {
          project(id: $id) {
            name
            services {
              edges {
                node {
                  id
                  name
                }
              }
            }
          }
        }
        """,
        {"id": PROJECT},
    )
    print("=== SERVICES ===")
    print(json.dumps(r3, ensure_ascii=False)[:1200])


if __name__ == "__main__":
    main()
