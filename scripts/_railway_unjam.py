# -*- coding: utf-8 -*-
"""Inspect / cancel stuck Railway deploys and force a fresh deploy."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

TOK = (
    Path(r"C:\Users\hysoo\Projects\RoadLog\.launch\railway.token")
    .read_text(encoding="utf-8-sig")
    .strip()
    .splitlines()[0]
    .strip()
    .replace("\ufeff", "")
)
GQL = "https://backboard.railway.app/graphql/v2"
UA = "Mozilla/5.0 CoreLabsDeploy/1.0"

ROADLOG = {
    "name": "RoadLog",
    "projectId": "9d3da15b-b2e6-4790-af3c-b0229e2d1965",
    "environmentId": "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7",
    "serviceId": "ebf3faf1-2f14-425a-acad-9cc2c67fa633",
}
WAKE = {
    "name": "WakeAgain",
    "projectId": "2977b794-a0a8-42af-8ee5-add128046ae2",
    "environmentId": "2a3b69b2-441f-4369-9582-eaaa8e2c4f39",
    "serviceId": "32c989b1-4e9b-4057-adab-547bc8e2ebf1",
}


def gql(query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        GQL,
        data=body,
        headers={
            "Authorization": f"Bearer {TOK}",
            "Content-Type": "application/json",
            "User-Agent": UA,
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            data = json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        print("HTTP", e.code, err[:800])
        return {}
    if data.get("errors"):
        print("GQLERR", json.dumps(data["errors"], ensure_ascii=False)[:800])
    return data.get("data") or {}


def list_deployments(cfg: dict) -> list[dict]:
    # Several query shapes — Railway schema changes often
    queries = [
        (
            "deployments(input)",
            """
            query($input: DeploymentListInput!) {
              deployments(input: $input) {
                edges {
                  node {
                    id
                    status
                    createdAt
                    meta
                    staticUrl
                    canRedeploy
                    projectId
                    serviceId
                    environmentId
                  }
                }
              }
            }
            """,
            {
                "input": {
                    "projectId": cfg["projectId"],
                    "environmentId": cfg["environmentId"],
                    "serviceId": cfg["serviceId"],
                }
            },
        ),
        (
            "deployments(first)",
            """
            query($projectId: String!, $environmentId: String!, $serviceId: String!) {
              deployments(
                first: 10
                input: {
                  projectId: $projectId
                  environmentId: $environmentId
                  serviceId: $serviceId
                }
              ) {
                edges { node { id status createdAt } }
              }
            }
            """,
            {
                "projectId": cfg["projectId"],
                "environmentId": cfg["environmentId"],
                "serviceId": cfg["serviceId"],
            },
        ),
    ]
    for name, q, v in queries:
        print(f"\n-- list {cfg['name']} via {name}")
        data = gql(q, v)
        edges = (((data.get("deployments") or {}).get("edges")) or [])
        nodes = [e.get("node") or {} for e in edges]
        for n in nodes[:8]:
            print(
                " ",
                n.get("status"),
                n.get("id"),
                n.get("createdAt"),
                str(n.get("meta"))[:80] if n.get("meta") else "",
            )
        if nodes:
            return nodes
    return []


def cancel(dep_id: str) -> None:
    print(f" cancel {dep_id}")
    # try cancel + stop
    for mut, field in [
        (
            """
            mutation($id: String!) { deploymentCancel(id: $id) }
            """,
            "deploymentCancel",
        ),
        (
            """
            mutation($id: String!) { deploymentStop(id: $id) }
            """,
            "deploymentStop",
        ),
        (
            """
            mutation($id: String!) { deploymentRemove(id: $id) }
            """,
            "deploymentRemove",
        ),
    ]:
        data = gql(mut, {"id": dep_id})
        if data.get(field) is not None or data:
            print("  ->", field, data)
            break


def deploy_latest(cfg: dict) -> None:
    print(f"\n-- serviceInstanceDeploy {cfg['name']}")
    print(
        gql(
            """
            mutation($environmentId: String!, $serviceId: String!) {
              serviceInstanceDeploy(environmentId: $environmentId, serviceId: $serviceId)
            }
            """,
            {
                "environmentId": cfg["environmentId"],
                "serviceId": cfg["serviceId"],
            },
        )
    )


def service_detail(cfg: dict) -> None:
    print(f"\n-- service instance {cfg['name']}")
    # try fetch service
    data = gql(
        """
        query($id: String!) {
          service(id: $id) {
            id
            name
            serviceInstances {
              edges {
                node {
                  id
                  environmentId
                  source { repo image { image } }
                  latestDeployment { id status createdAt }
                }
              }
            }
          }
        }
        """,
        {"id": cfg["serviceId"]},
    )
    print(json.dumps(data, ensure_ascii=False)[:1200])


def main() -> int:
    print("token len", len(TOK))
    for cfg in (ROADLOG, WAKE):
        print("\n" + "=" * 60)
        print(cfg["name"])
        service_detail(cfg)
        nodes = list_deployments(cfg)
        # cancel stuck BUILDING / DEPLOYING / INITIALIZING
        stuck = {
            "BUILDING",
            "DEPLOYING",
            "INITIALIZING",
            "QUEUED",
            "WAITING",
            "NEEDS_APPROVAL",
        }
        for n in nodes:
            st = (n.get("status") or "").upper()
            if st in stuck or st.endswith("ING"):
                cancel(n["id"])
        time.sleep(2)
        deploy_latest(cfg)
        time.sleep(2)
        list_deployments(cfg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
