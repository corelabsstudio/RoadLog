import re
from pathlib import Path

import sys

NEW = sys.argv[1] if len(sys.argv) > 1 else "20260712-force-v20"
ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

# index.html
idx = WEB / "index.html"
t = idx.read_text(encoding="utf-8")
t = re.sub(r"2026071[12]-[a-z0-9.-]+", NEW, t)
idx.write_text(t, encoding="utf-8", newline="\n")

# sw.js
sw = WEB / "sw.js"
st = sw.read_text(encoding="utf-8")
st = re.sub(r'const VERSION = "[^"]+"', f'const VERSION = "{NEW}"', st)
st = re.sub(r"2026071[12]-[a-z0-9.-]+", NEW, st)
sw.write_text(st, encoding="utf-8", newline="\n")

# update.html
up = WEB / "update.html"
if up.exists():
    ut = up.read_text(encoding="utf-8")
    ut = re.sub(r"2026071[12]-[a-z0-9.-]+", NEW, ut)
    up.write_text(ut, encoding="utf-8", newline="\n")

# build.json — clients poll this
(WEB / "build.json").write_text(
    f'{{"build":"{NEW}","note":"source of truth for auto-update"}}\n',
    encoding="utf-8",
)

print("bumped to", NEW)
for p in (idx, sw, up, WEB / "build.json"):
    if p.exists():
        print(p.name, NEW in p.read_text(encoding="utf-8"))
