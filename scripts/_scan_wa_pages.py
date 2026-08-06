# -*- coding: utf-8 -*-
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
wa = Path(r"C:\Users\hysoo\projects\WakeAgain\public")
for p in sorted(wa.rglob("*.html")):
    t = p.read_text(encoding="utf-8", errors="replace")
    if "styles.css" not in t:
        continue
    has_yard = "yard-theme" in t
    has_theme = "theme-yard" in t
    v = re.search(r"styles\.css\?v=([^\"\s>]+)", t)
    print(
        f"{p.relative_to(wa)} yard_link={has_yard} theme_class={has_theme} v={v.group(1) if v else 'none'}"
    )
