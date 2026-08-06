# -*- coding: utf-8 -*-
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

RL_BUILD = "20260729-deep-qa"
WA_BUILD = "20260729-deep-qa"

root = pathlib.Path(r"C:\Users\hysoo\projects\RoadLog\web")
(root / "build.json").write_text(
    f'{{"build":"{RL_BUILD}","note":"source of truth for auto-update"}}\n',
    encoding="utf-8",
)
sw = (root / "sw.js").read_text(encoding="utf-8")
sw = re.sub(r'VERSION\s*=\s*"[^"]+"', f'VERSION = "{RL_BUILD}"', sw, count=1)
(root / "sw.js").write_text(sw, encoding="utf-8", newline="\n")

ih = (root / "index.html").read_text(encoding="utf-8")
ih = re.sub(
    r'(<meta\s+name="rl-build"\s+content=")[^"]+(")',
    rf"\g<1>{RL_BUILD}\2",
    ih,
    count=1,
)
ih = re.sub(r'var BUILD = "[^"]+"', f'var BUILD = "{RL_BUILD}"', ih, count=1)
ih = re.sub(r"styles\.css\?v=[^\"]+", f"styles.css?v={RL_BUILD}", ih)
ih = re.sub(r"app\.js\?v=[^\"]+", f"app.js?v={RL_BUILD}", ih)
(root / "index.html").write_text(ih, encoding="utf-8", newline="\n")

# resources
res = (root / "resources" / "index.html").read_text(encoding="utf-8")
res = re.sub(r"styles\.css\?v=[^\"]+", f"styles.css?v={RL_BUILD}", res)
res = re.sub(r"blog\.css\?v=[^\"]+", f"blog.css?v={RL_BUILD}", res)
(root / "resources" / "index.html").write_text(res, encoding="utf-8", newline="\n")

print("RoadLog ->", RL_BUILD)

# WakeAgain — bump all html that reference styles.css
wa = pathlib.Path(r"C:\Users\hysoo\projects\WakeAgain\public")
n = 0
for p in wa.rglob("*.html"):
    t = p.read_text(encoding="utf-8")
    if "styles.css" not in t and "yard-theme.css" not in t and "app.css" not in t:
        continue
    orig = t
    for name in ("styles.css", "ux9.css", "yard-theme.css", "app.css", "blog.css", "guide-visual.css", "legal.css"):
        t = re.sub(
            rf"({re.escape(name)})(\?v=[^\"']*)?",
            rf"\1?v={WA_BUILD}",
            t,
        )
    if t != orig:
        p.write_text(t, encoding="utf-8", newline="\n")
        n += 1
        print("WA", p.relative_to(wa))
print("WakeAgain pages bumped:", n, "->", WA_BUILD)
