# -*- coding: utf-8 -*-
"""Ensure key WakeAgain HTML pages load yard-theme + theme-yard + cache bust."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

WA = Path(r"C:\Users\hysoo\projects\WakeAgain\public")
BUILD = "20260729-deep-qa"

# Pages that should be yard-themed (marketing/app-adjacent)
TARGETS = [
    "index.html",
    "sell.html",
    "buy.html",
    "get-app.html",
    "project.html",
    "review.html",
    "showcase.html",
    "showcase-new.html",
    "diagnose.html",
    "promo/event.html",
    "app/index.html",
]


def patch(path: Path) -> bool:
    t = path.read_text(encoding="utf-8")
    orig = t

    # bump known cache versions on core CSS
    for name in ("styles.css", "ux9.css", "yard-theme.css", "app.css"):
        t = re.sub(
            rf'({re.escape(name)})(\?v=[^"\']*)?',
            rf"\1?v={BUILD}",
            t,
        )

    # ensure yard-theme link after styles.css if missing
    if "yard-theme.css" not in t and "styles.css" in t:
        t = re.sub(
            r'(<link[^>]+styles\.css[^>]*>)',
            rf'\1\n  <link rel="stylesheet" href="/yard-theme.css?v={BUILD}" />',
            t,
            count=1,
        )

    # ensure body has theme-yard
    if re.search(r"<body([^>]*)>", t, re.I):
        def body_sub(m):
            attrs = m.group(1)
            if "theme-yard" in attrs:
                return m.group(0)
            if "class=" in attrs:
                attrs2 = re.sub(
                    r'class=(["\'])([^"\']*)\1',
                    lambda mm: f'class={mm.group(1)}{mm.group(2)} theme-yard{mm.group(1)}'
                    if "theme-yard" not in mm.group(2)
                    else mm.group(0),
                    attrs,
                    count=1,
                )
                return f"<body{attrs2}>"
            return f'<body class="theme-yard"{attrs}>'

        t = re.sub(r"<body([^>]*)>", body_sub, t, count=1, flags=re.I)

    if t != orig:
        path.write_text(t, encoding="utf-8", newline="\n")
        return True
    return False


changed = []
for rel in TARGETS:
    p = WA / rel
    if not p.exists():
        print("skip missing", rel)
        continue
    if patch(p):
        changed.append(rel)
        print("patched", rel)
    else:
        print("ok", rel)

print("changed", len(changed), changed)
