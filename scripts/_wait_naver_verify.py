# -*- coding: utf-8 -*-
"""Poll live roadlog.co.kr for Naver verification assets."""
from __future__ import annotations

import time
import urllib.request

TOKEN = "4afa1a34caaa5eee191597c59ff416d7d87f6727"
FILE_URL = "https://roadlog.co.kr/naverf5d0e35e417b10198c439271e3a8aba1.html"
HOME = "https://roadlog.co.kr/"


def get(url: str) -> tuple[int | None, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 RoadLogNaverCheck/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:
        return None, str(e)


def main() -> None:
    for i in range(30):
        st1, body1 = get(HOME)
        st2, body2 = get(FILE_URL)
        has_meta = bool(body1 and TOKEN in body1 and "naver-site-verification" in body1)
        has_file = bool(body2 and TOKEN in body2 and st2 == 200)
        snip = (body2 or "")[:100].replace("\n", " ")
        print(f"[{i}] home={st1} meta={has_meta} | file={st2} ok={has_file} | {snip!r}")
        if has_meta and has_file:
            print("LIVE_NAVER_OK")
            return
        time.sleep(12)
    print("TIMEOUT_WAITING_DEPLOY")
    raise SystemExit(1)


if __name__ == "__main__":
    main()
