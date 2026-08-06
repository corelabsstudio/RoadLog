"""Bump RoadLog front-end build id in index/sw/update/build.json so PWA auto-update stays in sync.

Usage:
  python scripts/bump_build.py 20260727-reload-fix
"""
import re
import sys
from pathlib import Path

NEW = sys.argv[1] if len(sys.argv) > 1 else "20260712-force-v20"
ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"

# Any prior rl-build style token: YYYYMMDD-label
BUILD_RE = re.compile(r"20\d{6}-[a-z0-9.-]+")


def replace_builds(text: str) -> str:
    return BUILD_RE.sub(NEW, text)


# index.html
idx = WEB / "index.html"
t = idx.read_text(encoding="utf-8")
idx.write_text(replace_builds(t), encoding="utf-8", newline="\n")

# sw.js — VERSION constant is authoritative
sw = WEB / "sw.js"
st = sw.read_text(encoding="utf-8")
st = re.sub(r'const VERSION = "[^"]+"', f'const VERSION = "{NEW}"', st)
st = replace_builds(st)
sw.write_text(st, encoding="utf-8", newline="\n")

# update.html
up = WEB / "update.html"
if up.exists():
    ut = up.read_text(encoding="utf-8")
    up.write_text(replace_builds(ut), encoding="utf-8", newline="\n")

# build.json — clients poll this
(WEB / "build.json").write_text(
    f'{{"build":"{NEW}","note":"source of truth for auto-update"}}\n',
    encoding="utf-8",
)

print("bumped to", NEW)
for p in (idx, sw, up, WEB / "build.json"):
    if p.exists():
        body = p.read_text(encoding="utf-8")
        print(p.name, "ok" if NEW in body else "MISSING", "stale" if "20260722-sound-v1" in body else "")
