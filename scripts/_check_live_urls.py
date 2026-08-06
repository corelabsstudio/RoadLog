# -*- coding: utf-8 -*-
import re
import urllib.request
from pathlib import Path

sys_out = print


def get(url: str):
    req = urllib.request.Request(
        url, headers={"User-Agent": "x", "Cache-Control": "no-cache"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, r.headers.get("content-type"), r.read()


for u in [
    "https://roadlog.co.kr/build.json",
    "https://roadlog.co.kr/ui-sound.js",
    "https://roadlog.co.kr/?t=1",
]:
    try:
        code, ct, b = get(u)
        print(u, code, ct, b[:150])
    except Exception as e:
        print(u, "ERR", e)

candidates = [
    "https://wakeagain.com/",
    "https://www.wakeagain.com/",
    "https://wakeagain-production.up.railway.app/",
    "https://web-production-8ee81.up.railway.app/health",
    "https://web-production-8ee81.up.railway.app/",
]
for u in candidates:
    try:
        code, ct, b = get(u)
        text = b.decode("utf-8", errors="replace")
        t = re.search(r"<title>([^<]+)", text)
        print(u, code, len(b), t.group(1) if t else text[:80].replace("\n", " "))
    except Exception as e:
        print(u, type(e).__name__, e)

for p in [
    Path(r"C:\Users\hysoo\Projects\WakeAgain\README.md"),
    Path(r"C:\Users\hysoo\Projects\WakeAgain\PLATFORM.md"),
    Path(r"C:\Users\hysoo\Projects\WakeAgain\PROGRESS.md"),
]:
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8", errors="replace")
    for m in re.findall(r"https?://[^\s)\"']+", t):
        if "railway" in m or "wake" in m.lower():
            print(p.name, m)
