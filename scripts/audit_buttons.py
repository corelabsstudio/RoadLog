"""Static audit: HTML buttons/nav vs app.js handlers."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
js = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

# VIEW_MAP-like ids
views = set(re.findall(r'id="view-([^"]+)"', html))
navs = set(re.findall(r'data-nav="([^"]+)"', html))
btn_ids = set(re.findall(r'id="(btn[A-Za-z0-9_]+)"', html))
form_ids = set(re.findall(r'id="((?:auth|reg|login|gen|settings|style|admin|contact)[A-Za-z0-9_]*)"', html))

print("=== VIEWS ===")
print(sorted(views))
print("\n=== DATA-NAV ===")
print(sorted(navs))
print("\n=== NAV without view-* ===")
for n in sorted(navs):
    if n not in views:
        print("  missing view:", n)

print("\n=== BUTTON IDS (no #id or getElementById in JS) ===")
orphans = []
for bid in sorted(btn_ids):
    patterns = [
        f'#{bid}',
        f'"{bid}"',
        f"'{bid}'",
        f"getElementById(\"{bid}\")",
        f"getElementById('{bid}')",
    ]
    if not any(p in js for p in patterns):
        # data-nav buttons may not need JS id
        orphans.append(bid)
        print("  ORPHAN?", bid)

print("\n=== JS references to missing HTML ids (sample critical) ===")
# find $("#something") and getElementById
refs = set(re.findall(r'\$\(["\']#([A-Za-z0-9_-]+)["\']\)', js))
refs |= set(re.findall(r'getElementById\(["\']([A-Za-z0-9_-]+)["\']\)', js))
# dynamic created ids ok
dynamic = {
    "engineNotice",
    "resultWarnings",
    "freeModeBanner",
    "toast",
    "authAlert",
    "genAlert",
}
missing_html = []
for rid in sorted(refs):
    if rid in dynamic:
        continue
    if f'id="{rid}"' not in html and f"id='{rid}'" not in html:
        # maybe created in JS
        if f'id = "{rid}"' in js or f"id = '{rid}'" in js or f'id="{rid}"' in js:
            continue
        if f'"{rid}"' in js and "createElement" in js:
            # heuristic skip
            pass
        missing_html.append(rid)

# only report high-signal missing
interesting = [
    r
    for r in missing_html
    if r.startswith(("btn", "auth", "gen", "view", "nav", "pro", "ent", "price", "admin"))
    or r
    in (
        "authModal",
        "menuToggle",
        "landingReviewGrid",
        "pricingNote",
        "proLink",
        "entLink",
    )
]
print("potential missing ids referenced in JS:")
for r in interesting[:40]:
    print(" ", r)

print("\n=== bind function presence ===")
for name in (
    "bindAuth",
    "bindPricing",
    "bindSettings",
    "bindStyle",
    "bindAdmin",
    "bindQuickStamp",
    "bindPrint",
    "bindPwaInstall",
    "bindFeedbackForm",
    "showView",
):
    print(f"  {name}: {'yes' if f'function {name}' in js or f'{name}(' in js else 'NO'}")

print("\nDone. orphan_btns=", len(orphans))
