#!/usr/bin/env python3
"""
범용 홍보에 적합한 커뮤니티·채널 추천 (로컬 큐레이션)

외부 연동 없음 · 네트워크 없음 · 점수·카테고리·팁만 이 컴퓨터 데이터로 제공.
커뮤니티 규정·광고 금지를 항상 확인하세요.
"""

from __future__ import annotations

import random
from typing import Any

# score: 1~100 (일반 B2B·SaaS·자영업 홍보 적합도)
# kind: community | blog | sns | b2b | qna
RECOMMENDED_SITES: list[dict[str, Any]] = [
    {
        "id": "naver_blog",
        "name": "네이버 블로그",
        "category": "블로그·SEO",
        "kind": "blog",
        "score": 96,
        "site_url": "https://blog.naver.com/",
        "login_url": "https://nid.naver.com/nidlogin.login",
        "write_url": "https://blog.naver.com/GoBlogWrite.naver",
        "audience": "운행일지·외근일지 검색 유입",
        "why": "장기 검색 트래픽. 홍보 문구 본문 그대로 활용하기 좋음.",
        "tip": "제목에 '운행일지 양식'·'외근일지 작성' 등 키워드. 링크는 본문 하단 1개.",
        "caution": "반복 동일 글·과도한 키워드 나열은 저품질 처리될 수 있음.",
    },
    {
        "id": "tistory",
        "name": "티스토리",
        "category": "블로그·SEO",
        "kind": "blog",
        "score": 88,
        "site_url": "https://www.tistory.com/",
        "login_url": "https://www.tistory.com/auth/login",
        "write_url": "https://www.tistory.com/",
        "audience": "블로그·생산성 관심층",
        "why": "구글 검색 유입·장문 후기형 소개에 적합.",
        "tip": "문제→해결→가격 순. 스크린샷·사용 흐름 넣으면 신뢰↑.",
        "caution": "스팸성 상호 링크·복붙 도배는 피하기.",
    },
    {
        "id": "brunch",
        "name": "브런치스토리",
        "category": "블로그·SEO",
        "kind": "blog",
        "score": 82,
        "site_url": "https://brunch.co.kr/",
        "login_url": "https://brunch.co.kr/signin",
        "write_url": "https://brunch.co.kr/write",
        "audience": "직장인·창업 관심 독자",
        "why": "스토리텔링·문제 공감형 글이 잘 먹힘.",
        "tip": "광고 티 줄이고 '퇴근이 빨라지는 일지' 같은 경험 톤.",
        "caution": "노골적 홍보 제목은 거부감. 링크는 자연스럽게.",
    },
    {
        "id": "naver_cafe_biz",
        "name": "네이버 카페 (비즈니스·자영업)",
        "category": "네이버 카페",
        "kind": "community",
        "score": 90,
        "site_url": "https://section.cafe.naver.com/ca-fe/home",
        "login_url": "https://nid.naver.com/nidlogin.login",
        "write_url": "",
        "audience": "자영업·중소기업·영업",
        "why": "타깃(법인차·외근)과 겹치는 카페가 많음. 전환 가능성 높음.",
        "tip": "카페 검색: '영업' '자영업' '중소기업' '법인'. 홍보게시판·정보공유 게시판 확인 후 작성.",
        "caution": "홍보 금지 게시판·도배 금지. 가입 인사·활동 후 글 권장.",
    },
    {
        "id": "naver_cafe_car",
        "name": "네이버 카페 (업무차·영업)",
        "category": "네이버 카페",
        "kind": "community",
        "score": 87,
        "site_url": "https://section.cafe.naver.com/ca-fe/home",
        "login_url": "https://nid.naver.com/nidlogin.login",
        "write_url": "",
        "audience": "법인차·영업사원",
        "why": "운행기록·일지 니즈가 직접 있는 집단.",
        "tip": "제목 예: '운행일지 엑셀 정리, 이렇게 줄였어요'. 첫 글은 팁 공유형.",
        "caution": "순수 광고 글은 삭제·강퇴 위험. 본문 하단 링크만.",
    },
    {
        "id": "blind",
        "name": "블라인드 (Blind)",
        "category": "직장인 커뮤니티",
        "kind": "community",
        "score": 84,
        "site_url": "https://www.teamblind.com/kr",
        "login_url": "https://www.teamblind.com/kr",
        "write_url": "",
        "audience": "대기업·중견 직장인",
        "why": "외근·총무·영업 직군 피드백·입소문에 유리.",
        "tip": "회사 인증 계정. '우리 팀 일지 작성 지옥인데…' 공감 후 도구 소개.",
        "caution": "노골적 홍보·자작 후기 남발 금지. 규정 확인.",
    },
    {
        "id": "clien",
        "name": "클리앙",
        "category": "직장인 커뮤니티",
        "kind": "community",
        "score": 72,
        "site_url": "https://www.clien.net/",
        "login_url": "https://www.clien.net/service/auth/login",
        "write_url": "",
        "audience": "IT·직장인",
        "why": "생산성 도구 반응 있는 편. 사용기 톤이 중요.",
        "tip": "사용기 게시판·소모임 위주. 스크린샷·실제 워크플로.",
        "caution": "광고성 단문·링크만 올리면 비추천·신고 많음.",
    },
    {
        "id": "ppomppu",
        "name": "뽐뿌",
        "category": "커뮤니티",
        "kind": "community",
        "score": 68,
        "site_url": "https://www.ppomppu.co.kr/",
        "login_url": "https://www.ppomppu.co.kr/login.php",
        "write_url": "",
        "audience": "일반·직장인",
        "why": "정보 게시판 유입. 가성비(Pro 2,900원) 메시지와 맞음.",
        "tip": "정보·사용기 형식. 가격·무료 체험 먼저.",
        "caution": "홍보 규정 엄격한 게시판 많음. 반드시 확인.",
    },
    {
        "id": "okky",
        "name": "OKKY",
        "category": "개발·스타트업",
        "kind": "b2b",
        "score": 70,
        "site_url": "https://okky.kr/",
        "login_url": "https://okky.kr/login",
        "write_url": "https://okky.kr/articles/write",
        "audience": "개발자·스타트업",
        "why": "사이드 프로젝트·온라인 서비스 공유 문화. 피드백 수집용.",
        "tip": "forum/stories 성격으로 만든 과정·문제 정의 공유.",
        "caution": "순수 광고 글은 비추천. 기술·제품 스토리 필요.",
    },
    {
        "id": "linkedin",
        "name": "링크드인",
        "category": "기업·소셜",
        "kind": "b2b",
        "score": 86,
        "site_url": "https://www.linkedin.com/",
        "login_url": "https://www.linkedin.com/login",
        "write_url": "https://www.linkedin.com/preload/share",
        "audience": "기업·팀장·총무",
        "why": "팀 도입·기업 신뢰. 팀 요금제 관심층.",
        "tip": "프로필 한 줄 + 짧은 포스트. '팀 도입 문의 환영'.",
        "caution": "과도한 DM 스팸 금지.",
    },
    {
        "id": "threads",
        "name": "Threads (스레드)",
        "category": "SNS",
        "kind": "sns",
        "score": 74,
        "site_url": "https://www.threads.net/",
        "login_url": "https://www.threads.net/login",
        "write_url": "https://www.threads.net/",
        "audience": "일반·직장인 SNS",
        "why": "짧은 문제 공감 문구 + 링크. 주 2~3회 노출용.",
        "tip": "한 줄 소개 템플릿. 해시태그 과다 금지.",
        "caution": "동일 문구 반복 포스팅은 도달↓.",
    },
    {
        "id": "x_twitter",
        "name": "X (트위터)",
        "category": "SNS",
        "kind": "sns",
        "score": 71,
        "site_url": "https://x.com/",
        "login_url": "https://x.com/i/flow/login",
        "write_url": "https://x.com/compose/post",
        "audience": "인지도·빌더 커뮤니티",
        "why": "런칭 소식·짧은 CTA. 인지도 쌓기용.",
        "tip": "무료 체험 링크 중심. 스레드로 기능 3줄 요약.",
        "caution": "봇성 반복 트윗 금지.",
    },
    {
        "id": "kakao_openchat",
        "name": "카카오 오픈채팅",
        "category": "메신저",
        "kind": "sns",
        "score": 92,
        "site_url": "https://open.kakao.com/",
        "login_url": "",
        "write_url": "",
        "audience": "영업·외근·지인 네트워크",
        "why": "전환율 최고 구간. 초기 1~2주 1순위 채널.",
        "tip": "짧은 인사 + 무료 체험 링크 1개. 가격은 질문 오면.",
        "caution": "무차별 초대·스팸성 링크 금지. 방 규칙 준수.",
    },
    {
        "id": "naver_kin",
        "name": "네이버 지식iN",
        "category": "Q&A·검색",
        "kind": "qna",
        "score": 76,
        "site_url": "https://kin.naver.com/",
        "login_url": "https://nid.naver.com/nidlogin.login",
        "write_url": "",
        "audience": "운행일지 작성법 검색자",
        "why": "'운행일지 쓰는 법' 질문에 도움이 되는 답 + 선택적 소개.",
        "tip": "답변 본문이 먼저. 도구는 '참고로' 한 줄.",
        "caution": "광고성 답변만 올리면 신고·저품질.",
    },
    {
        "id": "dc_gallery",
        "name": "디시인사이드 (갤러리)",
        "category": "커뮤니티",
        "kind": "community",
        "score": 45,
        "site_url": "https://gall.dcinside.com/",
        "login_url": "https://dcid.dcinside.com/join/login.php",
        "write_url": "",
        "audience": "일반 커뮤니티",
        "why": "트래픽은 크지만 홍보 거부감·규정 리스크 큼. 후순위.",
        "tip": "관련 갤만, 사용기 톤. 가능하면 비추천.",
        "caution": "광고 글 즉시 삭제·차단 흔함. 비추천 채널에 가깝음.",
    },
    {
        "id": "reddit_korea",
        "name": "Reddit (r/korea 등)",
        "category": "해외·영문",
        "kind": "community",
        "score": 40,
        "site_url": "https://www.reddit.com/r/korea/",
        "login_url": "https://www.reddit.com/login",
        "write_url": "",
        "audience": "영문·해외 거주",
        "why": "국내 타깃과 겹침 적음. 영어 버전 있을 때만.",
        "tip": "서브레딧 규칙 필수 확인. self-promo 비율 제한 흔함.",
        "caution": "한국어 온라인 서비스 홍보에는 우선순위 낮음.",
    },
    {
        "id": "indie_hackers_style",
        "name": "인디·사이드프로젝트 커뮤니티",
        "category": "개발·스타트업",
        "kind": "b2b",
        "score": 73,
        "site_url": "https://www.facebook.com/groups/",
        "login_url": "https://www.facebook.com/login",
        "write_url": "",
        "audience": "메이커·1인 창업",
        "why": "런칭 공유·피드백. 제품 스토리 환영하는 그룹 다수.",
        "tip": "FB 그룹 검색: '사이드프로젝트' '인디해커' '1인개발'.",
        "caution": "그룹마다 홍보 요일·양식 다름. 가입 후 규칙 읽기.",
    },
    {
        "id": "job_cafe",
        "name": "취업·이직 카페 (독취사 등)",
        "category": "네이버 카페",
        "kind": "community",
        "score": 58,
        "site_url": "https://cafe.naver.com/",
        "login_url": "https://nid.naver.com/nidlogin.login",
        "write_url": "",
        "audience": "구직·이직 준비생",
        "why": "영업·총무 취업 준비 중 일지 양식 관심 가능. 부차적.",
        "tip": "업무 스킬·양식 공유 톤. 취업 게시판 성격 맞추기.",
        "caution": "광고 금지 강한 곳 많음. 신중히.",
    },
]

