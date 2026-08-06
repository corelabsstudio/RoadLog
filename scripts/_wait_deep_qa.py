# -*- coding: utf-8 -*-
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "wait", "Cache-Control": "no-cache"}


def get(url):
    req = urllib.request.Request(url + ("&" if "?" in url else "?") + "t=" + str(time.time()), headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def check():
    bj = json.loads(get("https://roadlog.co.kr/build.json"))
    rl = bj.get("build") == "20260729-deep-qa"
    home = get("https://roadlog.co.kr/")
    css = get("https://roadlog.co.kr/styles.css?v=20260729-deep-qa")
    wa = get("https://wakeagain.com/")
    print(
        "RL",
        bj.get("build"),
        "cyan5e",
        css.count("#5eead4"),
        "purp",
        css.count("167, 139, 250"),
        "meta",
        "20260729-deep-qa" in home,
    )
    print("WA", "deep-qa" in wa, re_v(wa))
    return rl and "20260729-deep-qa" in home and "20260729-deep-qa" in wa and css.count("#5eead4") == 0


def re_v(html):
    import re

    m = re.search(r"styles\.css\?v=([^\"']+)", html)
    return m.group(1) if m else "?"


for i in range(30):
    print(f"--- {i+1} ---")
    try:
        if check():
            print("LIVE OK")
            sys.exit(0)
    except Exception as e:
        print("err", e)
    time.sleep(12)
print("timeout")
sys.exit(1)
