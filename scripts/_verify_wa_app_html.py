# -*- coding: utf-8 -*-
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")
wa = Path(r"C:\Users\hysoo\projects\WakeAgain\public")
bad = []
for p in wa.rglob("*.html"):
    t = p.read_text(encoding="utf-8")
    if t.count("<style") != t.count("</style>"):
        bad.append(f"style mismatch {p.relative_to(wa)} {t.count('<style')}/{t.count('</style>')}")
    if 'styles.css?v=' in t and re.search(r'styles\.css\?v=[^"\n]+"[a-zA-Z]', t):
        bad.append(f"corrupt styles version {p.relative_to(wa)}")
    if "wa-topbar-fix\">" in t and "<style id=\"wa-topbar-fix\">" not in t:
        bad.append(f"broken topbar style {p.relative_to(wa)}")
print("bad:", bad or "none")

t = (wa / "app" / "index.html").read_text(encoding="utf-8")
print("style", t.count("<style"), t.count("</style>"))
print("head closed", "</head>" in t)
print("style open ok", '<style id="wa-topbar-fix">' in t)
print("comment ok", "header{position:relative}" in t)
print("body", re.search(r"<body[^>]*>", t).group(0))
