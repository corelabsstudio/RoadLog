"""Map smartstore product IDs to titles."""
from __future__ import annotations

import re
import urllib.request

IDS = [
    "13684008043",
    "13684008042",
    "13684008041",
    "13684008040",
    "13684008039",
    "13684008038",
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def main() -> None:
    for pid in IDS:
        url = f"https://smartstore.naver.com/thelucid/products/{pid}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            html = urllib.request.urlopen(req, timeout=20).read().decode(
                "utf-8", "replace"
            )
            og = re.search(
                r'property="og:title"\s+content="([^"]+)"', html
            ) or re.search(
                r'content="([^"]+)"\s+property="og:title"', html
            )
            title = re.search(r"<title>([^<]+)</title>", html)
            # price sometimes in JSON
            price = re.search(r'"price"\s*:\s*(\d+)', html)
            print(
                pid,
                "|",
                (og.group(1) if og else "-")[:90],
                "|",
                (title.group(1) if title else "-")[:50],
                "|",
                price.group(1) if price else "?",
            )
        except Exception as e:
            print(pid, "ERR", e)


if __name__ == "__main__":
    main()
