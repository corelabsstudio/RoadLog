"""홍보 글 템플릿 (복붙/자동입력용) — 제품 비종속 범용 문구."""

from __future__ import annotations

TEMPLATES: dict[str, dict[str, str]] = {
    "문제 공감형": {
        "title": "이런 불편, 아직도 손으로 해결하고 계신가요?",
        "body": (
            "반복 업무·정리·제출 때문에 시간이 늘 부족하다고 느끼는 분 계신가요.\n\n"
            "핵심만 입력하면 결과물로 정리해 주는 도구를 소개합니다.\n\n"
            "· 이름: (사이트 분석 후 자동 반영)\n"
            "· 한 줄 소개: (분석 결과 반영)\n"
            "· 사이트: (제품 주소)\n\n"
            "비슷한 고민이 있어 써 보고 공유합니다.\n"
            "실제 사용 전에는 내용을 한 번만 확인해 주세요.\n"
            "질문 있으면 댓글로 남겨 주세요."
        ),
    },
    "가격 강조형": {
        "title": "가격 대비 써 볼 만한 도구 공유",
        "body": (
            "가볍게 시작하기 좋은 서비스를 정리해 둡니다.\n\n"
            "· 무료/체험 구간이 있는 경우가 많습니다\n"
            "· 유료는 사이트에서 최신 요금을 확인해 주세요\n"
            "· 팀·개인 플랜 여부는 제품마다 다릅니다\n\n"
            "자세한 내용: (제품 주소)\n\n"
            "※ 서비스 소개 목적입니다. 커뮤니티 규정에 맞게 이용 부탁드립니다."
        ),
    },
    "사용 방법형": {
        "title": "이렇게 시작하면 됩니다 (사용 흐름)",
        "body": (
            "처음 쓰시는 분 기준으로 흐름만 짧게 정리합니다.\n\n"
            "1. 사이트 접속\n"
            "2. 핵심 기능·메뉴 확인\n"
            "3. 필요하면 가입·체험\n"
            "4. 결과물 확인 후 본 업무에 적용\n\n"
            "자세한 안내는 사이트 공지·도움말을 참고하세요.\n"
            "바로 가기: (제품 주소)\n\n"
            "※ 본 글은 서비스 소개 목적입니다."
        ),
    },
    "짧은 버전": {
        "title": "유용할 수 있는 도구 한 줄 공유",
        "body": (
            "한 줄 소개: (사이트 분석 후 자동 반영)\n"
            "바로 가기: (제품 주소)\n"
            "궁금한 점 있으면 댓글 주세요."
        ),
    },
}


def list_template_names() -> list[str]:
    return list(TEMPLATES.keys())


def get_template(name: str) -> dict[str, str]:
    return dict(TEMPLATES.get(name) or next(iter(TEMPLATES.values())))


def get_template_for_profile(name: str, profile=None) -> dict[str, str]:
    """프로필이 있으면 브랜드·주소·소개를 템플릿에 주입."""
    t = get_template(name)
    if profile is None:
        return t

    brand = (
        getattr(profile, "brand", None)
        or getattr(profile, "title", None)
        or ""
    )
    brand = str(brand).strip() if brand else ""
    url = (
        getattr(profile, "final_url", None)
        or getattr(profile, "url", None)
        or ""
    )
    url = str(url).strip() if url else ""
    desc = str(getattr(profile, "description", None) or "").strip()
    if hasattr(profile, "to_dict"):
        d = profile.to_dict()
        brand = brand or str(d.get("brand") or d.get("title") or "").strip()
        url = url or str(d.get("final_url") or d.get("url") or "").strip()
        desc = desc or str(d.get("description") or "").strip()

    title = t["title"]
    body = t["body"]
    if brand:
        body = body.replace("(사이트 분석 후 자동 반영)", brand)
        body = body.replace("이름: (사이트 분석 후 자동 반영)", f"이름: {brand}")
        title = title if brand in title else f"{brand} — {title}"
    if desc:
        body = body.replace("한 줄 소개: (분석 결과 반영)", f"한 줄 소개: {desc[:120]}")
        body = body.replace("한 줄 소개: (사이트 분석 후 자동 반영)", f"한 줄 소개: {desc[:120]}")
    if url:
        body = body.replace("(제품 주소)", url)
        body = body.replace("사이트: (제품 주소)", f"사이트: {url}")
        body = body.replace("바로 가기: (제품 주소)", f"바로 가기: {url}")
        body = body.replace("자세한 내용: (제품 주소)", f"자세한 내용: {url}")

    return {"title": title, "body": body}
