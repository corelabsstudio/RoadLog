"""
리치킷 — 제품 설정

범용 커뮤니티 홍보 도우미. 특정 서비스(예: 외부 SaaS)에 종속되지 않음.
"""

from __future__ import annotations

from pathlib import Path as _Path

# --- 제품 브랜딩 (판매·창 제목·바로가기 공통) ---
PRODUCT_NAME = "리치킷"  # 정식 표시명 (UI 100% 한글)
PRODUCT_NAME_EN = "ReachKit"  # 파일·내부 식별용 (UI 비표시)
PRODUCT_NAME_KO = "리치킷"
PRODUCT_DISPLAY_NAME = "리치킷"  # UI·바로가기 표시명
PRODUCT_VERSION = "0.5.3"
PRODUCT_TAGLINE = "3단계로 홍보 글 올리기"
PRODUCT_TAGLINE_EN = "AI-powered analyze · write · reach — with community guardrails."
PRODUCT_COMPANY = "코어랩스"

_ASSETS = _Path(__file__).resolve().parent / "assets"
ICON_ICO = _ASSETS / "icon.ico"
ICON_PNG = _ASSETS / "icon.png"

# 홍보 대상 사이트 — 기본값 비움 (사용자가 본인 제품 URL 입력)
DEFAULT_PRODUCT_URL = ""
VALIDATION_MODE_DEFAULT = True  # 결과 기록 모드 기본 ON

# 도배 방지 기본값
DEFAULT_MAX_POSTS_PER_DAY = 5
DEFAULT_COOLDOWN_MINUTES = 30
DEFAULT_SUBMIT_ENABLED = False  # 「올리기」버튼 자동 클릭 기본 끔
MIN_BODY_LEN = 40
MIN_TITLE_LEN = 5

# 지원 수준 라벨 (쉬운 말)
SUPPORT_LEVELS = {
    "guided": "안내만 — 문구 복사해서 직접 올리기 (추천)",
    "auto_write": "로그인 후 글 칸에 넣기 — 올리기는 직접",
    "auto_submit": "올리기까지 자동 — 고급·위험, 기본 꺼짐",
}
SUPPORT_LEVELS_SHORT = {
    "guided": "안내만",
    "auto_write": "글 칸에 넣기",
    "auto_submit": "올리기 자동",
}

# 이번 주 목표 (쉬운 말)
VALIDATION_GOALS = [
    "이번 주에 실제로 글·메시지를 5번 이상 올려 보기",
    "올린 것 중 절반 이상 성공하기 (결과 화면에서 확인)",
    "누가 가입하거나 문의하면 「가입·문의 기록」에 남기기",
    "「올리기」자동은 끈 채로, 직접 확인하고 올리기",
    "같은 글을 여러 곳에 그대로 복붙하지 않기",
    "이번 주는 아래 3곳만 쓰기 (블로그 · 오픈채팅 · 링크드인)",
]

# ---------------------------------------------------------------------------
# 이번 주 올릴 곳 3곳 (한꺼번에 여러 곳 도배 방지)
# ---------------------------------------------------------------------------
WEEKLY_VALIDATION_LABEL = "이번 주 올릴 곳"
WEEKLY_VALIDATION_CHANNELS: list[dict] = [
    {
        "id": "naver_blog",
        "slot": 1,
        "name": "네이버 블로그",
        "short": "블로그",
        "days": "월요일 · 목요일",
        "goal": "검색으로 손님 오기 + 리치킷으로 글 쓰기 연습",
        "why": "오래 쌓이면 검색으로 찾아옵니다. 글쓰기 화면 주소가 있어 쓰기도 쉽습니다.",
        "support": "auto_write",
        "site_url": "https://blog.naver.com/",
        "login_url": "https://nid.naver.com/nidlogin.login",
        "write_url": "https://blog.naver.com/GoBlogWrite.naver",
        "phrase_style": "사용 방법형",
        "checklist": [
            "네이버에 내 계정으로 로그인",
            "제목에 내 제품·서비스 관련 단어 넣기",
            "본문 맨 아래 내 사이트 링크 1개만",
            "리치킷으로 제목·본문 채운 뒤, 「올리기」는 직접 누르기",
            "결과 화면에서 성공/실패 확인",
        ],
        "success_ok": "글이 발행됐거나, 글쓰기 화면에 내용이 잘 들어감",
        "tip": "광고처럼 쓰지 말고 ‘이런 문제, 이렇게 해결’ 톤으로. 화면 캡처 1장 있으면 좋음.",
        "caution": "같은 글 복붙·키워드만 잔뜩 넣기 금지.",
    },
    {
        "id": "kakao_openchat",
        "slot": 2,
        "name": "카카오 오픈채팅",
        "short": "오픈채팅",
        "days": "화요일 · (선택) 금요일 짧게",
        "goal": "반응·가입 보기 + 짧은 문구 연습",
        "why": "말이 잘 통하면 반응이 빨리 옵니다. 프로그램이 대신 보내 주지는 않습니다.",
        "support": "guided",
        "site_url": "https://open.kakao.com/",
        "login_url": "",
        "write_url": "",
        "phrase_style": "짧은 버전",
        "checklist": [
            "내 손님과 맞는 방인지, 방 규칙 확인",
            "리치킷「짧은 버전」문구 복사",
            "인사 1줄 + 내 사이트 링크 1개만",
            "가격은 누가 물어보면 답하기",
            "가입·문의가 있으면 「가입·문의 기록」에 남기기",
        ],
        "success_ok": "메시지를 보냄 (리치킷은 문구·체크리스트만 도와줌)",
        "tip": "링크만 연달아 보내지 마세요. 방마다 홍보 가능 여부 확인.",
        "caution": "아무 방이나 도배하면 강퇴·계정 제재될 수 있음.",
    },
    {
        "id": "linkedin",
        "slot": 3,
        "name": "링크드인",
        "short": "링크드인",
        "days": "수요일 · (선택) 금요일",
        "goal": "회사·팀 담당자에게 알리기",
        "why": "업무용 인맥. 짧은 글 + 프로필 한 줄이 잘 맞습니다.",
        "support": "auto_write",
        "site_url": "https://www.linkedin.com/",
        "login_url": "https://www.linkedin.com/login",
        "write_url": "https://www.linkedin.com/preload/share",
        "phrase_style": "짧은 버전",
        "checklist": [
            "링크드인 로그인",
            "리치킷 짧은 버전으로 글 만든 뒤 말투만 다듬기",
            "필요하면 「팀 도입 문의 환영」 한 줄",
            "게시·올리기는 직접 누르기",
            "프로필 소개에 내 제품 한 줄 있으면 좋음",
        ],
        "success_ok": "글이 올라갔거나, 작성 화면에 내용이 잘 들어감",
        "tip": "쪽지 스팸은 하지 마세요. 피드에 글 올리는 쪽을 권장.",
        "caution": "같은 문장 반복 게시는 도달이 떨어질 수 있음.",
    },
]


