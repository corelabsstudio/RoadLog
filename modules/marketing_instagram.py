"""ROADLOG-only official Instagram Login publishing adapter.

Never used by the scheduler. Secrets come only from server environment variables.
"""
from __future__ import annotations

import os
import re
import time
from urllib.parse import urlsplit

import httpx
from modules import marketing_safety


TARGET_USERNAME = "mumung_101"
_VERSION = re.compile(r"v\d+\.\d+\Z")
_ID = re.compile(r"\d+\Z")


def configuration() -> dict[str, str] | None:
    version = os.getenv("INSTAGRAM_GRAPH_VERSION", "").strip()
    user_id = os.getenv("INSTAGRAM_USER_ID", "").strip()
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    if not version or not user_id or not token:
        return None
    if not _VERSION.fullmatch(version) or not _ID.fullmatch(user_id):
        return None
    return {"version": version, "user_id": user_id, "token": token}


def configured() -> bool:
    return configuration() is not None


def publishing_enabled() -> bool:
    return os.getenv("INSTAGRAM_PUBLISH_ENABLED", "").strip().lower() == "true"


def image_url_ok(value: str) -> bool:
    """Only public ROADLOG JPEGs are sent to Meta; no arbitrary URL input."""
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and parsed.hostname == "roadlog.co.kr"
                and parsed.port is None and not parsed.username and not parsed.password
                and parsed.path.lower().endswith((".jpg", ".jpeg"))
                and not parsed.query and not parsed.fragment and len(value) <= 500)
    except ValueError:
        return False


class InstagramPublisher:
    def __init__(self, client: httpx.Client | None = None, sleep=time.sleep):
        self.client = client or httpx.Client(timeout=15, follow_redirects=False)
        self.sleep = sleep

    def _request(self, method: str, path: str, config: dict[str, str], **kwargs) -> dict:
        if not marketing_safety.enabled("sns"):
            raise PermissionError("마케팅 SNS API가 비활성화되어 있습니다.")
        audit_id = marketing_safety.before_call("sns", "instagram_graph", agent_id="social_manager")
        url = f"https://graph.instagram.com/{config['version']}/{path}"
        response = self.client.request(method, url, headers={"Authorization": f"Bearer {config['token']}"}, **kwargs)
        marketing_safety.after_call(audit_id, "HTTP_" + str(response.status_code))
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("인스타그램 API 응답 형식 오류")
        return data

    def verify_account(self, config: dict[str, str]) -> None:
        result = self._request("GET", config["user_id"], config, params={"fields": "id,username,account_type"})
        if str(result.get("id")) != config["user_id"] or str(result.get("username", "")).lower() != TARGET_USERNAME:
            raise PermissionError("연결 계정이 @mumung_101과 일치하지 않습니다.")
        if result.get("account_type") not in {"BUSINESS", "MEDIA_CREATOR", "CREATOR"}:
            raise PermissionError("프로페셔널 계정 여부를 확인할 수 없습니다.")

    def publish_image(self, image_url: str, caption: str, config: dict[str, str]) -> dict[str, str]:
        if not image_url_ok(image_url):
            raise ValueError("ROADLOG 공개 JPEG 주소만 사용할 수 있습니다.")
        if not caption or len(caption) > 2200:
            raise ValueError("게시 문구 길이를 확인해 주세요.")
        self.verify_account(config)
        created = self._request("POST", f"{config['user_id']}/media", config,
                                data={"image_url": image_url, "caption": caption})
        container = str(created.get("id") or "")
        if not _ID.fullmatch(container):
            raise ValueError("인스타그램 미디어 준비 응답 오류")
        for attempt in range(5):
            state = self._request("GET", container, config, params={"fields": "status_code"}).get("status_code")
            if state == "FINISHED":
                break
            if state in {"ERROR", "EXPIRED"}:
                raise ValueError("인스타그램 미디어 준비 실패")
            if attempt < 4:
                self.sleep(2)
        else:
            raise ValueError("인스타그램 미디어 준비 시간 초과")
        # This final request is never retried: a timeout may mean the post is already public.
        published = self._request("POST", f"{config['user_id']}/media_publish", config,
                                  data={"creation_id": container})
        media_id = str(published.get("id") or "")
        if not _ID.fullmatch(media_id):
            raise ValueError("인스타그램 공개 결과를 확인할 수 없습니다.")
        return {"media_id": media_id, "container_id": container}
