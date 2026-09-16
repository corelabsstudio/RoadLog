"""네이버 데이터랩 검색어 트렌드. 키는 서버 환경변수에서만 읽는다."""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from typing import Any

import httpx


LEGACY_URL = "https://openapi.naver.com/v1/datalab/search"
API_HUB_URL = "https://naverapihub.apigw.ntruss.com/search-trend/v1/search"
WOMEN_19_TO_39 = ["3", "4", "5", "6"]
log = logging.getLogger(__name__)


class NaverDatalabError(RuntimeError):
    pass


def _env(*names: str) -> str:
    for name in names:
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return ""


def _credentials() -> tuple[str, str, str]:
    """API HUB를 우선 사용하고, 이관 기간의 기존 키도 잠시 지원한다."""
    client_id = _env("NAVER_API_HUB_CLIENT_ID", "X-NCP-APIGW-API-KEY-ID")
    client_secret = _env("NAVER_API_HUB_CLIENT_SECRET", "X-NCP-APIGW-API-KEY")
    if client_id and client_secret:
        return "api_hub", client_id, client_secret

    client_id = _env("NAVER_DATALAB_CLIENT_ID", "NAVER_CLIENT_ID")
    client_secret = _env("NAVER_DATALAB_CLIENT_SECRET", "NAVER_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise NaverDatalabError(
            "네이버 API HUB 키가 아직 없습니다. Railway 변수에 X-NCP-APIGW-API-KEY-ID와 "
            "X-NCP-APIGW-API-KEY를 넣어 주세요."
        )
    return "legacy", client_id, client_secret


def configured() -> bool:
    try:
        _credentials()
        return True
    except NaverDatalabError:
        return False


def configuration_mode() -> str:
    """관리 화면에 표시할 현재 인증 방식. 키 값 자체는 절대 내보내지 않는다."""
    try:
        mode, _, _ = _credentials()
        return mode
    except NaverDatalabError:
        return "missing"


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


def _safe_error_summary(response: httpx.Response) -> str:
    """API 오류의 원인만 운영 로그에 남긴다. 본문·키 등 민감값은 남기지 않는다."""
    try:
        body = response.json()
    except ValueError:
        return "non-json response"
    if not isinstance(body, dict):
        return "unexpected response"
    error = body.get("error")
    if isinstance(error, dict):
        code = str(error.get("errorCode") or error.get("code") or "")[:60]
        return f"errorCode={code}" if code else "api error"
    code = str(body.get("errorCode") or body.get("code") or "")[:60]
    return f"errorCode={code}" if code else "api error"


def trend(groups: list[dict[str, Any]]) -> dict[str, Any]:
    """19~39세 여성의 모바일 통합검색 상대 추이를 최근 90일 월 단위로 가져온다."""
    mode, client_id, client_secret = _credentials()
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
    headers = {"Content-Type": "application/json"}
    if mode == "api_hub":
        url = API_HUB_URL
        headers.update({
            "X-NCP-APIGW-API-KEY-ID": client_id,
            "X-NCP-APIGW-API-KEY": client_secret,
        })
    else:
        url = LEGACY_URL
        headers.update({
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret,
        })
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=12.0)
    except httpx.HTTPError as exc:
        raise NaverDatalabError("네이버 데이터랩에 연결하지 못했습니다. 잠시 뒤 다시 시도해 주세요.") from exc
    if response.status_code == 401 and mode == "api_hub":
        raise NaverDatalabError("API HUB 키를 인증하지 못했습니다. Railway의 두 API HUB 키를 다시 확인해 주세요.")
    if response.status_code == 403:
        raise NaverDatalabError("데이터랩 권한이 없습니다. 네이버 앱 설정에서 데이터랩(검색어트렌드)을 켜 주세요.")
    if response.status_code != 200:
        log.warning(
            "naver datalab request failed: mode=%s status=%s %s",
            mode, response.status_code, _safe_error_summary(response),
        )
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
