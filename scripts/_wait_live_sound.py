# -*- coding: utf-8 -*-
import sys
import time
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)


def get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "CoreLabsCheck/1.0",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, str(e)


def main() -> None:
    urls = [
        ("RL build", "https://roadlog.co.kr/build.json"),
        ("RL js", "https://roadlog.co.kr/ui-sound.js?v=20260722-sound-v1"),
        ("RL html", "https://roadlog.co.kr/?fresh=soundcheck"),
        ("WA js", "https://wakeagain.com/js/ui-sound.js?v=20260722a"),
        ("WA html", "https://wakeagain.com/"),
        ("WA2 js", "https://wakeagain-production.up.railway.app/js/ui-sound.js?v=20260722a"),
    ]
    for i in range(30):
        print(f"=== {i} {time.strftime('%H:%M:%S')}", flush=True)
        marks = {}
        for name, u in urls:
            code, b = get(u)
            if name == "RL build":
                good = "20260722-sound-v1" in b
                print(name, code, b.strip()[:80], "NEW" if good else "old", flush=True)
            elif "js" in name:
                good = ("CoreLabsSound" in b) or ("playTone" in b)
                print(
                    name,
                    code,
                    "MARKER" if good else "no",
                    len(b),
                    b[:40].replace("\n", " "),
                    flush=True,
                )
            else:
                good = "ui-sound.js" in b
                print(name, code, "script" if good else "no-script", len(b), flush=True)
            marks[name] = good
        # enough for success: RL new + WA script
        if marks.get("RL js") and marks.get("RL html") and (marks.get("WA js") or marks.get("WA2 js")) and marks.get("WA html"):
            print("ALL LIVE", flush=True)
            return
        time.sleep(15)
    print("TIMEOUT", flush=True)


if __name__ == "__main__":
    main()
