# -*- coding: utf-8 -*-
"""RoadLog news digest builder (3-step format).

1) Wallet-targeted items only (tax / fine / regulation / cost recognition)
2) 3~4 line summary + source link (no full-text reprint)
3) RoadLog solution pitch

Reads:  docs/marketing/news_digest/items.json
Writes: web/blog/news/<slug>.html
        web/blog/news/index.html
        updates web/blog/index.html news block (between markers)
        merges URLs into web/sitemap.xml

Usage:
  python scripts/make_news_digest.py
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ITEMS = ROOT / "docs" / "marketing" / "news_digest" / "items.json"
BLOG = ROOT / "web" / "blog"
NEWS = BLOG / "news"
SITEMAP = ROOT / "web" / "sitemap.xml"
SITE = "https://roadlog.co.kr"

MARK_START = "<!-- NEWS_DIGEST_START -->"
MARK_END = "<!-- NEWS_DIGEST_END -->"


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def shell(title: str, desc: str, canonical: str, body: str, json_ld: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(desc)}" />
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href="{esc(canonical)}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{esc(canonical)}" />
  <meta property="og:title" content="{esc(title)}" />
  <meta property="og:description" content="{esc(desc)}" />
  <meta property="og:image" content="{SITE}/icons/og-image.jpg" />
  <meta name="theme-color" content="#030712" />
  <link rel="icon" type="image/svg+xml" href="/icons/logo.svg" />
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/sun-typeface/SUIT@2/fonts/variable/woff2/SUIT-Variable.css" />
  <link rel="stylesheet" href="/styles.css?v=20260727-news" />
  <link rel="stylesheet" href="/blog/blog.css?v=20260727-news" />
  {json_ld}
</head>
<body class="blog-page">
  <header class="blog-nav">
    <div class="blog-nav-inner">
      <a class="blog-brand" href="/">
        <img src="/icons/logo.svg" width="32" height="32" alt="RoadLog" />
        <span>로드로그<small>AI 운행·외근 일지</small></span>
      </a>
      <nav class="blog-nav-links">
        <a href="/blog/">가이드</a>
        <a href="/blog/news/">뉴스 브리핑</a>
        <a href="/#create">무료 시작</a>
      </nav>
    </div>
  </header>
  <main class="blog-wrap">
{body}
  </main>
</body>
</html>
"""


def render_item(item: dict) -> str:
    slug = item["slug"]
    title = item["title"]
    date_s = item["date"]
    tags = item.get("tags") or []
    wallet = item.get("wallet") or "규제·비용"
    source_name = item["source_name"]
    source_url = item["source_url"]
    summary = item["summary"]
    pitch = item["pitch"]
    canonical = f"{SITE}/blog/news/{slug}"
    desc = summary[0][:110] if summary else title

    bullets = "\n".join(f"        <li>{esc(line)}</li>" for line in summary[:4])
    tag_html = " ".join(f'<span class="tag">{esc(t)}</span>' for t in tags[:4])

    json_ld = f"""
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "NewsArticle",
    "headline": {json.dumps(title, ensure_ascii=False)},
    "datePublished": "{date_s}",
    "dateModified": "{date_s}",
    "author": {{"@type": "Organization", "name": "CoreLabs"}},
    "mainEntityOfPage": "{canonical}",
    "description": {json.dumps(desc, ensure_ascii=False)}
  }}
  </script>"""

    body = f"""
    <article>
      <div class="blog-kicker">뉴스 브리핑 · {esc(wallet)}</div>
      <div class="news-tags">{tag_html}</div>
      <h1 style="font-family:var(--font-display);font-size:clamp(1.45rem,3.4vw,2rem);line-height:1.3;margin:10px 0 8px">{esc(title)}</h1>
      <p class="blog-meta">{esc(date_s)} · 원문 전재 없음 · 3~4줄 요약 + 로드로그 코멘트</p>

      <div class="article-body">
        <h2>핵심 요약</h2>
        <ul class="news-summary">
{bullets}
        </ul>

        <div class="source-box">
          <strong>자세한 내용은 원문 참조</strong><br />
          출처: <a href="{esc(source_url)}" rel="noopener noreferrer" target="_blank">{esc(source_name)}</a>
          <div style="margin-top:6px;word-break:break-all;font-size:0.85rem">
            <a href="{esc(source_url)}" rel="noopener noreferrer" target="_blank">{esc(source_url)}</a>
          </div>
        </div>

        <div class="cta-box pitch-box">
          <h3>로드로그 코멘트 · 해결책</h3>
          <p>{esc(pitch)}</p>
          <div class="btn-row">
            <a class="btn btn-primary" href="/">로드로그에서 기록 시작</a>
            <a class="btn btn-ghost" href="/blog/news/">다른 브리핑 보기</a>
          </div>
        </div>

        <p class="disclaimer">
          면책: 본 페이지는 공개 기사·안내를 바탕으로 한 짧은 요약이며 세무·법률 자문이 아닙니다.
          기사 전문을 복제하지 않습니다. 비용 인정·의무·벌칙 여부는 개별 사안과 최신 규정에 따르며,
          절세·수익을 보장하지 않습니다. 의사결정은 세무 전문가와 하세요.
        </p>
      </div>
    </article>
    <footer class="blog-foot">
      <a href="/blog/news/">← 뉴스 브리핑 목록</a>
      <a href="/blog/">가이드 글</a>
    </footer>
"""
    return shell(f"{title} | 로드로그 뉴스 브리핑", desc, canonical, body, json_ld)


