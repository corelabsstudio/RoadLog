# -*- coding: utf-8 -*-
"""Daily X auto: build pack (copy+image) and post via X API.

Requires: .launch/x.env with OAuth 1.0a user tokens.
Does NOT commit secrets. Safe to run from scheduler.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
PACKS = ROOT / "docs" / "marketing" / "x" / "packs"
CARD_SCRIPT = ROOT / "scripts" / "make_x_card.py"
ENV_PATHS = [
    ROOT / ".launch" / "x.env",
    ROOT / ".env",
]

try:
    from requests_oauthlib import OAuth1Session
except ImportError:
    OAuth1Session = None  # type: ignore


def kst_today() -> str:
    return datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d")


def load_env() -> dict[str, str]:
    out: dict[str, str] = {}
    for p in ENV_PATHS:
        if not p.is_file():
            continue
        for line in p.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
    # process env overrides
    for k in (
        "X_API_KEY",
        "X_API_SECRET",
        "X_ACCESS_TOKEN",
        "X_ACCESS_TOKEN_SECRET",
        "X_POST_ROADLOG",
        "X_POST_WAKEAGAIN_SOFT",
    ):
        if os.environ.get(k):
            out[k] = os.environ[k]
    return out


def require_keys(env: dict[str, str]) -> list[str]:
    need = [
        "X_API_KEY",
        "X_API_SECRET",
        "X_ACCESS_TOKEN",
        "X_ACCESS_TOKEN_SECRET",
    ]
    return [k for k in need if not env.get(k)]


def extract_caption(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    # first fenced block after "## Caption"
    m = re.search(
        r"## Caption[^\n]*\n+```(?:\w*)?\n(.*?)```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        raise SystemExit(f"No caption block in {md_path}")
    cap = m.group(1).strip()
    # X free often 280 chars; keep as-is if longer (Premium) else trim soft
    if len(cap) > 280:
        # try keep first paragraphs under 280
        parts = cap.split("\n\n")
        acc = ""
        for p in parts:
            cand = (acc + "\n\n" + p).strip() if acc else p
            if len(cand) <= 280:
                acc = cand
            else:
                break
        cap = acc or cap[:277] + "…"
    return cap


def ensure_default_pack(day: str) -> Path:
    pack = PACKS / day
    img_dir = pack / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    rl_md = pack / "ROADLOG.md"
    wa_md = pack / "WA_SOFT.md"
    rl_img = img_dir / "roadlog.png"
    wa_img = img_dir / "wakeagain_soft.png"

    # weekday persona light defaults if missing
    if not rl_md.is_file():
        rl_md.write_text(
            f"""# RoadLog X pack — {day}

PERSONA: P1 외근 실무
## Caption (게시용)
```
외근 끝내고 차 안에서 엑셀?

방문 직후 한 줄만 남겨도
제출용으로 정리됩니다.

RoadLog · Free
https://roadlog.co.kr
```
REVIEW: PASS
""",
            encoding="utf-8",
        )
    if not wa_md.is_file():
        wa_md.write_text(
            f"""# WakeAgain SOFT — {day}