# 초반 추천 기본 가중 (전환·작성 보조 용이 채널 우선)
_PRIORITY_BOOST = {
    "kakao_openchat": 8,
    "naver_cafe_biz": 6,
    "naver_blog": 6,
    "linkedin": 4,
    "naver_cafe_car": 4,
    "blind": 3,
    "tistory": 2,
    "threads": 2,
}


def list_categories() -> list[str]:
    cats = sorted({s["category"] for s in RECOMMENDED_SITES})
    return ["전체"] + cats


def list_kinds() -> list[str]:
    return ["전체", "community", "blog", "sns", "b2b", "qna"]


def get_site(site_id: str) -> dict[str, Any] | None:
    for s in RECOMMENDED_SITES:
        if s["id"] == site_id:
            return dict(s)
    return None


def all_sites() -> list[dict[str, Any]]:
    return [dict(s) for s in RECOMMENDED_SITES]


def _effective_score(site: dict[str, Any]) -> float:
    base = float(site.get("score", 50))
    boost = float(_PRIORITY_BOOST.get(site.get("id", ""), 0))
    return base + boost


def recommend(
    n: int = 8,
    category: str | None = None,
    kind: str | None = None,
    min_score: int = 0,
    shuffle: bool = True,
    exclude_low: bool = True,
) -> list[dict[str, Any]]:
    """
    홍보에 좋은 사이트를 점수 순으로 추천.

    - shuffle=True: 상위권 안에서 살짝 섞어 '다시 추천' 시 다양성 확보
    - exclude_low: score < 50 채널 제외 (디시·레딧 등 후순위)
    """
    items = all_sites()
    if category and category not in ("", "전체"):
        items = [s for s in items if s["category"] == category]
    if kind and kind not in ("", "전체"):
        items = [s for s in items if s["kind"] == kind]
    if min_score:
        items = [s for s in items if s["score"] >= min_score]
    if exclude_low:
        items = [s for s in items if s["score"] >= 50]

    # 점수 + 소량 랜덤으로 정렬 키
    ranked: list[tuple[float, dict[str, Any]]] = []
    for s in items:
        jitter = random.uniform(0, 6) if shuffle else 0.0
        ranked.append((_effective_score(s) + jitter, s))
    ranked.sort(key=lambda x: x[0], reverse=True)

    out = [s for _, s in ranked[: max(1, n)]]
    # 표시용 추천 점수 (100 캡)
    for s in out:
        s["recommend_score"] = min(100, int(round(_effective_score(s))))
    return out


def recommend_top(n: int = 6) -> list[dict[str, Any]]:
    """초반 기본 추천 (우선 채널 가중, 저점수 제외)."""
    return recommend(n=n, shuffle=True, exclude_low=True, min_score=65)


# 하위 호환 별칭
recommend_top_for_roadlog = recommend_top


def format_site_line(site: dict[str, Any]) -> str:
    score = site.get("recommend_score") or site.get("score", 0)
    return f"[{score:3d}] {site['name']}  ·  {site['category']}"


if __name__ == "__main__":
    print("=== 홍보 채널 추천 ===\n")
    for s in recommend_top(8):
        print(format_site_line(s))
        print(f"     {s['why']}")
        print(f"     → {s['site_url']}\n")
