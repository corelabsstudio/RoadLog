"""Read Railway marketing switch names only. Never print values or credentials."""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOKEN_FILE = ROOT / ".launch" / "railway.token"
PROJECT = "9d3da15b-b2e6-4790-af3c-b0229e2d1965"
ENV = "367f2cc2-ac64-4daf-b04d-0d28f4ac97c7"
SERVICE = "ebf3faf1-2f14-425a-acad-9cc2c67fa633"
FLAGS = ("MARKETING_EXTERNAL_API_ENABLED", "MARKETING_GEMINI_ENABLED", "MARKETING_RESEARCH_ENABLED",
         "MARKETING_IMAGE_ENABLED", "MARKETING_VIDEO_ENABLED", "MARKETING_SNS_ENABLED",
         "MARKETING_AUTO_TEAM_ENABLED", "MARKETING_AUTO_PUBLISH_ENABLED")


def main() -> None:
    token = TOKEN_FILE.read_text(encoding="utf-8-sig").strip().splitlines()[0].strip().strip('"').strip("'")
    query = "query($p:String!,$e:String!,$s:String!){variables(projectId:$p,environmentId:$e,serviceId:$s)}"
    request = urllib.request.Request("https://backboard.railway.app/graphql/v2",
        data=json.dumps({"query": query,"variables": {"p":PROJECT,"e":ENV,"s":SERVICE}}).encode(),
        headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"},method="POST")
    with urllib.request.urlopen(request, timeout=20) as response:
        result = json.load(response)
    variables = (result.get("data") or {}).get("variables")
    if not isinstance(variables, dict):
        raise RuntimeError("Railway 변수 목록을 확인하지 못했습니다. 배포 안전 검증 중단.")
    for name in FLAGS:
        state = "ON" if str(variables.get(name,"false")).strip().lower() == "true" else "OFF"
        print(name, state)
        if state != "OFF":
            raise RuntimeError("마케팅 외부/자동 스위치가 켜져 있습니다. 배포 중단.")
    print("PASS: 운영 마케팅 외부/자동 스위치 모두 OFF")


if __name__ == "__main__": main()
