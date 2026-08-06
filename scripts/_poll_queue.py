# -*- coding: utf-8 -*-
"""Poll Railway deployment queue + live until sound is up."""
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

CFGS = [
    (
        "RoadLog",
        {
            "projectId": "9d3da15b-b2e6-4790-af3c-b0229e2d1965",
            "environmentId": "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7",
            "serviceId": "ebf3faf1-2f14-425a-acad-9cc2c67fa633",
        },
    ),
    (
        "WakeAgain",
        {
            "projectId": "2977b794-a0a8-42af-8ee5-add128046ae2",
            "environmentId": "2a3b69b2-441f-4369-9582-eaaa8e2c4f39",
            "serviceId": "32c989b1-4e9b-4057-adab-547bc8e2ebf1",
        },
    ),
]


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
        with urllib.request.urlopen(req, timeout=60) as res:
            data = json.loads(res.read().decode())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read()[:200], flush=True)
        return {}
    if data.get("errors"):
        print("GQLERR", data["errors"][0].get("message"), flush=True)
    return data.get("data") or {}


def top_deploys(cfg: dict) -> list[tuple[str, str]]:
    data = gql(
        """
        query($input: DeploymentListInput!) {
          deployments(input: $input) {
            edges { node { id status createdAt } }
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
    )
    edges = (((data.get("deployments") or {}).get("edges")) or [])
    out = []
    for e in edges[:5]:
        n = e.get("node") or {}
        out.append((n.get("status") or "?", n.get("id") or ""))
    return out


def live() -> dict:
    def get(url: str) -> str:
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "x", "Cache-Control": "no-cache"}
            )
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            return f"ERR:{e}"

    rl_build = get("https://roadlog.co.kr/build.json")
    rl_js = get("https://roadlog.co.kr/ui-sound.js")
    wa_js = get("https://wakeagain.com/js/ui-sound.js?v=20260722a")
    wa_html = get("https://wakeagain.com/")
    return {
        "rl_build_new": "20260722-sound-v1" in rl_build,
        "rl_js": "CoreLabsSound" in rl_js or "playTone" in rl_js,
        "wa_js": "CoreLabsSound" in wa_js or "playTone" in wa_js,
        "wa_html": "ui-sound.js" in wa_html,
        "rl_build_raw": rl_build.strip()[:80],
    }


def main() -> int:
    for i in range(40):
        print(f"\n=== poll {i} {time.strftime('%H:%M:%S')}", flush=True)
        all_successish = True
        for name, cfg in CFGS:
            tops = top_deploys(cfg)
            print(name, tops[:3], flush=True)
            if not tops or tops[0][0] not in ("SUCCESS", "ACTIVE"):
                # still waiting if top is QUEUED/BUILDING/DEPLOYING
                if tops and tops[0][0] in (
                    "QUEUED",
                    "BUILDING",
                    "DEPLOYING",
                    "INITIALIZING",
                    "WAITING",
                ):
                    all_successish = False
        L = live()
        print("live", L, flush=True)
        if L["rl_js"] and L["wa_js"] and L["wa_html"]:
            print("ALL LIVE OK", flush=True)
            return 0
        # if stuck only QUEUED for long, keep waiting trial queue
        time.sleep(20)
    print("TIMEOUT", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
