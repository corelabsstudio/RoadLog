# -*- coding: utf-8 -*-
import pathlib
import re

RL_BUILD = "20260729-qa-fix"
WA_BUILD = "20260729-yard-fix"

# RoadLog
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
print("RoadLog ->", RL_BUILD)

# WakeAgain
wa = pathlib.Path(r"C:\Users\hysoo\projects\WakeAgain\public")
for p in [wa / "index.html", wa / "app" / "index.html", wa / "sell.html", wa / "buy.html"]:
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    orig = t
    t = t.replace("20260729-accent", WA_BUILD)
    t = re.sub(r"styles\.css\?v=[^\"]+", f"styles.css?v={WA_BUILD}", t)
    t = re.sub(r"ux9\.css\?v=[^\"]+", f"ux9.css?v={WA_BUILD}", t)
    t = re.sub(r"yard-theme\.css\?v=[^\"]+", f"yard-theme.css?v={WA_BUILD}", t)
    t = re.sub(r"app\.css\?v=[^\"]+", f"app.css?v={WA_BUILD}", t)
    t = re.sub(r'(?<![\w-])app\.js\?v=[^\"]+', f"app.js?v={WA_BUILD}", t)
    if t != orig:
        p.write_text(t, encoding="utf-8", newline="\n")
        print("updated", p.relative_to(wa.parent))
    else:
        print("unchanged", p.name)
print("WakeAgain ->", WA_BUILD)
