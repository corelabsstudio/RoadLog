# -*- coding: utf-8 -*-
"""Publish a post to Tistory Open API (onhae126.tistory.com).

Auth: access_token in .launch/tistory.env (never commit).
Docs: https://tistory.github.io/document-tistory-apis/

Usage:
  python tools/tistory_publish/publish.py --ping
  python tools/tistory_publish/publish.py --file post.html --title "제목" --tags "a,b"
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_CANDIDATES = [
    ROOT / ".launch" / "tistory.env",
    Path(r"C:\Users\hysoo\Projects\WakeAgain\.launch\tistory.env"),
    Path(r"C:\Users\hysoo\Projects\RoadLog\.launch\tistory.env"),
]
LOG = Path(__file__).resolve().parent / "publish_log.jsonl"
API_BASE = "https://www.tistory.com/apis"


def load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in ENV_CANDIDATES:
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
        if out.get("TISTORY_ACCESS_TOKEN"):
            out["_env_path"] = str(p)
            break
    # process env overrides
    for k in ("TISTORY_ACCESS_TOKEN", "TISTORY_BLOG_NAME", "TISTORY_DEFAULT_VISIBILITY"):
        if os.environ.get(k):
            out[k] = os.environ[k].strip()
    return out


def api_get(path: str, params: dict) -> dict:
    q = urllib.parse.urlencode(params)
    url = f"{API_BASE}{path}?{q}"
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "CoreLabsTistory/1.0"})
    with urllib.request.urlopen(req, timeout=60) as res:
        raw = res.read().decode("utf-8", "replace")
    return json.loads(raw)


def api_post(path: str, fields: dict) -> dict:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "User-Agent": "CoreLabsTistory/1.0",
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as res:
            raw = res.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:800]
        raise SystemExit(f"Tistory HTTP {e.code}: {body}") from e
    return json.loads(raw)


def html_from_file(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    # If full HTML document, extract body / article
    m = re.search(r"<article[^>]*>(.*?)</article>", text, re.I | re.S)
    if m:
        return m.group(1).strip()
    m = re.search(r"<main[^>]*>(.*?)</main>", text, re.I | re.S)
    if m:
        inner = m.group(1)
        # strip nav chrome if present
        return re.sub(r"<header[\s\S]*?</header>", "", inner, count=1).strip()
    if "<html" in text.lower():
        m = re.search(r"<body[^>]*>(.*?)</body>", text, re.I | re.S)
        if m:
            return m.group(1).strip()
    return text


def content_hash(title: str, content: str) -> str:
    h = hashlib.sha256(f"{title}\n{content}".encode("utf-8")).hexdigest()
    return h[:16]


def already_published(h: str) -> bool:
    if not LOG.is_file():
        return False
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if row.get("hash") == h and row.get("ok"):
            return True
    return False


def log_row(row: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def ping(env: dict) -> int:
    token = env.get("TISTORY_ACCESS_TOKEN")
    blog = env.get("TISTORY_BLOG_NAME") or "onhae126"
    if not token:
        print("SKIP_NO_TOKEN — create .launch/tistory.env (see README.md)")
        return 0
    data = api_get(
        "/blog/info",
        {"access_token": token, "output": "json", "blogName": blog},
    )
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
    status = (((data.get("tistory") or {}).get("status")) or "")
    if str(status) not in ("200", "200.0"):
        print("PING_FAIL", status)
        return 1
    print("PING_OK blog=", blog)
    return 0


def publish(env: dict, title: str, content: str, tags: str, visibility: str) -> int:
    token = env.get("TISTORY_ACCESS_TOKEN")
    blog = env.get("TISTORY_BLOG_NAME") or "onhae126"
    if not token:
        print("SKIP_NO_TOKEN")
        return 0
    h = content_hash(title, content)
    if already_published(h):
        print("SKIP_DUPLICATE hash=", h)
        return 0
    fields = {
        "access_token": token,
        "output": "json",
        "blogName": blog,
        "title": title,
        "content": content,
        "visibility": visibility,
        "tag": tags,
        "acceptComment": "1",
    }
    data = api_post("/post/write", fields)
    t = data.get("tistory") or {}
    status = str(t.get("status") or "")
    post_id = t.get("postId") or t.get("postid")
    url = t.get("url") or ""
    ok = status in ("200", "200.0") and bool(post_id or url)
    row = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "status": status,
        "postId": post_id,
        "url": url,
        "title": title,
        "blog": blog,
        "hash": h,
        "raw_keys": list(t.keys()),
    }
    log_row(row)
    print(json.dumps(row, ensure_ascii=False, indent=2))
    if not ok:
        print("PUBLISH_FAIL", json.dumps(data, ensure_ascii=False)[:1200])
        return 1
    print("PUBLISH_OK", url or post_id)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Tistory publisher for onhae126")
    ap.add_argument("--ping", action="store_true", help="blog info only")
    ap.add_argument("--file", type=Path, help="HTML/MD file to publish")
    ap.add_argument("--title", default="", help="post title")
    ap.add_argument("--tags", default="", help="comma-separated tags")
    ap.add_argument("--visibility", default="", help="0 draft / 1 protected / 3 public")
    args = ap.parse_args()

    env = load_env()
    if args.ping:
        return ping(env)

    title = (args.title or "").strip()
    if args.file:
        if not args.file.is_file():
            print("file not found", args.file)
            return 1
        content = html_from_file(args.file)
        if not title:
            # try <title> or first h1
            raw = args.file.read_text(encoding="utf-8")
            m = re.search(r"<h1[^>]*>(.*?)</h1>", raw, re.I | re.S)
            if m:
                title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
            if not title:
                m = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
                if m:
                    title = re.sub(r"<[^>]+>", "", m.group(1)).split("|")[0].strip()
    else:
        content = sys.stdin.read()
    if not title or not content.strip():
        print("need --title and content (--file or stdin)")
        return 1

    vis = (args.visibility or env.get("TISTORY_DEFAULT_VISIBILITY") or "3").strip()
    return publish(env, title, content, args.tags.strip(), vis)


if __name__ == "__main__":
    raise SystemExit(main())
