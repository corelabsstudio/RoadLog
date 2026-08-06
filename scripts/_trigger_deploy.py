# -*- coding: utf-8 -*-
"""Force Railway to build/deploy latest GitHub commits."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path


def token(p: str) -> str:
    return (
        Path(p)
        .read_text(encoding="utf-8-sig")
        .strip()
        .splitlines()[0]
        .strip()
        .replace("\ufeff", "")
        .strip('"')
        .strip("'")
    )


TOK = token(r"C:\Users\hysoo\Projects\RoadLog\.launch\railway.token")
GQL = "https://backboard.railway.app/graphql/v2"

ROADLOG = {
    "projectId": "9d3da15b-b2e6-4790-af3c-b0229e2d1965",
    "environmentId": "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7",
    "serviceId": "ebf3faf1-2f14-425a-acad-9cc2c67fa633",
    "sha": "e346d0a5963152047e0eb0fc9b3a471bfce9346f",
}
WAKE = {
    "projectId": "2977b794-a0a8-42af-8ee5-add128046ae2",
    "environmentId": "2a3b69b2-441f-4369-9582-eaaa8e2c4f39",
    "serviceId": "32c989b1-4e9b-4057-adab-547bc8e2ebf1",
    "sha": "2bc2220bf51c1a3a822634b683df58f78e4948ff",
}


def gql(query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        GQL,
        data=body,
        headers={
            "Authorization": f"Bearer {TOK}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 CoreLabsDeploy/1.0",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            data = json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode("utf-8", errors="replace")[:700])
        return {}
    print(json.dumps(data, ensure_ascii=False)[:800])
    return data


def try_mutations(label: str, cfg: dict) -> None:
    print(f"\n======== {label} ========")
    e, s, sha = cfg["environmentId"], cfg["serviceId"], cfg["sha"]

    attempts = [
        (
            "deploymentTrigger",
            """
            mutation($input: DeploymentTriggerInput!) {
              deploymentTrigger(input: $input) { id status }
            }
            """,
            {
                "input": {
                    "commitSha": sha,
                    "environmentId": e,
                    "serviceId": s,
                }
            },
        ),
        (
            "serviceInstanceDeploy",
            """
            mutation($environmentId: String!, $serviceId: String!) {
              serviceInstanceDeploy(environmentId: $environmentId, serviceId: $serviceId)
            }
            """,
            {"environmentId": e, "serviceId": s},
        ),
        (
            "serviceInstanceRedeploy",
            """
            mutation($environmentId: String!, $serviceId: String!) {
              serviceInstanceRedeploy(environmentId: $environmentId, serviceId: $serviceId)
            }
            """,
            {"environmentId": e, "serviceId": s},
        ),
        (
            "deploymentCreate",
            """
            mutation($input: DeploymentCreateInput!) {
              deploymentCreate(input: $input) { id status }
            }
            """,
            {
                "input": {
                    "serviceId": s,
                    "environmentId": e,
                    "commitSha": sha,
                }
            },
        ),
    ]
    for name, q, v in attempts:
        print(f"\n-- {name}")
        gql(q, v)


if __name__ == "__main__":
    try_mutations("RoadLog", ROADLOG)
    try_mutations("WakeAgain", WAKE)
