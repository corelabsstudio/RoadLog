# -*- coding: utf-8 -*-
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
req = urllib.request.Request(
    "https://wakeagain.com/app/?t=dom",
    headers={"User-Agent": "qa", "Cache-Control": "no-cache"},
)
with urllib.request.urlopen(req, timeout=25) as r:
    t = r.read().decode("utf-8", "replace")
print("len", len(t))
print("body tag", re.search(r"<body[^>]*>", t).group(0))
print("app-top count", t.count("app-top"))
print("formLogin", "formLogin" in t)
print("theme-yard", "theme-yard" in t)
print("app-body", "app-body" in t)
# unclosed / script issues
print("script opens", len(re.findall(r"<script", t, re.I)))
print("script closes", len(re.findall(r"</script>", t, re.I)))
print("title raw", re.search(r"<title>[^<]*</title>", t).group(0))
# find if header exists
print("header.app-top", bool(re.search(r'<header[^>]*class="[^"]*app-top', t)))
# check for accidental body close early
idx = t.find("<body")
print("body snippet", t[idx : idx + 400].replace("\n", " "))
