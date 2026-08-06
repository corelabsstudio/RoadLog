# -*- coding: utf-8 -*-
from pathlib import Path
import re

BUILD = "20260729-phones"
root = Path(r"C:\Users\hysoo\projects\RoadLog\web")
(root / "build.json").write_text(
    f'{{"build":"{BUILD}","note":"source of truth for auto-update"}}\n', encoding="utf-8"
)
sw = (root / "sw.js").read_text(encoding="utf-8")
sw = re.sub(r'VERSION\s*=\s*"[^"]+"', f'VERSION = "{BUILD}"', sw, count=1)
(root / "sw.js").write_text(sw, encoding="utf-8", newline="\n")

ih = (root / "index.html").read_text(encoding="utf-8")
ih = re.sub(
    r'(<meta\s+name="rl-build"\s+content=")[^"]+(")',
    rf"\g<1>{BUILD}\2",
    ih,
    count=1,
)
ih = re.sub(r'var BUILD = "[^"]+"', f'var BUILD = "{BUILD}"', ih, count=1)
ih = re.sub(r"styles\.css\?v=[^\"]+", f"styles.css?v={BUILD}", ih)
ih = re.sub(r"app\.js\?v=[^\"]+", f"app.js?v={BUILD}", ih)
(root / "index.html").write_text(ih, encoding="utf-8", newline="\n")

for rel in ["resources/index.html", "legal/business.html"]:
    p = root / rel
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    t = re.sub(r"styles\.css\?v=[^\"]+", f"styles.css?v={BUILD}", t)
    t = re.sub(r"blog\.css\?v=[^\"]+", f"blog.css?v={BUILD}", t)
    p.write_text(t, encoding="utf-8", newline="\n")

print("bumped", BUILD)