def render_news_index(items: list[dict]) -> str:
    cards = []
    for it in items:
        tags = ", ".join(it.get("tags") or [])
        lead = (it.get("summary") or [""])[0]
        cards.append(
            f"""
      <a class="blog-card" href="/blog/news/{esc(it['slug'])}">
        <span class="tag">{esc(it.get('wallet') or '뉴스')}</span>
        <h2>{esc(it['title'])}</h2>
        <p>{esc(lead)}</p>
        <div class="more">{esc(it['date'])} · {esc(tags)} →</div>
      </a>"""
        )
    body = f"""
    <header class="blog-hero">
      <div class="blog-kicker">RoadLog News Briefing</div>
      <h1>세금·규제·비용 — 지갑에 닿는 뉴스만</h1>
      <p class="lead">
        단순 자동차 뉴스가 아니라 <strong>세금·벌금·규제·비용 인정</strong>과 직결된 이슈만 고릅니다.
        전문은 퍼오지 않고 <strong>3~4줄 요약 + 원문 링크</strong> 후,
        <strong>로드로그로 어떻게 대비할지</strong>만 덧붙입니다.
      </p>
      <p class="blog-meta">업데이트 {esc(items[0]['date'] if items else str(date.today()))} · 매일 관련 이슈 추가</p>
    </header>
    <section class="blog-grid" aria-label="뉴스 브리핑 목록">
      {''.join(cards)}
    </section>
    <div class="cta-box" style="margin-top:28px">
      <h3>기록 누락이 비용 리스크가 되기 전에</h3>
      <p>현장 스탬프 → 제출용 Excel·PDF·DOCX. 카드 없이 Free 10회.</p>
      <div class="btn-row">
        <a class="btn btn-primary" href="/">로드로그 시작</a>
        <a class="btn btn-ghost" href="/blog/">실무 가이드</a>
      </div>
    </div>
    <footer class="blog-foot">
      <span>© CoreLabs · RoadLog</span>
      <a href="/blog/">가이드로</a>
    </footer>
"""
    return shell(
        "로드로그 뉴스 브리핑 · 법인차·운행일지·세무 이슈",
        "세금·규제·비용 인정과 연결된 뉴스만 3~4줄 요약하고 로드로그 해결책을 제시합니다.",
        f"{SITE}/blog/news/",
        body,
    )


