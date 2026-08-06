# -*- coding: utf-8 -*-
"""Deploy latest main HEAD to RoadLog Railway web service + verify payment vars."""
from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOK = (
    (ROOT / ".launch" / "railway.token")
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

PAYMENT_VARS = {
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
            "User-Agent": "RoadLogDeploy/2.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as res:
            return json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        return {
            "http": e.code,
            "body": e.read().decode("utf-8", "replace")[:1200],
        }


def head_sha() -> str:
    return (
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT)
        .decode()
        .strip()
    )


def main() -> None:
    sha = head_sha()
    print("HEAD", sha)

    # ensure payment env
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
                "variables": PAYMENT_VARS,
            }
        },
    )
    print("vars", json.dumps(r, ensure_ascii=False)[:300])

    # deploy latest (with commit sha if supported)
    for name, q, v in [
        (
            "deployV2+sha",
            """
            mutation($e:String!, $s:String!, $c:String!) {
              serviceInstanceDeployV2(environmentId:$e, serviceId:$s, commitSha:$c)
            }
            """,
            {"e": ENV, "s": SERVICE, "c": sha},
        ),
        (
            "deployV2",
            """
            mutation($e:String!, $s:String!) {
              serviceInstanceDeployV2(environmentId:$e, serviceId:$s)
            }
            """,
            {"e": ENV, "s": SERVICE},
        ),
        (
            "deploy",
            """
            mutation($e:String!, $s:String!) {
              serviceInstanceDeploy(environmentId:$e, serviceId:$s)
            }
            """,
            {"e": ENV, "s": SERVICE},
        ),
    ]:
        out = gql(q, v)
        print("==", name, json.dumps(out, ensure_ascii=False)[:400])

    # poll live
    for i in range(24):
        time.sleep(15)
        try:
            with urllib.request.urlopen(
                "https://roadlog.co.kr/build.json", timeout=20
            ) as res:
                build = json.loads(res.read().decode())
            b = build.get("build") or ""
            print(i, "build", b)
            # success if not the old stuck build
            if b and b not in ("20260727-vat-excl", "20260722-sound-v1"):
                # also probe summary route
                req = urllib.request.Request(
                    "https://roadlog.co.kr/api/logs/summary?period=month",
                    headers={"User-Agent": "deploy-check"},
                )
                try:
                    urllib.request.urlopen(req, timeout=15)
                    code = 200
                except urllib.error.HTTPError as e:
                    code = e.code
                print("LIVE_OK", b, "summary_status", code)
                # check html
                with urllib.request.urlopen(
                    "https://roadlog.co.kr/", timeout=20
                ) as res:
                    html = res.read().decode("utf-8", "replace")
                print(
                    "has reports ui",
                    "view-reports" in html,
                    "PDF 저장" in html,
                )
                return
        except Exception as e:
            print(i, "wait", e)
    print("TIMEOUT still old build — check Railway dashboard Deployments")


if __name__ == "__main__":
    main()
