"""ROADLOG blog adapter backed by the existing persistent marketing database."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path

from modules.marketing_core.repository import MarketingRepository


class BlogPublisher:
    def __init__(self, repository: MarketingRepository, web_root: Path, origin: str):
        self.repository = repository
        self.web_root = Path(web_root)
        self.origin = origin.rstrip("/")

    def publish(self, approval_id: int) -> dict:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            article_template = (self.web_root / "blog" / "first-time-saju.html").read_text(encoding="utf-8")
            index_template = (self.web_root / "blog" / "index.html").read_text(encoding="utf-8")
            if "<main>" not in article_template or '<ul class="sj-cards">' not in index_template:
                raise RuntimeError("게시물 화면 템플릿을 확인하지 못했습니다.")
            result = self.repository.publish_blog(approval_id,stamp,self.origin)
            return result
        except ValueError:
            raise
        except Exception:
            self.repository.fail_blog_publish(approval_id,"게시물 저장 또는 검증 실패")
            raise

    def render(self, slug: str) -> str | None:
        if not re.fullmatch(r"ai-[1-9][0-9]*",slug): return None
        post = self.repository.blog_post(slug)
        if not post: return None
        template = (self.web_root / "blog" / "first-time-saju.html").read_text(encoding="utf-8")
        title = html.escape(post["title"])
        hook = html.escape(post["hook"])
        body = "".join(f'<p class="bl-p">{html.escape(block).replace(chr(10),"<br>")}</p>' for block in post["body"].split("\n\n") if block.strip())
        cta = html.escape(post["cta"])
        url = html.escape(self.origin + "/blog/" + slug + ".html",quote=True)
        tracking_url = html.escape(post["tracking_url"],quote=True)
        main = f'<main><p class="sj-kicker">로드로그 이야기</p><h1 class="sj-q">{title}</h1><p class="sj-line">{hook}</p>{body}<p class="bl-p"><a href="{tracking_url}">{cta}</a></p><a class="back" href="/blog/">다른 글 보기</a></main>'
        template = re.sub(r"<main>.*?</main>",lambda _:main,template,count=1,flags=re.S)
        template = re.sub(r"<title>.*?</title>",lambda _:f"<title>{title} | 로드로그</title>",template,count=1,flags=re.S)
        template = re.sub(r'<meta name="description" content="[^"]*"',lambda _:f'<meta name="description" content="{html.escape(post["hook"],quote=True)}"',template,count=1)
        template = re.sub(r'<link rel="canonical" href="[^"]*"',lambda _:f'<link rel="canonical" href="{url}"',template,count=1)
        template = re.sub(r'<meta property="og:url" content="[^"]*"',lambda _:f'<meta property="og:url" content="{url}"',template,count=1)
        template = re.sub(r'<meta property="og:title" content="[^"]*"',lambda _:f'<meta property="og:title" content="{title} | 로드로그"',template,count=1)
        template = re.sub(r'<meta property="og:description" content="[^"]*"',lambda _:f'<meta property="og:description" content="{html.escape(post["hook"],quote=True)}"',template,count=1)
        return template

    def render_index(self) -> str:
        template = (self.web_root / "blog" / "index.html").read_text(encoding="utf-8")
        posts = self.repository.blog_posts()
        cards = "".join(f'<li><a href="/blog/{html.escape(p["slug"],quote=True)}.html"><b>{html.escape(p["title"])}</b><span>{html.escape(p["hook"])}</span></a></li>' for p in posts)
        return template.replace('<ul class="sj-cards">','<ul class="sj-cards">'+cards,1)
