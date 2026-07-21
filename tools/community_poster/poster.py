"""
커뮤니티 글쓰기 자동화 (Playwright).

사이트마다 HTML이 달라 100% 성공을 보장하지 않습니다.
- 브라우저를 띄운 채 동작 (headed)
- 캡차·2단계 인증·이상 로그인 차단은 사용자가 직접 처리
- 최종 등록 전 확인 모드 기본
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

LogFn = Callable[[str], None]


def _noop_log(msg: str) -> None:
    print(msg)


@dataclass
class PostJob:
    site_url: str
    username: str
    password: str
    title: str
    body: str
    write_url: str = ""  # 비우면 사이트에서 '글쓰기' 링크 탐색
    login_url: str = ""  # 비우면 메인에서 로그인 폼 탐색
    board_url: str = ""  # 게시판 목록 URL — 여기 들어가 글쓰기 탐색
    submit: bool = False  # True면 등록 버튼까지 클릭
    headless: bool = False
    slow_mo_ms: int = 80
    timeout_ms: int = 25_000
    # 사이트 전용 선택자 (비우면 휴리스틱)
    selectors: dict[str, str] = field(default_factory=dict)
    # True면 로그인 후 게시판을 자동 고르고(최고점) 작성
    auto_pick_board: bool = False


@dataclass
class PostResult:
    ok: bool
    message: str
    final_url: str = ""
    board_name: str = ""
    board_url: str = ""


@dataclass
class BoardCandidate:
    name: str
    url: str
    score: int
    reason: str
    write_url: str = ""


@dataclass
class DiscoverResult:
    ok: bool
    message: str
    boards: list[BoardCandidate] = field(default_factory=list)
    final_url: str = ""


# 일반 홍보에 비교적 적합한 게시판 키워드 (가점)
BOARD_GOOD_KEYWORDS: list[tuple[str, int, str]] = [
    ("홍보", 40, "홍보 게시판"),
    ("광고", 15, "광고(규정 확인)"),
    ("정보공유", 38, "정보 공유"),
    ("정보", 28, "정보"),
    ("팁", 32, "팁·노하우"),
    ("노하우", 32, "노하우"),
    ("사용기", 34, "사용기"),
    ("후기", 30, "후기"),
    ("리뷰", 28, "리뷰"),
    ("자유게시판", 30, "자유게시판"),
    ("자유", 22, "자유"),
    ("일상", 12, "일상"),
    ("잡담", 10, "잡담"),
    ("비즈니스", 36, "비즈니스"),
    ("사업", 30, "사업"),
    ("자영업", 34, "자영업"),
    ("영업", 36, "영업"),
    ("창업", 32, "창업"),
    ("스타트업", 30, "스타트업"),
    ("직장", 24, "직장"),
    ("업무", 26, "업무"),
    ("생산성", 34, "생산성"),
    ("툴", 22, "툴·도구"),
    ("도구", 22, "도구"),
    ("소프트웨어", 24, "소프트웨어"),
    ("IT", 18, "IT"),
    ("자기소개", 20, "자기소개"),
    ("가입인사", 8, "가입인사"),
    ("질문", 14, "Q&A"),
    ("q&a", 14, "Q&A"),
    ("qa", 12, "Q&A"),
    ("free", 26, "free board"),
    ("promo", 20, "promo"),
    ("general", 18, "general"),
    ("community", 16, "community"),
    ("board", 8, "board"),
    ("게시판", 6, "게시판"),
]

# 가급적 피할 키워드 (감점)
BOARD_BAD_KEYWORDS: list[tuple[str, int, str]] = [
    ("공지", -50, "공지"),
    ("공지사항", -55, "공지사항"),
    ("관리자", -60, "관리자"),
    ("신고", -40, "신고"),
    ("정치", -35, "정치"),
    ("연예", -30, "연예"),
    ("성인", -80, "성인"),
    ("19금", -80, "19금"),
    ("중고거래", -25, "중고거래"),
    ("장터", -25, "장터"),
    ("구매", -15, "구매"),
    ("갤러리", -5, "갤러리"),
]


# 흔한 로그인 / 글쓰기 선택자 후보
USER_SELECTORS = [
    'input[name="mb_id"]',
    'input[name="user_id"]',
    'input[name="userid"]',
    'input[name="uid"]',
    'input[name="id"]',
    'input[name="member_id"]',
    'input[name="username"]',
    'input[name="email"]',
    'input[name="loginId"]',
    'input[id="mb_id"]',
    'input[id="user_id"]',
    'input[id="userid"]',
    'input[id="username"]',
    'input[id="loginId"]',
    'input[type="email"]',
    'input[autocomplete="username"]',
    'input[placeholder*="아이디"]',
    'input[placeholder*="ID"]',
    'input[placeholder*="이메일"]',
    'input[name*="user" i]',
    'input[name*="login" i]:not([type="password"])',
]

PASS_SELECTORS = [
    'input[type="password"]',
    'input[name="mb_password"]',
    'input[name="password"]',
    'input[name="passwd"]',
    'input[name="user_pw"]',
    'input[name="user_password"]',
    'input[autocomplete="current-password"]',
]

LOGIN_BTN_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("로그인")',
    'input[value*="로그인"]',
    'a:has-text("로그인")',
    'button:has-text("Login")',
    'button:has-text("Sign in")',
]

TITLE_SELECTORS = [
    'input[name="wr_subject"]',
    'input[name="subject"]',
    'input[name="title"]',
    'input[name="bd_title"]',
    'input[name="article_title"]',
    'input[id="wr_subject"]',
    'input[id="subject"]',
    'input[id="title"]',
    'input[placeholder*="제목"]',
    'input[aria-label*="제목"]',
]

BODY_SELECTORS = [
    'textarea[name="wr_content"]',
    'textarea[name="content"]',
    'textarea[name="bd_content"]',
    'textarea[name="article_content"]',
    'textarea[id="wr_content"]',
    'textarea[id="content"]',
    'textarea[placeholder*="내용"]',
    'textarea[placeholder*="본문"]',
    'div.note-editable[contenteditable="true"]',
    'div.ql-editor[contenteditable="true"]',
    'div[contenteditable="true"].ProseMirror',
    'div[contenteditable="true"]',
    'iframe.cke_wysiwyg_frame',
    'iframe[title*="편집"]',
    'iframe[id*="editor"]',
]

WRITE_LINK_TEXTS = [
    "글쓰기",
    "글 쓰기",
    "새 글",
    "새글",
    "게시글 작성",
    "작성하기",
    "Write",
    "Post",
    "Write a post",
]

SUBMIT_SELECTORS = [
    'button:has-text("등록")',
    'button:has-text("작성")',
    'button:has-text("저장")',
    'button:has-text("올리기")',
    'button:has-text("게시")',
    'button:has-text("완료")',
    'input[type="submit"][value*="등록"]',
    'input[type="submit"][value*="작성"]',
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Submit")',
    'button:has-text("Publish")',
]


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def _first_visible(page, selectors: list[str], timeout: int = 1500):
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            if loc.is_visible(timeout=timeout):
                return loc
        except Exception:
            continue
    return None


def _fill_first(page, selectors: list[str], value: str, log: LogFn) -> bool:
    el = _first_visible(page, selectors)
    if not el:
        return False
    try:
        el.click(timeout=3000)
        el.fill(value, timeout=5000)
        log(f"  입력 완료: {selectors[0] if len(selectors) == 1 else el}")
        return True
    except Exception as e:
        try:
            el.fill(value, timeout=5000)
            return True
        except Exception:
            log(f"  입력 실패: {e}")
            return False


def _click_first(page, selectors: list[str], log: LogFn) -> bool:
    el = _first_visible(page, selectors, timeout=2000)
    if not el:
        return False
    try:
        el.click(timeout=5000)
        return True
    except Exception as e:
        log(f"  클릭 실패: {e}")
        return False


def _try_login(page, job: PostJob, log: LogFn) -> bool:
    custom = job.selectors or {}
    user_sels = [custom["username"]] if custom.get("username") else USER_SELECTORS
    pass_sels = [custom["password"]] if custom.get("password") else PASS_SELECTORS
    btn_sels = [custom["login_button"]] if custom.get("login_button") else LOGIN_BTN_SELECTORS

    # 이미 로그인된 경우 (로그아웃 링크 등)
    try:
        if page.locator('a:has-text("로그아웃"), a:has-text("Logout"), button:has-text("로그아웃")').first.is_visible(
            timeout=1200
        ):
            log("이미 로그인된 세션으로 보입니다.")
            return True
    except Exception:
        pass

    user_ok = _fill_first(page, user_sels, job.username, log)
    pass_ok = _fill_first(page, pass_sels, job.password, log)
    if not user_ok or not pass_ok:
        log("로그인 입력칸을 찾지 못했습니다. 브라우저에서 직접 로그인해 주세요.")
        log("로그인 후 이 창이 30초 대기합니다…")
        page.wait_for_timeout(30_000)
        return True

    if not _click_first(page, btn_sels, log):
        # Enter 키 시도
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass

    page.wait_for_timeout(2000)
    log("로그인 제출 시도 완료. 캡차가 있으면 직접 풀어 주세요 (최대 60초 대기).")
    page.wait_for_timeout(3000)

    # CAPTCHA/추가 인증 여유
    for i in range(12):
        try:
            if page.locator('input[type="password"]').first.is_visible(timeout=500):
                # 아직 로그인 폼이면 대기
                page.wait_for_timeout(5000)
                continue
        except Exception:
            break
        page.wait_for_timeout(2000)
    return True


def _score_board_text(text: str) -> tuple[int, str]:
    """게시판 이름·URL 텍스트로 홍보 적합 점수."""
    t = (text or "").lower()
    t_raw = text or ""
    score = 0
    reasons: list[str] = []
    for kw, pts, label in BOARD_GOOD_KEYWORDS:
        if kw.lower() in t or kw in t_raw:
            score += pts
            if label not in reasons:
                reasons.append(label)
    for kw, pts, label in BOARD_BAD_KEYWORDS:
        if kw.lower() in t or kw in t_raw:
            score += pts
            if label not in reasons:
                reasons.append(f"주의:{label}")
    if not reasons:
        reasons.append("일반 링크")
    return score, ", ".join(reasons[:4])


def guess_write_url_from_board(board_url: str) -> str:
    """게시판 목록 URL에서 글쓰기 URL 추정 (그누보드·공통 패턴)."""
    url = _normalize_url(board_url)
    if not url:
        return ""
    # 이미 write면 그대로
    if re.search(r"write\.php|write\b|/new\b|/create\b", url, re.I):
        return url
    # 그누보드: board.php / list.php ?bo_table=
    m = re.search(r"[?&]bo_table=([^&]+)", url, re.I)
    if m:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/bbs/write.php?bo_table={m.group(1)}"
    # board.php?id= / bbs/board.php
    if "board.php" in url.lower():
        return re.sub(r"board\.php", "write.php", url, flags=re.I)
    if re.search(r"/list\.php", url, re.I):
        return re.sub(r"/list\.php", "/write.php", url, flags=re.I)
    # path/board/xxx → path/board/xxx/write
    if re.search(r"/board/[^/?#]+/?$", url, re.I):
        return url.rstrip("/") + "/write"
    if re.search(r"/boards?/[^/?#]+/?$", url, re.I):
        return url.rstrip("/") + "/new"
    # cafe.naver ArticleList → write is complex; leave empty
    if "cafe.naver.com" in url.lower():
        return ""
    return ""


def _collect_board_links(page, base_url: str, log: LogFn) -> list[BoardCandidate]:
    """페이지 내 a 태그에서 게시판 후보 수집·점수화."""
    base_host = urlparse(base_url).netloc.lower().replace("www.", "")
    raw: list[dict[str, str]] = []
    try:
        raw = page.evaluate(
            """() => {
                const out = [];
                const seen = new Set();
                for (const a of document.querySelectorAll('a[href]')) {
                    const href = a.href || '';
                    let text = (a.innerText || a.textContent || a.getAttribute('title') || '').trim();
                    text = text.replace(/\\s+/g, ' ').slice(0, 80);
                    if (!href || href.startsWith('javascript:') || href === '#' || href.endsWith('#')) continue;
                    if (!text || text.length < 2) continue;
                    const key = href.split('#')[0] + '|' + text;
                    if (seen.has(key)) continue;
                    seen.add(key);
                    out.push({ href, text });
                    if (out.length >= 400) break;
                }
                return out;
            }"""
        )
    except Exception as e:
        log(f"링크 수집 실패: {e}")
        return []

    # 게시판성 URL 힌트
    boardish = re.compile(
        r"bo_table=|board\.php|bbs/|/board/|/boards/|/forum/|/community/"
        r"|ArticleList|cafe\.naver|/gallery/|list\.php|mid=|menu_id=|/cafes?/",
        re.I,
    )
    skip_url = re.compile(
        r"logout|login|signin|signup|register|join|password|cart|admin\.php"
        r"|javascript:|mailto:|tel:",
        re.I,
    )
    skip_text = re.compile(
        r"^(홈|home|login|로그인|로그아웃|회원가입|검색|더보기|close|닫기|\d+)$",
        re.I,
    )

    scored: dict[str, BoardCandidate] = {}
    for item in raw or []:
        href = (item.get("href") or "").strip()
        text = (item.get("text") or "").strip()
        if not href or not text:
            continue
        if skip_url.search(href) or skip_text.match(text):
            continue
        try:
            host = urlparse(href).netloc.lower().replace("www.", "")
        except Exception:
            continue
        # 외부 광고·SNS 제외 (같은 사이트·서브도메인만)
        if host and base_host and not (host == base_host or host.endswith("." + base_host) or base_host.endswith("." + host)):
            # 네이버 카페 등: section.cafe / cafe.naver 허용
            if not (base_host.endswith("naver.com") and "naver.com" in host):
                if not (base_host.endswith("daum.net") and "daum.net" in host):
                    continue

        blob = f"{text} {href}"
        score, reason = _score_board_text(blob)
        # URL이 게시판 형태면 가점
        if boardish.search(href):
            score += 18
            if "게시판형 주소" not in reason:
                reason = (reason + ", 게시판형 주소").strip(", ")
        # 너무 긴 글 제목 링크 감점 (목록 글일 가능성)
        if len(text) > 40:
            score -= 12
        # 최소 점수 미달 + 게시판형도 아니면 스킵
        if score < 12 and not boardish.search(href):
            continue

        write_u = guess_write_url_from_board(href)
        # 동일 URL은 높은 점수 유지
        prev = scored.get(href)
        if prev is None or score > prev.score:
            scored[href] = BoardCandidate(
                name=text[:60],
                url=href,
                score=score,
                reason=reason,
                write_url=write_u,
            )

    boards = sorted(scored.values(), key=lambda b: b.score, reverse=True)
    # 상위만
    return boards[:40]


def _click_write_on_page(page, log: LogFn) -> bool:
    """현재 페이지에서 글쓰기 링크/버튼 클릭."""
    for text in WRITE_LINK_TEXTS:
        try:
            link = page.get_by_role("link", name=re.compile(text, re.I)).first
            if link.is_visible(timeout=800):
                log(f"글쓰기 링크 클릭: {text}")
                link.click(timeout=5000)
                page.wait_for_timeout(1500)
                return True
        except Exception:
            pass
        try:
            btn = page.get_by_role("button", name=re.compile(text, re.I)).first
            if btn.is_visible(timeout=500):
                log(f"글쓰기 버튼 클릭: {text}")
                btn.click(timeout=5000)
                page.wait_for_timeout(1500)
                return True
        except Exception:
            pass
        try:
            el = page.locator(f'a:has-text("{text}"), button:has-text("{text}")').first
            if el.is_visible(timeout=500):
                el.click(timeout=5000)
                page.wait_for_timeout(1500)
                return True
        except Exception:
            pass
    return False


def _page_has_write_form(page, timeout: int = 1500) -> bool:
    return bool(_first_visible(page, TITLE_SELECTORS + BODY_SELECTORS, timeout=timeout))


def _url_looks_like_write_dead_end(url: str) -> bool:
    """글쓰기 화면이 아닌 검색·홈 등 — 자동 성공으로 치면 안 되는 주소."""
    u = (url or "").lower()
    bad = (
        "search.naver.com",
        "search.google.",
        "search.daum.net",
        "/search?",
        "where=nexearch",
        "where=nv",
    )
    return any(b in u for b in bad)


def _goto_write(page, job: PostJob, log: LogFn) -> bool:
    # 0) 게시판 목록으로 먼저 이동 후 글쓰기 탐색
    if job.board_url:
        board = _normalize_url(job.board_url)
        log(f"게시판으로 이동: {board}")
        try:
            page.goto(board, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
        except Exception as e:
            log(f"게시판 이동 실패: {e}")
        # 추정 글쓰기 URL
        guessed = guess_write_url_from_board(board)
        if guessed and guessed != board:
            try:
                log(f"추정 글쓰기 주소 시도: {guessed}")
                page.goto(guessed, wait_until="domcontentloaded", timeout=12_000)
                page.wait_for_timeout(1000)
                if _page_has_write_form(page, 1200):
                    log("글쓰기 폼 발견 (추정 주소)")
                    return True
            except Exception:
                page.goto(board, wait_until="domcontentloaded")
                page.wait_for_timeout(800)
        if _click_write_on_page(page, log) and _page_has_write_form(page, 2000):
            return True

    if job.write_url:
        url = _normalize_url(job.write_url)
        log(f"글쓰기 주소로 이동: {url}")
        try:
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
        except Exception as e:
            log(f"글쓰기 주소 이동 실패: {e}")
        if _page_has_write_form(page, 2000):
            return True
        # write_url이 게시판 목록일 수 있음
        if _click_write_on_page(page, log) and _page_has_write_form(page, 2000):
            return True
        # 폼이 늦게 뜨는 사이트(네이버 등) — 조금 더 대기 후 재확인
        log("글쓰기 칸이 바로 안 보입니다. 15초 더 기다립니다…")
        page.wait_for_timeout(15_000)
        if _page_has_write_form(page, 3000):
            return True
        log("글쓰기 주소로 갔지만 제목·본문 칸을 찾지 못했습니다.")
        return False

    custom = (job.selectors or {}).get("write_link")
    if custom:
        try:
            page.locator(custom).first.click(timeout=5000)
            page.wait_for_timeout(1500)
            if _page_has_write_form(page, 2000):
                return True
        except Exception as e:
            log(f"커스텀 글쓰기 링크 실패: {e}")

    if _click_write_on_page(page, log) and _page_has_write_form(page, 2000):
        return True

    # URL 패턴 추정 (그누보드 등)
    base = job.site_url.rstrip("/")
    candidates = [
        f"{base}/bbs/write.php",
        f"{base}/bbs/write.php?bo_table=free",
        f"{base}/write",
        f"{base}/board/write",
        f"{base}/post/new",
    ]
    parsed = urlparse(job.site_url)
    if "bo_table=" in job.site_url:
        m = re.search(r"bo_table=([^&]+)", job.site_url)
        if m:
            candidates.insert(0, f"{parsed.scheme}://{parsed.netloc}/bbs/write.php?bo_table={m.group(1)}")

    log("글쓰기 링크를 못 찾았습니다. 추정 주소를 시도합니다…")
    for u in candidates:
        try:
            page.goto(u, wait_until="domcontentloaded", timeout=10_000)
            page.wait_for_timeout(800)
            if _page_has_write_form(page, 1000):
                log(f"글쓰기 폼 발견: {u}")
                return True
        except Exception:
            continue

    log("글쓰기 페이지를 자동으로 찾지 못했습니다. 브라우저에서 글쓰기 화면으로 이동해 주세요 (60초).")
    page.wait_for_timeout(60_000)
    if _page_has_write_form(page, 3000):
        log("글쓰기 폼 확인됨 (직접 이동)")
        return True
    log("대기 후에도 글쓰기 칸을 찾지 못했습니다.")
    return False


def _login_session(page, job: PostJob, log: LogFn) -> None:
    """로그인 페이지 이동 + 로그인 시도 (공통)."""
    start = _normalize_url(job.login_url) if job.login_url else job.site_url
    log(f"이동: {start}")
    page.goto(start, wait_until="domcontentloaded")
    page.wait_for_timeout(1000)

    try:
        login_link = page.locator(
            'a:has-text("로그인"), a:has-text("Login"), a:has-text("Sign in")'
        ).first
        if login_link.is_visible(timeout=1500):
            if not _first_visible(page, PASS_SELECTORS, timeout=500):
                login_link.click()
                page.wait_for_timeout(1200)
    except Exception:
        pass

    log("로그인 시도…")
    _try_login(page, job, log)


def discover_boards(job: PostJob, log: LogFn | None = None) -> DiscoverResult:
    """
    로그인 후 사이트에서 홍보에 적합한 게시판/카테고리 링크를 자동 수집·점수화.
    사이트마다 HTML이 달라 100%는 보장하지 않습니다.
    """
    log = log or _noop_log
    job.site_url = _normalize_url(job.site_url)
    if not job.site_url:
        return DiscoverResult(False, "사이트 주소를 입력하세요.")
    if not job.username or not job.password:
        return DiscoverResult(False, "아이디와 비밀번호를 입력하세요.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return DiscoverResult(
            False,
            "브라우저 자동화(플레이라이트)가 없습니다. 설치: pip install playwright 후 playwright install chromium",
        )

    log(f"[게시판 탐색] 대상: {job.site_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=job.headless, slow_mo=job.slow_mo_ms)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
        )
        page = context.new_page()
        page.set_default_timeout(job.timeout_ms)

        try:
            _login_session(page, job, log)

            # 메인·사이트 루트에서 링크 수집
            pages_to_scan = []
            cur = page.url
            pages_to_scan.append(cur)
            site = job.site_url.rstrip("/")
            if site not in pages_to_scan:
                pages_to_scan.append(site)

            all_boards: dict[str, BoardCandidate] = {}
            for u in pages_to_scan:
                try:
                    if page.url.rstrip("/") != u.rstrip("/"):
                        log(f"탐색 페이지: {u}")
                        page.goto(u, wait_until="domcontentloaded")
                        page.wait_for_timeout(1200)
                except Exception as e:
                    log(f"  이동 실패: {e}")
                    continue
                found = _collect_board_links(page, job.site_url, log)
                log(f"  후보 {len(found)}개")
                for b in found:
                    prev = all_boards.get(b.url)
                    if prev is None or b.score > prev.score:
                        all_boards[b.url] = b

            # 사이드 메뉴 더 펼치기 시도 (간단)
            try:
                for lab in ("게시판", "커뮤니티", "메뉴", "전체", "카테고리"):
                    el = page.locator(f'a:has-text("{lab}"), button:has-text("{lab}")').first
                    if el.is_visible(timeout=400):
                        el.click(timeout=2000)
                        page.wait_for_timeout(800)
                        for b in _collect_board_links(page, job.site_url, log):
                            prev = all_boards.get(b.url)
                            if prev is None or b.score > prev.score:
                                all_boards[b.url] = b
                        break
            except Exception:
                pass

            boards = sorted(all_boards.values(), key=lambda x: x.score, reverse=True)[:25]
            final = page.url
            # 결과 확인용 짧게 대기
            page.wait_for_timeout(2000)
            browser.close()

            if not boards:
                return DiscoverResult(
                    False,
                    "게시판을 자동으로 찾지 못했습니다. "
                    "사이트 주소에 게시판 목록 주소를 넣거나, 글쓰기 페이지를 직접 지정해 주세요.",
                    boards=[],
                    final_url=final,
                )

            log(f"추천 게시판 {len(boards)}개 (상위 점수 순)")
            for i, b in enumerate(boards[:8], 1):
                log(f"  {i}. [{b.score}] {b.name} — {b.reason}")

            return DiscoverResult(
                True,
                f"게시판 {len(boards)}개를 찾았습니다. 점수가 높은 순으로 골라 주세요.",
                boards=boards,
                final_url=final,
            )
        except Exception as e:
            try:
                page.wait_for_timeout(3000)
                browser.close()
            except Exception:
                pass
            return DiscoverResult(False, f"탐색 오류: {e}")


def _fill_post(page, job: PostJob, log: LogFn) -> tuple[bool, bool]:
    """제목·본문 입력. (title_ok, body_ok) 반환 — 둘 다 True여야 자동 작성 성공."""
    custom = job.selectors or {}
    title_sels = [custom["title"]] if custom.get("title") else TITLE_SELECTORS
    body_sels = [custom["body"]] if custom.get("body") else BODY_SELECTORS

    title_ok = _fill_first(page, title_sels, job.title, log)
    if not title_ok:
        log("제목 칸을 찾지 못했습니다.")

    # 본문: textarea 우선, 그다음 contenteditable, iframe
    body_ok = False
    for sel in body_sels:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            tag = loc.evaluate("el => el.tagName.toLowerCase()")
            if tag == "iframe":
                frame = loc.content_frame()
                if frame:
                    editable = frame.locator("body, body[contenteditable='true'], .cke_editable").first
                    editable.click(timeout=3000)
                    # 기존 내용 지우고 입력
                    try:
                        editable.fill(job.body)
                    except Exception:
                        editable.evaluate(
                            "(el, text) => { el.focus(); el.innerText = text; el.innerHTML = text.replace(/\\n/g,'<br>'); }",
                            job.body,
                        )
                    body_ok = True
                    log("  본문(iframe 에디터) 입력 완료")
                    break
            elif tag == "textarea":
                loc.click(timeout=3000)
                loc.fill(job.body, timeout=5000)
                body_ok = True
                log("  본문(textarea) 입력 완료")
                break
            else:
                # contenteditable
                loc.click(timeout=3000)
                loc.evaluate(
                    """(el, text) => {
                        el.focus();
                        el.innerText = text;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    }""",
                    job.body,
                )
                body_ok = True
                log("  본문(contenteditable) 입력 완료")
                break
        except Exception:
            continue

    if not body_ok:
        log("본문 칸을 자동 입력하지 못했습니다. 클립보드에 본문을 넣었으니 붙여넣기 하세요.")
        try:
            page.evaluate(
                """async (text) => { await navigator.clipboard.writeText(text); }""",
                job.body,
            )
        except Exception:
            pass

    return title_ok, body_ok


def _try_submit(page, job: PostJob, log: LogFn) -> bool:
    custom = (job.selectors or {}).get("submit")
    sels = [custom] if custom else SUBMIT_SELECTORS
    if _click_first(page, sels, log):
        page.wait_for_timeout(2000)
        return True
    log("등록 버튼을 찾지 못했습니다. 직접 눌러 주세요.")
    return False


def run_post(job: PostJob, log: LogFn | None = None) -> PostResult:
    log = log or _noop_log
    job.site_url = _normalize_url(job.site_url)
    if not job.site_url:
        return PostResult(False, "사이트 주소를 입력하세요.")
    if not job.username or not job.password:
        return PostResult(False, "아이디와 비밀번호를 입력하세요.")
    if not (job.title or "").strip():
        return PostResult(False, "제목을 입력하세요.")
    if not (job.body or "").strip():
        return PostResult(False, "본문을 입력하세요.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return PostResult(
            False,
            "브라우저 자동화(플레이라이트)가 없습니다. 터미널에서:\n"
            "  pip install playwright\n"
            "  playwright install chromium",
        )

    log(f"대상: {job.site_url}")
    log(f"제출 모드: {'등록까지 클릭' if job.submit else '작성만 (등록은 직접)'}")

    board_name = ""
    board_url_used = job.board_url or ""

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=job.headless, slow_mo=job.slow_mo_ms)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ko-KR",
        )
        page = context.new_page()
        page.set_default_timeout(job.timeout_ms)

        try:
            log("1) 로그인 시도…")
            _login_session(page, job, log)

            # 스마트: 게시판 자동 선택
            if job.auto_pick_board and not job.board_url and not job.write_url:
                log("1.5) 적합한 게시판 자동 탐색…")
                try:
                    if page.url.rstrip("/") != job.site_url.rstrip("/"):
                        page.goto(job.site_url, wait_until="domcontentloaded")
                        page.wait_for_timeout(1000)
                except Exception:
                    pass
                found = _collect_board_links(page, job.site_url, log)
                # 사이트 루트도
                try:
                    page.goto(job.site_url, wait_until="domcontentloaded")
                    page.wait_for_timeout(800)
                    for b in _collect_board_links(page, job.site_url, log):
                        if not any(x.url == b.url for x in found):
                            found.append(b)
                except Exception:
                    pass
                found = sorted(found, key=lambda x: x.score, reverse=True)
                if found:
                    best = found[0]
                    job.board_url = best.url
                    if best.write_url:
                        job.write_url = best.write_url
                    board_name = best.name
                    board_url_used = best.url
                    log(f"자동 선택 게시판: [{best.score}] {best.name} — {best.reason}")
                    log(f"  → {best.url}")
                else:
                    log("자동 게시판을 못 찾았습니다. 기본 글쓰기 탐색으로 진행합니다.")

            log("2) 글쓰기 화면으로…")
            on_write = _goto_write(page, job, log)
            final = page.url
            if not on_write:
                log("글쓰기 화면을 열지 못했습니다. 브라우저를 2분 열어둡니다 (직접 이동·작성).")
                try:
                    page.wait_for_timeout(120_000)
                    final = page.url
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass
                return PostResult(
                    False,
                    "글쓰기 화면·입력 칸을 찾지 못했습니다. 글이 자동으로 쓰이지 않았습니다.\n"
                    f"(마지막 주소: {final})",
                    final_url=final,
                    board_name=board_name,
                    board_url=board_url_used,
                )

            if _url_looks_like_write_dead_end(page.url):
                log(f"현재 주소가 글쓰기 화면이 아닙니다: {page.url}")
                try:
                    page.wait_for_timeout(60_000)
                    final = page.url
                except Exception:
                    pass
                try:
                    browser.close()
                except Exception:
                    pass
                return PostResult(
                    False,
                    "검색·다른 화면으로 열려 글을 쓰지 못했습니다. 다시 시도해 주세요.\n"
                    f"(주소: {page.url})",
                    final_url=final or page.url,
                    board_name=board_name,
                    board_url=board_url_used,
                )

            log("3) 제목·본문 입력…")
            title_ok, body_ok = _fill_post(page, job, log)
            wrote = title_ok and body_ok
            if title_ok and not body_ok:
                log("제목만 들어갔습니다. 본문은 직접 붙여넣기 해 주세요.")
            elif body_ok and not title_ok:
                log("본문만 들어갔습니다. 제목은 직접 입력해 주세요.")
            elif not wrote:
                log("제목·본문 모두 자동 입력에 실패했습니다.")

            # 부분 입력·실패 시에도 사용자가 마무리할 수 있게 브라우저 유지
            hold_ms = 300_000 if wrote and not job.submit else 180_000  # 성공 5분 / 실패·부분 3분

            if job.submit and wrote:
                log("4) 등록 버튼 클릭…")
                submitted = _try_submit(page, job, log)
                log("등록을 시도했습니다. 결과를 브라우저에서 확인하세요 (15초).")
                page.wait_for_timeout(15_000)
                final = page.url
                try:
                    browser.close()
                except Exception:
                    pass
                if submitted:
                    msg = "올리기 버튼까지 눌렀습니다. 실제 등록 여부는 사이트에서 확인하세요."
                else:
                    msg = "제목·본문은 넣었지만 올리기 버튼을 찾지 못했습니다. 직접 등록해 주세요."
                if board_name:
                    msg = f"게시판「{board_name}」— {msg}"
                return PostResult(
                    submitted,  # 버튼 클릭 실패면 부분 성공이 아니라 False에 가깝게
                    msg if submitted else msg,
                    final_url=final,
                    board_name=board_name,
                    board_url=board_url_used,
                )

            # 작성만 (기본) 또는 입력 실패
            if wrote:
                log("4) 제목·본문 입력 완료. 「올리기」는 직접 눌러 주세요.")
                log(f"브라우저를 {hold_ms // 60_000}분 열어둡니다. 확인·등록 후 창이 닫혀도 됩니다.")
                msg = (
                    "제목·본문을 칸에 넣었습니다. 브라우저에서 확인한 뒤 「올리기」는 직접 누르세요.\n"
                    f"(브라우저 약 {hold_ms // 60_000}분 유지 — 발행 완료가 아닙니다)"
                )
                ok = True
            else:
                log(f"4) 자동 작성 실패. 브라우저를 {hold_ms // 60_000}분 열어둡니다 (직접 작성).")
                msg = (
                    "제목·본문을 자동으로 넣지 못했습니다. 글이 써진 상태가 아닙니다.\n"
                    "브라우저가 잠시 열려 있으면 직접 붙여넣기 할 수 있습니다."
                )
                ok = False

            try:
                page.wait_for_timeout(hold_ms)
                final = page.url
            except Exception:
                final = page.url
            try:
                browser.close()
            except Exception:
                pass
            if board_name and ok:
                msg = f"게시판「{board_name}」— {msg}"
            return PostResult(
                ok,
                msg,
                final_url=final,
                board_name=board_name,
                board_url=board_url_used,
            )
        except Exception as e:
            try:
                page.wait_for_timeout(10_000)
                browser.close()
            except Exception:
                pass
            return PostResult(False, f"오류: {e}")


def save_site_profile(path: str, data: dict[str, Any]) -> None:
    import json
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing: dict = {}
    if p.exists():
        try:
            existing = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
    name = data.get("name") or urlparse(data.get("site_url", "")).netloc or "site"
    existing[name] = data
    p.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")


def load_site_profiles(path: str) -> dict[str, Any]:
    import json
    from pathlib import Path

    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
