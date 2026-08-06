# -*- coding: utf-8 -*-
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
req = urllib.request.Request(
    "https://wakeagain.com/app/?t=probe",
    headers={"User-Agent": "qa", "Cache-Control": "no-cache"},
)
with urllib.request.urlopen(req, timeout=25) as r:
    t = r.read().decode("utf-8", "replace")
print("len", len(t))
print("title", re.search(r"<title>[^<]+</title>", t).group(0))
print("body", re.search(r"<body[^>]*>", t).group(0))
print("app-body", "app-body" in t)
print("theme-yard", "theme-yard" in t)
print("app.js", bool(re.search(r"app\.js", t)))
for m in re.findall(r'src="([^"]+)"', t)[:20]:
    print("src", m)
for m in re.findall(r'href="([^"]+\.css[^"]*)"', t)[:15]:
    print("css", m)
