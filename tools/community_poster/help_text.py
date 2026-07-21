"""사용 방법 안내 문구 (GUI 도움말 창)."""

from __future__ import annotations

from product_config import (  # noqa: E402
    PRODUCT_DISPLAY_NAME,
    PRODUCT_NAME_KO,
    PRODUCT_VERSION,
)

HELP_TITLE = f"사용 방법 · {PRODUCT_DISPLAY_NAME}"

HELP_BODY = f"""
【{PRODUCT_DISPLAY_NAME}】 v{PRODUCT_VERSION}
{PRODUCT_NAME_KO} — 홍보 글을 만들고, 올릴 곳을 정하고, 브라우저에서 올리는 도우미

━━━━━━━━━━━━━━━━━━━━
초간단 3단계 (이것만 하면 됩니다)
━━━━━━━━━━━━━━━━━━━━
① 내 사이트 주소 넣기 → 「홍보글 만들기」
② 올릴 곳 주소 + 아이디/비번 넣기
   (또는 「올릴 곳 고르기」로 선택)
③ 「브라우저에서 글 쓰기」→ 내용 확인 → 올리기는 직접

끝입니다.


━━━━━━━━━━━━━━━━━━━━
메뉴
━━━━━━━━━━━━━━━━━━━━
· 홈 …… 초간단 3단계 (평소 여기만)
· 자세히 …… 칸 찾기·게시판 등 고급 (필요할 때만)


━━━━━━━━━━━━━━━━━━━━
주의
━━━━━━━━━━━━━━━━━━━━
· 캡차·휴대폰 인증은 직접 하세요
· 「올리기」는 직접 누르는 것이 기본입니다
· 카페 규칙은 본인이 지켜야 합니다
· 같은 글 복붙 대신 「다른 버전 만들기」
""".strip()
