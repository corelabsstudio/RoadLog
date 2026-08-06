# -*- coding: utf-8 -*-
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

UA = {"User-Agent": "RoadLogQA/wait", "Cache-Control": "no-cache"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def check():
    ok = True
    try:
        bj = json.loads(get("https://roadlog.co.kr/build.json?t=" + str(time.time())))
        rl_ok = bj.get("build") == "20260729-qa-fix"
        print("RL build.json", bj.get("build"), "OK" if rl_ok else "WAIT")
        ok = ok and rl_ok
        home = get("https://roadlog.co.kr/?t=" + str(time.time()))
        print("RL free-fab", "free-fab" in home and "무료" in home)
        print("RL meta", "20260729-qa-fix" in home)
    except Exception as e:
        print("RL err", e)
        ok = False
    try:
        wa = get("https://wakeagain.com/?t=" + str(time.time()))
        wa_ok = "20260729-yard-fix" in wa
        print("WA cache", "OK" if wa_ok else "WAIT", "yard-fix" if wa_ok else "old")
        ok = ok and wa_ok
    except Exception as e:
        print("WA err", e)
        ok = False
    return ok


for i in range(24):
    print(f"\n--- poll {i+1} ---")
    if check():
        print("BOTH LIVE")
        sys.exit(0)
    time.sleep(15)
print("TIMEOUT")
sys.exit(1)
