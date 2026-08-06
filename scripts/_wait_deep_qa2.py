# -*- coding: utf-8 -*-
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
UA = {"User-Agent": "wait", "Cache-Control": "no-cache"}


def get(url):
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(url + sep + "t=" + str(time.time()), headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


for i in range(30):
    print("---", i + 1)
    try:
        bj = json.loads(get("https://roadlog.co.kr/build.json"))
        home = get("https://roadlog.co.kr/")
        css = get("https://roadlog.co.kr/styles.css?v=x")
        app = get("https://wakeagain.com/app/")
        ok = (
            bj.get("build") == "20260729-deep-qa2"
            and "20260729-deep-qa2" in home
            and "body:has(.view.active:not(#view-home)) .free-fab" in css
            and "deep-qa2" in app
            and "app-body" in app
        )
        print("RL", bj.get("build"), "fab-rule", "body:has(.view.active" in css, "WA app", "deep-qa2" in app)
        if ok:
            print("LIVE")
            sys.exit(0)
    except Exception as e:
        print("err", e)
    time.sleep(12)
print("timeout")
sys.exit(1)
