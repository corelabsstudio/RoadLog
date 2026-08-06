# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
wa = Path(r"C:\Users\hysoo\projects\WakeAgain\public")
for rel in [
    "index.html",
    "get-app.html",
    "app/index.html",
    "sell.html",
    "buy.html",
    "project.html",
]:
    s = (wa / rel).read_text(encoding="utf-8")
    yards = len(re.findall(r"yard-theme\.css", s))
    body = re.search(r"<body[^>]*>", s, re.I)
    vs = re.findall(r"(?:styles|yard-theme|ux9|app)\.css\?v=([^\"']+)", s)
    print(rel)
    print("  body:", body.group(0) if body else None)
    print("  yard_css_count:", yards)
    print("  versions:", vs[:8])
    if "theme-yard theme-yard" in s:
        print("  DOUBLE theme-yard class!")