MODE: soft
## Caption
```
폴더에만 있는 MVP
지우기 전에 한 번만 올려볼래?

등록 무료 · 오픈 초기
피드백이 제일 필요해요.

https://wakeagain.com
```
REVIEW: PASS
""",
            encoding="utf-8",
        )

    import subprocess

    py = sys.executable
    if not rl_img.is_file():
        subprocess.check_call(
            [
                py,
                str(CARD_SCRIPT),
                "--out",
                str(rl_img),
                "--theme",
                "roadlog",
                "--brand",
                "RoadLog",
                "--headline",
                "외근 끝내고\n차 안에서 엑셀?",
                "--sub",
                "방문 직후 한 줄만 남겨도\n제출용으로 정리됩니다",
                "--footer",
                "roadlog.co.kr · Free",
            ]
        )
    if not wa_img.is_file():
        subprocess.check_call(
            [
                py,
                str(CARD_SCRIPT),
                "--out",
                str(wa_img),
                "--theme",
                "wakeagain",
                "--brand",
                "WakeAgain",
                "--headline",
                "폴더에만 있는 MVP\n지우기 전에",
                "--sub",
                "등록은 무료 · 오픈 초기\n피드백이 제일 필요해요",
                "--footer",
                "wakeagain.com",
            ]
        )
    return pack


def oauth_session(env: dict[str, str]) -> "OAuth1Session":
    if OAuth1Session is None:
        raise SystemExit(
            "requests-oauthlib 필요: pip install requests requests-oauthlib"
        )
    return OAuth1Session(
        env["X_API_KEY"],
        client_secret=env["X_API_SECRET"],
        resource_owner_key=env["X_ACCESS_TOKEN"],
        resource_owner_secret=env["X_ACCESS_TOKEN_SECRET"],
    )


def upload_media(sess: "OAuth1Session", path: Path) -> str:
    url = "https://upload.twitter.com/1.1/media/upload.json"
    with path.open("rb") as f:
        r = sess.post(url, files={"media": f})
    if r.status_code >= 300:
        raise SystemExit(f"media upload failed {r.status_code}: {r.text[:500]}")
    mid = r.json().get("media_id_string") or str(r.json().get("media_id"))
    if not mid:
        raise SystemExit(f"no media_id: {r.text[:500]}")
    return mid


def post_tweet(sess: "OAuth1Session", text: str, media_id: str | None) -> dict:
    url = "https://api.twitter.com/2/tweets"
    payload: dict = {"text": text}
    if media_id:
        payload["media"] = {"media_ids": [media_id]}
    r = sess.post(url, json=payload)
    if r.status_code >= 300:
        raise SystemExit(f"tweet failed {r.status_code}: {r.text[:800]}")
    return r.json()


def update_meta(pack: Path, results: dict) -> None:
    meta_path = pack / "META.json"
    meta = {}
    if meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.setdefault("date", pack.name)
    meta["status"] = "posted" if results.get("ok") else "error"
    meta["auto_post"] = results
    meta.setdefault("posted", {})
    if results.get("roadlog", {}).get("id"):
        meta["posted"]["roadlog"] = True
    if results.get("wakeagain", {}).get("id"):
        meta["posted"]["wakeagain"] = True
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--roadlog-only", action="store_true")
    ap.add_argument("--wa-only", action="store_true")
    args = ap.parse_args()

    day = args.date or kst_today()
    pack = ensure_default_pack(day)
    env = load_env()
    missing = require_keys(env)
    if missing and not args.dry_run:
        print("MISSING_KEYS", ",".join(missing))
        print(
            "Setup: copy .launch/x.env.example → .launch/x.env and fill keys.\n"
            "Guide: docs/marketing/x/AUTO_POST_SETUP.md"
        )
        return 2

    post_rl = env.get("X_POST_ROADLOG", "1") != "0" and not args.wa_only
    post_wa = env.get("X_POST_WAKEAGAIN_SOFT", "1") != "0" and not args.roadlog_only

    jobs = []
    if post_rl:
        jobs.append(
            (
                "roadlog",
                pack / "ROADLOG.md",
                pack / "images" / "roadlog.png",
            )
        )
    if post_wa:
        jobs.append(
            (
                "wakeagain",
                pack / "WA_SOFT.md",
                pack / "images" / "wakeagain_soft.png",
            )
        )

    results: dict = {"ok": True, "date": day}
    if args.dry_run:
        for name, md, img in jobs:
            cap = extract_caption(md)
            print("DRY", name, "chars", len(cap), "img", img.is_file())
            print(cap[:200])
            results[name] = {"dry": True, "chars": len(cap)}
        update_meta(pack, results)
        print("DRY_OK", pack)
        return 0

    sess = oauth_session(env)
    for name, md, img in jobs:
        try:
            cap = extract_caption(md)
            mid = upload_media(sess, img) if img.is_file() else None
            data = post_tweet(sess, cap, mid)
            tid = ((data.get("data") or {}).get("id")) or ""
            results[name] = {"id": tid, "media": mid}
            print("POSTED", name, tid)
        except SystemExit as e:
            results["ok"] = False
            results[name] = {"error": str(e)}
            print("FAIL", name, e)
            break
        except Exception as e:
            results["ok"] = False
            results[name] = {"error": repr(e)}
            print("FAIL", name, repr(e))
            break

    update_meta(pack, results)
    print("DONE", json.dumps(results, ensure_ascii=False))
    return 0 if results.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
