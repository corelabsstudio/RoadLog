# -*- coding: utf-8 -*-
import json
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

root = pathlib.Path(r"C:\Users\hysoo\projects\RoadLog\web")
rt = (root / "resources" / "index.html").read_text(encoding="utf-8")
hrefs = re.findall(r'href="([^"]+)"', rt)
print("=== resources hrefs ===")
missing = []
for h in hrefs:
    print(" ", h)
    if h.startswith(("http", "#", "mailto", "javascript")):
        continue
    if h.startswith("/"):
        p = root / h.lstrip("/")
    else:
        p = root / "resources" / h
    if not p.exists() and not p.is_dir():
        # directory index
        if not (p.with_name(p.name) ).exists():
            missing.append(str(p))
            print("   MISSING", p)

man = json.loads((root / "assets" / "templates" / "manifest.json").read_text(encoding="utf-8"))
print("\n=== template manifest ===")
print(type(man), list(man)[:10] if isinstance(man, dict) else len(man))
if isinstance(man, dict):
    files = man.get("templates") or man.get("files") or man.get("items") or []
    if not files:
        print(json.dumps(man, ensure_ascii=False)[:800])
    for it in files:
        if isinstance(it, str):
            fp = root / "assets" / "templates" / it
            print(("OK" if fp.exists() else "MISS"), it)
        elif isinstance(it, dict):
            name = it.get("file") or it.get("path") or it.get("href") or it.get("name")
            print(it)

# WA assets from index
wa = pathlib.Path(r"C:\Users\hysoo\projects\WakeAgain\public")
wih = (wa / "index.html").read_text(encoding="utf-8")
for attr in re.findall(r'(?:href|src)="(/[^"#?]+)', wih):
    p = wa / attr.lstrip("/")
    if attr.endswith("/") or attr in ("/app", "/blog", "/guide"):
        continue
    if p.suffix and not p.exists():
        print("WA MISS", attr)

print("\nmissing resources:", missing or "none")
