# -*- coding: utf-8 -*-
"""Redeploy RoadLog + WakeAgain after UI sound push."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

def _read_token(path: str) -> str:
    raw = Path(path).read_text(encoding="utf-8-sig").strip()
    line = raw.splitlines()[0].strip()
    # strip accidental quotes / BOM leftovers
    return line.strip().strip('"').strip("'").replace("\ufeff", "")


ROADLOG_TOKEN = _read_token(r"C:\Users\hysoo\Projects\RoadLog\.launch\railway.token")
WA_TOKEN = _read_token(r"C:\Users\hysoo\Projects\WakeAgain\.launch\railway.token")
GQL = "https://backboard.railway.app/graphql/v2"
ROADLOG_SERVICE = "ebf3faf1-2f14-425a-acad-9cc2c67fa633"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CoreLabsDeploy/1.0"


def gql(token: str, query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        GQL,
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
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
        print(f"HTTP {e.code}: {err[:500]}")
        return {}
    if data.get("errors"):
        print("GQL errors:", json.dumps(data["errors"], ensure_ascii=False)[:600])
    return data.get("data") or {}


def redeploy_service(token: str, service_id: str, label: str) -> bool:
    print(f"\n== Redeploy {label} ({service_id})")
    # Try several mutation shapes (Railway schema drifts)
    attempts = [
        (
            "serviceInstanceRedeploy(serviceId)",
            """
            mutation($serviceId: String!) {
              serviceInstanceRedeploy(serviceId: $serviceId)
            }
            """,
            {"serviceId": service_id},
        ),
        (
            "serviceInstanceRedeploy(environmentId+serviceId)",
            """
            mutation($environmentId: String!, $serviceId: String!) {
              serviceInstanceRedeploy(environmentId: $environmentId, serviceId: $serviceId)
            }
            """,
            None,  # filled below if we know env
        ),
    ]
    r = gql(token, attempts[0][1], attempts[0][2])
    print(r)
    if r.get("serviceInstanceRedeploy") is not None or r:
        return True
    return False


def main() -> int:
    print("RoadLog token len", len(ROADLOG_TOKEN))
    print("WA token len", len(WA_TOKEN))

    print("\n== WA me")
    print(gql(WA_TOKEN, "{ me { name email } }"))

    print("\n== WA projects")
    data = gql(
        WA_TOKEN,
        """
        query {
          projects {
            edges {
              node {
                id
                name
                services { edges { node { id name } } }
                environments { edges { node { id name } } }
              }
            }
          }
        }
        """,
    )
    edges = ((data.get("projects") or {}).get("edges")) or []
    services: list[tuple[str, str, str]] = []  # name, serviceId, envId
    for e in edges:
        node = e.get("node") or {}
        pname = node.get("name")
        print(f"PROJECT {pname} {node.get('id')}")
        envs = ((node.get("environments") or {}).get("edges")) or []
        env_id = None
        for ee in envs:
            en = ee.get("node") or {}
            print("  env", en.get("name"), en.get("id"))
            if (en.get("name") or "").lower() == "production" or env_id is None:
                env_id = en.get("id")
        for se in ((node.get("services") or {}).get("edges")) or []:
            sn = se.get("node") or {}
            print("  service", sn.get("name"), sn.get("id"))
            if sn.get("id"):
                services.append((f"{pname}/{sn.get('name')}", sn["id"], env_id or ""))

    # RoadLog project-scoped token probe
    print("\n== RoadLog project token probe")
    print(gql(ROADLOG_TOKEN, "{ projectToken { projectId environmentId } }"))

    # Redeploy known RoadLog service with both tokens
    for tok, label in [(ROADLOG_TOKEN, "roadlog-token"), (WA_TOKEN, "wa-token")]:
        print(f"\n-- try {label} for RoadLog service")
        r = gql(
            tok,
            """
            mutation($serviceId: String!) {
              serviceInstanceRedeploy(serviceId: $serviceId)
            }
            """,
            {"serviceId": ROADLOG_SERVICE},
        )
        print(r)

    # Redeploy WakeAgain web service if found
    for name, sid, env in services:
        low = name.lower()
        if "wake" in low or "road" in low or "web" in low:
            print(f"\n== Redeploy discovered {name}")
            if env:
                r = gql(
                    WA_TOKEN,
                    """
                    mutation($environmentId: String!, $serviceId: String!) {
                      serviceInstanceRedeploy(environmentId: $environmentId, serviceId: $serviceId)
                    }
                    """,
                    {"environmentId": env, "serviceId": sid},
                )
                print("with env:", r)
            r2 = gql(
                WA_TOKEN,
                """
                mutation($serviceId: String!) {
                  serviceInstanceRedeploy(serviceId: $serviceId)
                }
                """,
                {"serviceId": sid},
            )
            print("service only:", r2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
