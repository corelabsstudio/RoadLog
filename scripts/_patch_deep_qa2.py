# -*- coding: utf-8 -*-
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# 1) WA app.js optional chaining for $("id").addEventListener
wa_js = Path(r"C:\Users\hysoo\projects\WakeAgain\public\app\app.js")
t = wa_js.read_text(encoding="utf-8")
t2 = re.sub(r'\$\("([^"]+)"\)\.addEventListener', r'$("\1")?.addEventListener', t)
# also $('id') style if any
t2 = re.sub(r"\$\('([^']+)'\)\.addEventListener", r"$('\1')?.addEventListener", t2)
wa_js.write_text(t2, encoding="utf-8", newline="\n")
print("WA app.js optional binds", t2.count(")?.addEventListener"))
print("WA bare leftover", len(re.findall(r'\$\("[^"]+"\)\.addEventListener', t2)))

# 2) Bump RL
BUILD = "20260729-deep-qa2"
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

res = (root / "resources" / "index.html").read_text(encoding="utf-8")
res = re.sub(r"styles\.css\?v=[^\"]+", f"styles.css?v={BUILD}", res)
res = re.sub(r"blog\.css\?v=[^\"]+", f"blog.css?v={BUILD}", res)
(root / "resources" / "index.html").write_text(res, encoding="utf-8", newline="\n")

uh = (root / "update.html").read_text(encoding="utf-8")
uh = re.sub(r'BUILD = "[^"]+"', f'BUILD = "{BUILD}"', uh)
(root / "update.html").write_text(uh, encoding="utf-8", newline="\n")
print("RL", BUILD)

# 3) WA app shell cache
wa_idx = Path(r"C:\Users\hysoo\projects\WakeAgain\public\app\index.html")
t = wa_idx.read_text(encoding="utf-8")
for name in ("app.js", "app.css", "styles.css", "ux9.css", "yard-theme.css"):
    t = re.sub(rf"{re.escape(name)}\?v=[^\"]+", f"{name}?v=20260729-deep-qa2", t)
wa_idx.write_text(t, encoding="utf-8", newline="\n")
print("WA app index cache deep-qa2")
print("app.js link", re.search(r'app\.js\?v=[^"]+', t).group(0))
