# -*- coding: utf-8 -*-
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


def gql(tok: str, query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        "https://backboard.railway.app/graphql/v2",
        data=body,
        headers={
            "Authorization": f"Bearer {tok}",
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
        print("HTTP", e.code, e.read().decode("utf-8", errors="replace")[:500])
        return {}
    print(json.dumps(data, ensure_ascii=False)[:600])
    return data


MUT = """
mutation($e: String!, $s: String!) {
  serviceInstanceRedeploy(environmentId: $e, serviceId: $s)
}
"""

# RoadLog
print("== RoadLog redeploy")
gql(
    token(r"C:\Users\hysoo\Projects\RoadLog\.launch\railway.token"),
    MUT,
    {
        "e": "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7",
        "s": "ebf3faf1-2f14-425a-acad-9cc2c67fa633",
    },
)

# WakeAgain
print("== WakeAgain redeploy")
gql(
    token(r"C:\Users\hysoo\Projects\WakeAgain\.launch\railway.token"),
    MUT,
    {
        "e": "2a3b69b2-441f-4369-9582-eaaa8e2c4f39",
        "s": "32c989b1-4e9b-4057-adab-547bc8e2ebf1",
    },
)

# Try WA with RoadLog token just in case same workspace
print("== WakeAgain via RoadLog token")
gql(
    token(r"C:\Users\hysoo\Projects\RoadLog\.launch\railway.token"),
    MUT,
    {
        "e": "2a3b69b2-441f-4369-9582-eaaa8e2c4f39",
        "s": "32c989b1-4e9b-4057-adab-547bc8e2ebf1",
    },
)
