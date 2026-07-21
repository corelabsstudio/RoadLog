#!/usr/bin/env python3
"""
홍보 대상 웹사이트 분석 (API·결제 없음)

표준 라이브러리만 사용: 페이지를 받아 title / meta / h1 등을 추출하고
카테고리를 휴리스틱으로 추정합니다.
"""

from __future__ import annotations

import html as html_lib
import re
import ssl
from dataclasses import asdict, dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


@dataclass
class SiteProfile:
    url: str = ""
    final_url: str = ""
    title: str = ""
    brand: str = ""
    description: str = ""
    keywords: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    highlights: list[str] = field(default_factory=list)
    category: str = "일반"  # SaaS·쇼핑몰·콘텐츠·교육·로컬 등
    category_hint: str = ""
    ok: bool = False
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SiteProfile":
        if not data:
            return cls()
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        kw = {k: v for k, v in data.items() if k in known}
        for list_key in ("keywords", "headings", "highlights"):
            if list_key in kw and not isinstance(kw[list_key], list):
                kw[list_key] = []
        return cls(**kw)

    def summary_text(self) -> str:
        if not self.ok:
            return self.message or "분석 결과가 없습니다."
        lines = [
            f"브랜드: {self.brand or '-'}",
            f"제목: {self.title or '-'}",
            f"카테고리: {self.category}"
            + (f" ({self.category_hint})" if self.category_hint else ""),
            f"주소: {self.final_url or self.url}",
        ]
        if self.description:
            desc = self.description[:220] + ("…" if len(self.description) > 220 else "")
            lines.append(f"소개: {desc}")
        if self.highlights:
            lines.append("핵심: " + " · ".join(self.highlights[:5]))
        if self.keywords:
            lines.append("키워드: " + ", ".join(self.keywords[:8]))
        return "\n".join(lines)


def _normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def _decode_html(raw: bytes, content_type: str = "") -> str:
    charset = "utf-8"
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    if m:
        charset = m.group(1).strip().strip("\"'")
    # HTML meta charset
    head = raw[:4000].decode(charset, errors="ignore")
    m2 = re.search(r'charset=["\']?([\w\-]+)', head, re.I)
    if m2:
        charset = m2.group(1)
    try:
        return raw.decode(charset, errors="replace")
    except Exception:
        return raw.decode("utf-8", errors="replace")


def _strip_tags(s: str) -> str:
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_lib.unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _meta_content(html: str, *names: str) -> str:
    for name in names:
        # name= / property=
        patterns = [
            rf'<meta[^>]+(?:name|property)=["\']{re.escape(name)}["\'][^>]+content=["\']([^"\']+)["\']',
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:name|property)=["\']{re.escape(name)}["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.I)
            if m:
                return html_lib.unescape(m.group(1)).strip()
    return ""


def _all_meta_keywords(html: str) -> list[str]:
    raw = _meta_content(html, "keywords", "news_keywords")
    if not raw:
        return []
    parts = re.split(r"[,;/|·•]\s*", raw)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) < 40][:12]


def _find_title(html: str) -> str:
    og = _meta_content(html, "og:title", "twitter:title")
    if og:
        return og[:120]
    m = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.I)
    if m:
        return _strip_tags(m.group(1))[:120]
    return ""


def _find_description(html: str) -> str:
    for key in (
        "og:description",
        "twitter:description",
        "description",
        "Description",
    ):
        d = _meta_content(html, key)
        if d and len(d) > 10:
            return d[:500]
    return ""


def _find_headings(html: str, limit: int = 8) -> list[str]:
    found: list[str] = []
    for tag in ("h1", "h2", "h3"):
        for m in re.finditer(rf"<{tag}[^>]*>([\s\S]*?)</{tag}>", html, re.I):
            t = _strip_tags(m.group(1))
            if 2 <= len(t) <= 80 and t not in found:
                found.append(t)
            if len(found) >= limit:
                return found
    return found


def _guess_brand(title: str, url: str, headings: list[str]) -> str:
    # "Brand - tagline" / "Brand | …"
    if title:
        for sep in (" | ", " - ", " – ", " — ", " · ", " : "):
            if sep in title:
                left = title.split(sep, 1)[0].strip()
                if 1 < len(left) <= 40:
                    return left
        if len(title) <= 40:
            return title
    if headings:
        h = headings[0]
        if len(h) <= 40:
            return h
    host = urlparse(url).netloc.replace("www.", "")
    return host.split(".")[0] if host else "이 서비스"


