#!/usr/bin/env python3
"""
커뮤니티 사이트 «글 쓰는 칸 찾기» (Playwright).

올릴 곳 주소를 열어 로그인·글쓰기·제목/본문 입력 칸 선택자를 수집하고
이후 자동화 성공률을 높이기 위해 프로필에 저장할 수 있게 합니다.

캡차·휴대폰 인증·2단계 인증은 수행하지 않습니다. (가입 시 사용자가 1회 처리)
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse

from poster import (
    BODY_SELECTORS,
    LOGIN_BTN_SELECTORS,
    PASS_SELECTORS,
    SUBMIT_SELECTORS,
    TITLE_SELECTORS,
    USER_SELECTORS,
    WRITE_LINK_TEXTS,
    _collect_board_links,
    _first_visible,
    _normalize_url,
    _try_login,
    guess_write_url_from_board,
    PostJob,
)

LogFn = Callable[[str], None]


def _noop(msg: str) -> None:
    print(msg)


@dataclass
class StructureScanResult:
    ok: bool
    message: str
    site_url: str = ""
    login_url: str = ""
    write_url: str = ""
    board_url: str = ""
    selectors: dict[str, str] = field(default_factory=dict)
    confidence: int = 0  # 0~100
    notes: list[str] = field(default_factory=list)
    boards_top: list[dict[str, Any]] = field(default_factory=list)
    final_url: str = ""

    def summary_text(self) -> str:
        lines = [
            f"신뢰도 {self.confidence}%  ·  {self.message}",
            f"사이트: {self.site_url or '-'}",
            f"로그인: {self.login_url or '(메인에서 탐색)'}",
            f"글쓰기 화면: {self.write_url or '(링크에서 찾는 중)'}",
        ]
        if self.board_url:
            lines.append(f"게시판: {self.board_url}")
        if self.selectors:
            lines.append("찾은 입력 칸:")
            for k, v in self.selectors.items():
                lines.append(f"  · {k}: {v}")
        if self.notes:
            lines.append("메모:")
            for n in self.notes:
                lines.append(f"  · {n}")
        if self.boards_top:
            lines.append("게시판 후보:")
            for b in self.boards_top[:5]:
                lines.append(f"  · [{b.get('score', 0)}] {b.get('name', '')}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "StructureScanResult":
        if not data:
            return cls(ok=False, message="")
        return cls(
            ok=bool(data.get("ok")),
            message=str(data.get("message") or ""),
            site_url=str(data.get("site_url") or ""),
            login_url=str(data.get("login_url") or ""),
            write_url=str(data.get("write_url") or ""),
            board_url=str(data.get("board_url") or ""),
            selectors=dict(data.get("selectors") or {}),
            confidence=int(data.get("confidence") or 0),
            notes=list(data.get("notes") or []),
            boards_top=list(data.get("boards_top") or []),
            final_url=str(data.get("final_url") or ""),
        )


def _css_for_element(page, locator) -> str:
    """가능한 한 안정적인 CSS 선택자 문자열 생성."""
    try:
        return locator.evaluate(
            """(el) => {
                if (!el) return '';
                if (el.id) {
                    const id = el.id;
                    if (!id.match(/^\\d/) && !id.includes(' ')) {
                        return '#' + CSS.escape(id);
                    }
                }
                const name = el.getAttribute('name');
                const tag = el.tagName.toLowerCase();
                if (name) {
                    return tag + '[name="' + name.replace(/"/g, '\\\\"') + '"]';
                }
                const ph = el.getAttribute('placeholder');
                if (ph) {
                    return tag + '[placeholder*="' + ph.slice(0, 24).replace(/"/g, '') + '"]';
                }
                const type = el.getAttribute('type');
                if (type === 'password') return 'input[type="password"]';
                if (type === 'email') return 'input[type="email"]';
                // class 일부
                if (el.classList && el.classList.length) {
                    const c = Array.from(el.classList).slice(0, 2).join('.');
                    if (c) return tag + '.' + c.replace(/\\s+/g, '.');
                }
                return tag;
            }"""
        ) or ""
    except Exception:
        return ""


def _first_working_selector(page, candidates: list[str], timeout: int = 800) -> str:
    for sel in candidates:
        try:
            loc = page.locator(sel).first
            if loc.count() == 0:
                continue
            if loc.is_visible(timeout=timeout):
                # 더 구체적 CSS 우선
                refined = _css_for_element(page, loc)
                return refined or sel
        except Exception:
            continue
    return ""


def _find_write_href(page) -> str:
    for text in WRITE_LINK_TEXTS:
        try:
            link = page.get_by_role("link", name=re.compile(text, re.I)).first
            if link.is_visible(timeout=600):
                href = link.get_attribute("href") or ""
                if href and not href.startswith("javascript"):
                    return page.evaluate("(h) => { try { return new URL(h, location.href).href; } catch(e){ return h; } }", href)
        except Exception:
            pass
        try:
            el = page.locator(f'a:has-text("{text}")').first
            if el.is_visible(timeout=400):
                href = el.get_attribute("href") or ""
                if href and not href.startswith("javascript"):
                    return page.evaluate("(h) => { try { return new URL(h, location.href).href; } catch(e){ return h; } }", href)
        except Exception:
            pass
    return ""


def scan_site_structure(
    *,
    site_url: str,
    login_url: str = "",
    username: str = "",
    password: str = "",
    headless: bool = False,
    log: LogFn | None = None,
    timeout_ms: int = 25_000,
) -> StructureScanResult:
    """
    사이트 구조를 스캔해 선택자·글쓰기 URL 등을 반환.
    로그인 정보가 있으면 로그인 후 글쓰기 폼까지 시도합니다.
    """
    log = log or _noop
    site_url = _normalize_url(site_url)
    login_url = _normalize_url(login_url)
    notes: list[str] = []
    selectors: dict[str, str] = {}
    conf = 0
    write_url = ""
    board_url = ""
    boards_top: list[dict[str, Any]] = []

    if not site_url:
        return StructureScanResult(False, "커뮤니티 사이트 주소를 입력하세요.")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return StructureScanResult(
            False,
            "playwright 가 없습니다. pip install playwright && playwright install chromium",
        )

    notes.append(
        "캡차·휴대폰 인증·2단계 인증은 가입 시 사용자가 1회 처리합니다. 리치킷은 이를 자동화하지 않습니다."
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless, slow_mo=50)
        context = browser.new_context(viewport={"width": 1280, "height": 900}, locale="ko-KR")
        page = context.new_page()
        page.set_default_timeout(timeout_ms)

        try:
            start = login_url or site_url
            log(f"[칸 찾기] 이동: {start}")
            page.goto(start, wait_until="domcontentloaded")
            page.wait_for_timeout(1200)

            # 로그인 링크
            try:
                login_link = page.locator(
                    'a:has-text("로그인"), a:has-text("Login"), a:has-text("Sign in")'
                ).first
                if login_link.is_visible(timeout=1200):
                    if not _first_visible(page, PASS_SELECTORS, timeout=400):
                        href = login_link.get_attribute("href") or ""
                        if href and not href.startswith("javascript"):
                            try:
                                full = page.evaluate(
                                    "(h) => new URL(h, location.href).href", href
                                )
                                if full and not login_url:
                                    login_url = full
                            except Exception:
                                pass
                        login_link.click()
                        page.wait_for_timeout(1000)
                        conf += 8
            except Exception:
                pass

            # 로그인 폼 선택자
            u_sel = _first_working_selector(page, USER_SELECTORS)
            p_sel = _first_working_selector(page, PASS_SELECTORS)
            b_sel = _first_working_selector(page, LOGIN_BTN_SELECTORS)
            if u_sel:
                selectors["username"] = u_sel
                conf += 15
                log(f"  아이디 칸: {u_sel}")
            else:
                notes.append("아이디 입력칸을 못 찾았습니다. 로그인 페이지 주소를 직접 넣어 보세요.")
            if p_sel:
                selectors["password"] = p_sel
                conf += 15
                log(f"  비밀번호 칸: {p_sel}")
            else:
                notes.append("비밀번호 칸을 못 찾았습니다.")
            if b_sel:
                selectors["login_button"] = b_sel
                conf += 8
                log(f"  로그인 버튼: {b_sel}")

            # 로그인 시도 (선택)
            if username and password and u_sel and p_sel:
                log("  로그인 정보로 칸 찾기용 로그인 시도…")
                job = PostJob(
                    site_url=site_url,
                    username=username,
                    password=password,
                    title=".",
                    body=".",
                    login_url=login_url or start,
                    selectors=selectors,
                )
                _try_login(page, job, log)
                conf += 10
                notes.append("로그인 후 화면에서 글쓰기·게시판을 이어서 탐색했습니다.")
            elif not username:
                notes.append("아이디/비번을 넣으면 로그인 후 글쓰기 화면까지 더 정확히 찾습니다.")

            # 게시판 후보
            try:
                found = _collect_board_links(page, site_url, log)
                if not found:
                    page.goto(site_url, wait_until="domcontentloaded")
                    page.wait_for_timeout(800)
                    found = _collect_board_links(page, site_url, log)
                found = sorted(found, key=lambda x: x.score, reverse=True)[:12]
                boards_top = [
                    {
                        "name": b.name,
                        "url": b.url,
                        "score": b.score,
                        "write_url": b.write_url,
                        "reason": b.reason,
                    }
                    for b in found
                ]
                if found:
                    conf += 10
                    board_url = found[0].url
                    if found[0].write_url:
                        write_url = found[0].write_url
                    log(f"  게시판 후보 {len(found)}개 (최고점: {found[0].name})")
            except Exception as e:
                notes.append(f"게시판 수집 일부 실패: {e}")

            # 글쓰기 링크/URL
            w_href = _find_write_href(page)
            if w_href:
                write_url = write_url or w_href
                selectors["write_link"] = f'a[href*="{urlparse(w_href).path.split("?")[0][-40:]}"]' if urlparse(w_href).path else ""
                conf += 12
                log(f"  글쓰기 링크: {w_href}")

            # 글쓰기 페이지로 이동 시도
            targets = []
            if write_url:
                targets.append(write_url)
            if board_url:
                g = guess_write_url_from_board(board_url)
                if g:
                    targets.append(g)
            targets.append(site_url.rstrip("/") + "/bbs/write.php")
            targets.append(site_url.rstrip("/") + "/write")

            form_found = False
            for u in targets:
                u = _normalize_url(u)
                if not u:
                    continue
                try:
                    log(f"  글쓰기 화면 탐색: {u}")
                    page.goto(u, wait_until="domcontentloaded", timeout=12_000)
                    page.wait_for_timeout(1000)
                    t_sel = _first_working_selector(page, TITLE_SELECTORS, timeout=1000)
                    bdy = _first_working_selector(page, BODY_SELECTORS, timeout=1000)
                    if t_sel or bdy:
                        write_url = u
                        if t_sel:
                            selectors["title"] = t_sel
                            conf += 15
                            log(f"  제목 칸: {t_sel}")
                        if bdy:
                            selectors["body"] = bdy
                            conf += 15
                            log(f"  본문 칸: {bdy}")
                        sub = _first_working_selector(page, SUBMIT_SELECTORS, timeout=600)
                        if sub:
                            selectors["submit"] = sub
                            conf += 5
                            log(f"  등록 버튼: {sub}")
                        form_found = True
                        break
                    # 글쓰기 버튼 클릭 재시도
                    from poster import _click_write_on_page

                    if _click_write_on_page(page, log):
                        t_sel = _first_working_selector(page, TITLE_SELECTORS, timeout=1000)
                        bdy = _first_working_selector(page, BODY_SELECTORS, timeout=1000)
                        if t_sel or bdy:
                            write_url = page.url
                            if t_sel:
                                selectors["title"] = t_sel
                                conf += 15
                            if bdy:
                                selectors["body"] = bdy
                                conf += 15
                            form_found = True
                            break
                except Exception:
                    continue

            if not form_found:
                notes.append(
                    "글쓰기 화면을 자동으로 못 찾았습니다. 글쓰기 화면 주소를 직접 넣고 다시 「글 쓰는 칸 찾기」를 하세요."
                )

            conf = min(100, conf)
            final = page.url
            page.wait_for_timeout(1500)
            browser.close()

            ok = conf >= 25 and bool(selectors)
            msg = (
                f"글 쓰는 칸 찾기 완료 (신뢰도 {conf}%)"
                if ok
                else f"부분 파악 (신뢰도 {conf}%) — 선택자/주소를 보완하세요"
            )
            return StructureScanResult(
                ok=ok or conf >= 15,
                message=msg,
                site_url=site_url,
                login_url=login_url,
                write_url=write_url,
                board_url=board_url,
                selectors={k: v for k, v in selectors.items() if v},
                confidence=conf,
                notes=notes,
                boards_top=boards_top,
                final_url=final,
            )
        except Exception as e:
            try:
                browser.close()
            except Exception:
                pass
            return StructureScanResult(False, f"칸 찾기 오류: {e}", site_url=site_url, notes=notes)