def get_weekly_channel(channel_id: str) -> dict | None:
    for ch in WEEKLY_VALIDATION_CHANNELS:
        if ch["id"] == channel_id:
            return dict(ch)
    return None


def support_label(support_id: str, *, short: bool = False) -> str:
    table = SUPPORT_LEVELS_SHORT if short else SUPPORT_LEVELS
    return table.get(support_id, support_id)


def weekly_plan_text() -> str:
    lines = [
        f"【{WEEKLY_VALIDATION_LABEL}】",
        "한꺼번에 여러 곳 올리지 마세요.",
        "· 이번 주는 이 3곳만",
        "· 한 곳당 주 1~2번",
        "· 「올리기」는 직접 누르기",
        "· 같은 글이면 「다른 버전 만들기」로 바꾸기",
        "",
    ]
    for ch in WEEKLY_VALIDATION_CHANNELS:
        lines.append(
            f"{ch['slot']}. {ch['name']}  ({ch['days']})"
            f"\n   목표: {ch['goal']}"
            f"\n   도움: {support_label(ch['support'], short=True)} · 글 스타일: {ch['phrase_style']}"
            f"\n   성공: {ch['success_ok']}"
            f"\n   팁: {ch['tip']}"
        )
        lines.append("")
    lines.append(
        "이번 주 목표: 5번 이상 올려 보기 "
        "(예: 블로그 2 + 오픈채팅 2 + 링크드인 1) · 성공 절반 이상"
    )
    return "\n".join(lines)


DISCLAIMER_SHORT = (
    "리치킷은 홍보 글 작성을 돕는 프로그램입니다. "
    "카페 규칙은 본인이 지키고, 캡차·올리기는 직접 하세요."
)

DISCLAIMER_FULL = """
【이용 안내】

1. 리치킷이 돕는 것
   · 내 사이트 살펴보기
   · 홍보 제목·본문 만들기
   · 어디에 올리면 좋은지 안내
   · 글 쓰는 화면 찾아 두기
   · 제목·본문 입력 도와주기

2. 본인이 할 일
   · 카페·사이트 규칙 지키기
   · 가입·캡차·휴대폰 인증 (보통 1번)
   · 내용 확인 후 「올리기」 누르기

3. 「올리기」 자동은 기본이 꺼져 있습니다.
   켜더라도 게시판과 내용을 꼭 확인하세요.

4. 비밀번호는 이 컴퓨터에만 저장할 수 있습니다.
   공용 컴퓨터에서는 저장하지 마세요.

5. 결과(성공·실패·가입 기록)는 이 컴퓨터에만 남습니다.
   밖으로 보내지 않습니다.

계속하면 위 내용에 동의하는 것으로 봅니다.
""".strip()

STRUCTURE_SCAN_HINT = (
    "글을 올릴 사이트 주소를 넣은 뒤 「글 쓰는 칸 찾기」를 누르세요. "
    "로그인 칸·제목 칸·본문 칸 위치를 찾아 저장합니다. "
    "가입·캡차·휴대폰 인증은 직접 해 주세요. (프로그램이 대신하지 않음)"
)