def _infer_category(blob: str) -> tuple[str, str]:
    t = (blob or "").lower()
    rules: list[tuple[str, str, list[str]]] = [
        (
            "온라인 서비스·앱",
            "소프트웨어·웹앱·구독 서비스로 보입니다",
            [
                "saas",
                "software",
                "api",
                "dashboard",
                "구독",
                "무료 체험",
                "free trial",
                "login",
                "sign up",
                "ai ",
                "인공지능",
                "자동화",
                "플랫폼",
            ],
        ),
        (
            "쇼핑몰",
            "상품·구매·배송 키워드가 많습니다",
            ["shop", "store", "cart", "구매", "배송", "할인", "장바구니", "order", "상품", "price"],
        ),
        (
            "교육·강의",
            "강의·코스·학습 관련으로 보입니다",
            ["강의", "코스", "course", "학습", "교육", "클래스", "tutor", "academy", "수강"],
        ),
        (
            "콘텐츠·미디어",
            "블로그·뉴스·콘텐츠 성격",
            ["blog", "news", "기사", "매거진", "스토리", "구독하기", "newsletter"],
        ),
        (
            "로컬·예약",
            "매장·예약·방문 키워드",
            ["예약", "매장", "방문", "restaurant", "카페", "병원", "클리닉", "booking"],
        ),
        (
            "포트폴리오·에이전시",
            "스튜디오·에이전시·포트폴리오",
            ["portfolio", "agency", "studio", "클라이언트", "프로젝트", "문의하기"],
        ),
    ]
    best = ("일반", "특정 업종 키워드가 적어 일반 소개형으로 작성합니다")
    best_hits = 0
    for name, hint, kws in rules:
        hits = sum(1 for k in kws if k in t)
        if hits > best_hits:
            best_hits = hits
            best = (name, hint)
    return best


def _highlights_from(
    description: str, headings: list[str], keywords: list[str]
) -> list[str]:
    out: list[str] = []
    for h in headings[:5]:
        if h not in out:
            out.append(h)
    # description sentences
    if description:
        for part in re.split(r"[.。!?!\n]", description):
            p = part.strip()
            if 12 <= len(p) <= 100 and p not in out:
                out.append(p)
            if len(out) >= 6:
                break
    for k in keywords[:4]:
        if k not in out:
            out.append(k)
    return out[:7]


def fetch_html(url: str, timeout: float = 12.0) -> tuple[str, str, str]:
    """
    Returns (html, final_url, error_message).
    error_message empty on success.
    """
    url = _normalize_url(url)
    if not url:
        return "", "", "주소가 비어 있습니다."
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36 CommunityPoster/1.0"
            ),
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.5",
        },
        method="GET",
    )
    ctx = ssl.create_default_context()
    try:
        with urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(1_500_000)  # max ~1.5MB
            ctype = resp.headers.get("Content-Type", "")
            final = resp.geturl() or url
            return _decode_html(raw, ctype), final, ""
    except HTTPError as e:
        return "", url, f"HTTP 오류 {e.code}: {e.reason}"
    except URLError as e:
        return "", url, f"접속 실패: {e.reason}"
    except Exception as e:
        return "", url, f"분석 실패: {e}"


def analyze_site(url: str, timeout: float = 12.0) -> SiteProfile:
    """홍보 대상 사이트를 가져와 프로필로 정리."""
    url = _normalize_url(url)
    profile = SiteProfile(url=url)
    if not url:
        profile.message = "분석할 사이트 주소를 입력하세요."
        return profile

    html, final_url, err = fetch_html(url, timeout=timeout)
    if err or not html:
        profile.message = err or "HTML을 가져오지 못했습니다."
        # 오프라인 폴백: URL만으로 최소 프로필
        host = urlparse(url).netloc.replace("www.", "")
        profile.final_url = url
        profile.brand = host.split(".")[0] if host else "내 사이트"
        profile.title = host or url
        profile.description = f"{profile.brand} 웹사이트 ({url})"
        profile.category = "일반"
        profile.category_hint = "페이지를 읽지 못해 주소 기준 최소 정보만 사용합니다"
        profile.highlights = [profile.brand, url]
        profile.ok = True  # 문구 생성은 가능하게
        profile.message = (err or "페이지 로드 실패") + " · 주소 기준 최소 분석으로 진행 가능"
        return profile

    title = _find_title(html)
    desc = _find_description(html)
    headings = _find_headings(html)
    keywords = _all_meta_keywords(html)
    brand = _guess_brand(title, final_url, headings)
    blob = " ".join([title, desc, " ".join(headings), " ".join(keywords), final_url])
    category, cat_hint = _infer_category(blob)
    highlights = _highlights_from(desc, headings, keywords)

    # site name from og:site_name
    site_name = _meta_content(html, "og:site_name")
    if site_name and len(site_name) <= 40:
        brand = site_name

    profile.final_url = final_url
    profile.title = title or brand
    profile.brand = brand
    profile.description = desc
    profile.keywords = keywords
    profile.headings = headings
    profile.highlights = highlights
    profile.category = category
    profile.category_hint = cat_hint
    profile.ok = True
    profile.message = f"분석 완료 · {brand} ({category})"
    return profile


def analyze_site_dict(url: str) -> dict[str, Any]:
    return analyze_site(url).to_dict()


if __name__ == "__main__":
    import sys

    u = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    p = analyze_site(u)
    print(p.message)
    print(p.summary_text())
