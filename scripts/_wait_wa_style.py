# -*- coding: utf-8 -*-
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
for i in range(24):
    req = urllib.request.Request(
        "https://wakeagain.com/app/?t=" + str(time.time()),
        headers={"Cache-Control": "no-cache", "User-Agent": "qa"},
    )
    t = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
    ok = '<style id="wa-topbar-fix">' in t and 'styles.css?v=20260729-deep-qa2"wa-topbar' not in t
    print(i, "style_ok", ok, "len", len(t))
    if ok:
        sys.exit(0)
    time.sleep(10)
sys.exit(1)
