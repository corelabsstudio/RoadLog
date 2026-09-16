"""네이버 데이터랩 검색어 트렌드. 키는 서버 환경변수에서만 읽는다."""

from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import httpx


URL = "https://openapi.naver.com/v1/datalab/search"
WOMEN_19_TO_39 = ["3", "4", "5", "6"]


class NaverDatalabError(RuntimeError):
    pass


def configured() -> bool:
    return bool(
        (os.getenv("NAVER_DATALAB_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID") or "").strip()
        and (os.getenv("NAVER_DATALAB_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET") or "").strip()
    )


def _credentials() -> tuple[str, str]:
    client_id = (os.getenv("NAVER_DATALAB_CLIENT_ID") or os.getenv("NAVER_CLIENT_ID") or "").strip()
    client_secret = (
        os.getenv("NAVER_DATALAB_CLIENT_SECRET") or os.getenv("NAVER_CLIENT_SECRET") or ""
    ).strip()
    if not client_id or not client_secret:
        raise NaverDatalabError(
            "네이버 데이터랩 키가 아직 없습니다. Railway 변수에 NAVER_DATALAB_CLIENT_ID와 "
            "NAVER_DATALAB_CLIENT_SECRET을 넣어 주세요."
        )
    return client_id, client_secret


def _clean_groups(groups: list[dict[str, Any]]) -> list[dict[str, list[str] | str]]:
    out: list[dict[str, list[str] | str]] = []
    for raw in groups:
        title = str(raw.get("groupName") or "").strip()[:50]
        words = raw.get("keywords") or []
        if not isinstance(words, list):
            words = []
        keywords = [str(word).strip()[:80] for word in words if str(word).strip()]
        if not title or not keywords:
            continue
        out.append({"groupName": title, "keywords": keywords[:20]})
    if not out:
        raise NaverDatalabError("검색어를 하나 이상 넣어 주세요.")
    if len(out) > 5:
        raise NaverDatalabError("한 번에 검색어 묶음 다섯 개까지만 비교할 수 있어요.")
    return out


def trend(groups: list[dict[str, Any]]) -> dict[str, Any]:
    """19~39세 여성의 모바일 통합검색 상대 추이를 최근 90일 월 단위로 가져온다."""
    client_id, client_secret = _credentials()
    end = date.today()
    start = end - timedelta(days=90)
    payload = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "timeUnit": "month",
        "keywordGroups": _clean_groups(groups),
        "device": "mo",
        "gender": "f",
        "ages": WOMEN_19_TO_39,
    }
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json",
    }
    try:
        response = httpx.post(URL, json=payload, headers=headers, timeout=12.0)
    except httpx.HTTPError as exc:
        raise NaverDatalabError("네이버 데이터랩에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요.") from exc
    if response.status_code == 403:
        raise NaverDatalabError("데이터랩 권한이 없습니다. 네이버 앱 설정에서 데이터랩(검색어트렌드)을 켜 주세요.")
    if response.status_code != 200:
        raise NaverDatalabError("네이버 데이터랩 조회에 실패했습니다. 키와 요청 한도를 확인해 주세요.")
    try:
        data = response.json()
    except ValueError as exc:
        raise NaverDatalabError("네이버 데이터랩 응답을 읽지 못했습니다.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise NaverDatalabError("네이버 데이터랩이 예상과 다른 응답을 보냈습니다.")
    return {
        "target": "여성 · 19~39세 · 모바일",
        "unit": "상대 검색지수 (조회 기간 안에서 가장 높은 값이 100)",
        "startDate": data.get("startDate", payload["startDate"]),
        "endDate": data.get("endDate", payload["endDate"]),
        "results": data["results"],
    }
