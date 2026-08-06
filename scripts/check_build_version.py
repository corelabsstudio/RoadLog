import re
import urllib.request
from pathlib import Path

req = urllib.request.Request(
    "https://roadlog.co.kr/",
    headers={
        "Cache-Control": "no-cache",
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    },
)
html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", errors="replace")
print("LIVE len", len(html))
for label, pat in [
    ("rl-build", r'name="rl-build"\s+content="([^"]+)"'),
    ("BUILD", r'var BUILD = "([^"]+)"'),
    ("app.js", r'app\.js\?v=([^"&]+)'),
    ("styles.css", r'styles\.css\?v=([^"&]+)'),
]:
    m = re.search(pat, html)
    print("LIVE", label, "->", m.group(1) if m else None)

local = Path("web/index.html").read_text(encoding="utf-8")
print("LOCAL len", len(local))
for label, pat in [
    ("rl-build", r'name="rl-build"\s+content="([^"]+)"'),
    ("BUILD", r'var BUILD = "([^"]+)"'),
    ("app.js", r'app\.js\?v=([^"&]+)'),
    ("styles.css", r'styles\.css\?v=([^"&]+)'),
]:
    m = re.search(pat, local)
    print("LOCAL", label, "->", m.group(1) if m else None)