def patch_blog_home(items: list[dict]) -> None:
    path = BLOG / "index.html"
    html = path.read_text(encoding="utf-8")
    cards = []
    for it in items[:6]:
        cards.append(
            f"""      <a class="blog-card" href="/blog/news/{esc(it['slug'])}">
        <span class="tag">뉴스 · {esc(it.get('wallet') or '')}</span>
        <h2>{esc(it['title'])}</h2>
        <p>{esc((it.get('summary') or [''])[0])}</p>
        <div class="more">{esc(it['date'])} · 브리핑 읽기 →</div>
      </a>"""
        )
    block = f"""{MARK_START}
    <section style="margin-top:40px" aria-label="뉴스 브리핑">
      <div class="blog-kicker">Daily / Wallet news</div>
      <h2 style="font-family:var(--font-display);font-size:1.35rem;margin:8px 0 6px">지갑에 닿는 뉴스 브리핑</h2>
      <p class="lead" style="margin-bottom:16px">세금·규제·비용 이슈만 요약하고 로드로그 해결책을 붙입니다. <a href="/blog/news/" style="color:var(--cyan)">전체 보기</a></p>
      <div class="blog-grid">
{chr(10).join(cards)}
      </div>
    </section>
{MARK_END}"""
    if MARK_START in html and MARK_END in html:
        html = re.sub(
            re.escape(MARK_START) + r".*?" + re.escape(MARK_END),
            block,
            html,
            count=1,
            flags=re.S,
        )
    else:
        # insert before first cta-box or before footer
        if '<div class="cta-box"' in html:
            html = html.replace('<div class="cta-box"', block + '\n    <div class="cta-box"', 1)
        else:
            html = html.replace('<footer class="blog-foot">', block + '\n    <footer class="blog-foot">', 1)
    # ensure nav has news link
    if 'href="/blog/news/"' not in html:
        html = html.replace(
            '<a href="/blog/">가이드</a>',
            '<a href="/blog/">가이드</a>\n        <a href="/blog/news/">뉴스</a>',
            1,
        )
    path.write_text(html, encoding="utf-8")


def patch_sitemap(items: list[dict]) -> None:
    # rebuild blog news urls into sitemap simply by text merge
    text = SITEMAP.read_text(encoding="utf-8")
    urls = [
        f"{SITE}/blog/news/",
        *[f"{SITE}/blog/news/{it['slug']}" for it in items],
    ]
    for u in urls:
        if u in text:
            continue
        entry = f"""  <url>
    <loc>{u}</loc>
    <lastmod>{date.today().isoformat()}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
"""
        text = text.replace("</urlset>", entry + "</urlset>")
    SITEMAP.write_text(text, encoding="utf-8")


def patch_css() -> None:
    css_path = BLOG / "blog.css"
    extra = """
.news-summary { margin: 0 0 1.2em 1.1em; }
.news-summary li { margin: 0.45em 0; color: #e2e8f0; }
.news-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 4px; }
.news-tags .tag { margin-bottom: 0; }
.pitch-box h3 { color: #a5f3fc; }
"""
    cur = css_path.read_text(encoding="utf-8")
    if ".news-summary" not in cur:
        css_path.write_text(cur.rstrip() + "\n" + extra, encoding="utf-8")


def main() -> None:
    data = json.loads(ITEMS.read_text(encoding="utf-8"))
    items: list[dict] = data["items"]
    # newest first
    items = sorted(items, key=lambda x: (x.get("date", ""), x.get("slug", "")), reverse=True)

    NEWS.mkdir(parents=True, exist_ok=True)
    for it in items:
        html = render_item(it)
        out = NEWS / f"{it['slug']}.html"
        out.write_text(html, encoding="utf-8")
        print("wrote", out.name)

    (NEWS / "index.html").write_text(render_news_index(items), encoding="utf-8")
    print("wrote news/index.html", len(items), "items")

    patch_blog_home(items)
    patch_sitemap(items)
    patch_css()
    print("OK digest", len(items))


if __name__ == "__main__":
    main()
