# -*- coding: utf-8 -*-
"""Upsert payment URLs on Railway and trigger redeploy."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

TOK = (
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

# Option creation order → ascending product IDs (best-effort mapping)
URLS = {
    "PRO_PAYMENT_URL": "https://smartstore.naver.com/thelucid/products/13684008038",
    "PRO_ANNUAL_PAYMENT_URL": "https://smartstore.naver.com/thelucid/products/13684008039",
    "ENTERPRISE_PAYMENT_URL": "https://smartstore.naver.com/thelucid/products/13684008040",
    "ENTERPRISE_ANNUAL_PAYMENT_URL": "https://smartstore.naver.com/thelucid/products/13684008041",
}


def gql(query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        GQL,
        data=body,
        headers={
            "Authorization": f"Bearer {TOK}",
            "Content-Type": "application/json",
            "User-Agent": "RoadLogDeploy/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as res:
        return json.loads(res.read().decode())


def main() -> None:
    # Upsert vars
    r = gql(
        """
        mutation($input: VariableCollectionUpsertInput!) {
          variableCollectionUpsert(input: $input)
        }
        """,
        {
            "input": {
                "projectId": PROJECT,
                "environmentId": ENV,
                "serviceId": SERVICE,
                "variables": URLS,
            }
        },
    )
    print("upsert", json.dumps(r, ensure_ascii=False)[:500])

    # Read back
    r2 = gql(
        """
        query($projectId: String!, $environmentId: String!, $serviceId: String) {
          variables(
            projectId: $projectId
            environmentId: $environmentId
            serviceId: $serviceId
          )
        }
        """,
        {"projectId": PROJECT, "environmentId": ENV, "serviceId": SERVICE},
    )
    data = r2.get("data", {}).get("variables")
    print("vars type", type(data).__name__)
    if isinstance(data, dict):
        for k in URLS:
            print(k, "=", data.get(k))
    else:
        print(json.dumps(r2, ensure_ascii=False)[:1500])

    # Redeploy latest
    r3 = gql(
        """
        mutation($environmentId: String!, $serviceId: String!) {
          serviceInstanceRedeploy(
            environmentId: $environmentId
            serviceId: $serviceId
          )
        }
        """,
        {"environmentId": ENV, "serviceId": SERVICE},
    )
    print("redeploy", json.dumps(r3, ensure_ascii=False)[:500])


if __name__ == "__main__":
    main()
