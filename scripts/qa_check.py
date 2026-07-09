"""Static QA: HTML/JS wiring, syntax, API coverage."""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
JS = (WEB / "app.js").read_text(encoding="utf-8")
HTML = (WEB / "index.html").read_text(encoding="utf-8")
SERVER = (ROOT / "server.py").read_text(encoding="utf-8")

issues: list[tuple[str, str]] = []


def issue(sev: str, msg: str) -> None:
    issues.append((sev, msg))


# 1) JS IDs vs HTML
js_ids = set(re.findall(r"""\$\(['"]#([A-Za-z_][\w-]*)['"]\)""", JS))
js_ids |= set(re.findall(r"""getElementById\(['"]([A-Za-z_][\w-]*)['"]\)""", JS))
html_ids = set(re.findall(r"""\bid=["']([A-Za-z_][\w-]*)["']""", HTML))
missing = sorted(js_ids - html_ids)
# Known dynamic / optional
skip = {
    "demoStage",
    "demoVideoWrap",
    "demoVideo",
    "demoPlayer",
    "demoPlayBtn",
    "demoProgress",
    "demoSteps",  # may be in HTML
}
for m in missing:
    if m in skip:
        continue
    # stamp-full-* is dynamic
    if m.startswith("stamp-full"):
        continue
    issue("bug", f"JS references #{m} but HTML has no such id")

# 2) data-nav targets in VIEW_MAP
view_map = re.search(r"const VIEW_MAP = \{([^}]+)\}", JS, re.S)
views = set(re.findall(r"(\w+)\s*:", view_map.group(1))) if view_map else set()
navs = set(re.findall(r"""data-nav=["']([^"']+)["']""", HTML))
for n in sorted(navs):
    if n not in views:
        issue("bug", f"data-nav='{n}' not in VIEW_MAP")

# view sections
for v in ["home", "create", "pricing", "style", "admin", "settings", "terms", "privacy", "about", "contact"]:
    if f'id="view-{v}"' not in HTML:
        issue("bug", f"missing section view-{v}")

# 3) API paths used in JS vs server
js_apis = set(re.findall(r"""['"`](/api/[^"'`?\s]+)""", JS))
# normalize template strings
js_apis = {re.sub(r"\$\{[^}]+\}", "{id}", a) for a in js_apis}
server_routes = set(re.findall(r"""@app\.(get|post|put|delete|patch)\(["']([^"']+)["']""", SERVER))
server_paths = {p for _, p in server_routes}

def route_exists(path: str) -> bool:
    # exact or pattern match for {sample_id} style
    if path in server_paths:
        return True
    # /api/style/samples/{id}/activate
    for sp in server_paths:
        # convert FastAPI {param} to regex
        pat = re.sub(r"\{[^}]+\}", r"[^/]+", sp)
        if re.fullmatch(pat, path.replace("{id}", "x")):
            return True
        # also try js template form
        jp = path.replace("{id}", "x")
        if re.fullmatch(pat, jp):
            return True
    return False

for api in sorted(js_apis):
    check = api
    # skip locale etc
    if not api.startswith("/api/"):
        continue
    # dynamic: /api/admin/vip/${...} already normalized
    if not route_exists(check) and not route_exists(check.replace("{id}", "x")):
        # try matching with path segments
        matched = False
        for sp in server_paths:
            sparts = sp.split("/")
            aparts = check.replace("{id}", "x").split("/")
            if len(sparts) != len(aparts):
                continue
            ok = True
            for sseg, aseg in zip(sparts, aparts):
                if sseg.startswith("{") and sseg.endswith("}"):
                    continue
                if sseg != aseg:
                    ok = False
                    break
            if ok:
                matched = True
                break
        if not matched:
            issue("bug", f"JS calls {api} but server has no matching route")

# 4) Static assets existence
for rel in [
    "icons/logo.svg",
    "icons/icon-192.png",
    "icons/icon-512.png",
    "manifest.webmanifest",
    "sw.js",
    "styles.css",
    "app.js",
    "locales/ko.json",
    "locales/en.json",
    "assets/legal/terms.md",
    "assets/legal/privacy.md",
    "assets/templates/manifest.json",
]:
    if not (WEB / rel).is_file():
        issue("bug", f"missing static file web/{rel}")

# 5) locales JSON valid + key parity sample
ko = json.loads((WEB / "locales/ko.json").read_text(encoding="utf-8"))
en = json.loads((WEB / "locales/en.json").read_text(encoding="utf-8"))
only_ko = sorted(set(ko) - set(en))
only_en = sorted(set(en) - set(ko))
if only_ko:
    issue("warn", f"i18n keys only in ko ({len(only_ko)}): {only_ko[:8]}")
if only_en:
    issue("warn", f"i18n keys only in en ({len(only_en)}): {only_en[:8]}")

# 6) HTML data-i18n keys exist in ko
i18n_keys = set(re.findall(r"""data-i18n=["']([^"']+)["']""", HTML))
i18n_keys |= set(re.findall(r"""data-i18n-title=["']([^"']+)["']""", HTML))
i18n_keys |= set(re.findall(r"""data-i18n-aria=["']([^"']+)["']""", HTML))
for k in sorted(i18n_keys):
    if k not in ko:
        issue("warn", f"data-i18n='{k}' missing in ko.json")

# 7) Syntax check: node if available else bracket balance
try:
    import subprocess

    r = subprocess.run(
        ["node", "--check", str(WEB / "app.js")],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if r.returncode != 0:
        issue("bug", f"app.js syntax error: {r.stderr.strip() or r.stdout.strip()}")
    else:
        print("OK node --check app.js")
except FileNotFoundError:
    # rough balance
    for open_c, close_c in [("(", ")"), ("{", "}"), ("[", "]")]:
        if JS.count(open_c) != JS.count(close_c):
            issue("warn", f"bracket imbalance {open_c}{close_c}: {JS.count(open_c)} vs {JS.count(close_c)}")

# 8) Python syntax
try:
    ast.parse(SERVER)
    print("OK server.py parse")
except SyntaxError as e:
    issue("bug", f"server.py syntax: {e}")

# 9) Critical: preventDefault on auth forms
if "authLoginForm" in JS and "preventDefault" not in JS:
    issue("bug", "auth forms may lack preventDefault")

# 10) anchors with href=# that are not data-nav
orphan = re.findall(r"""<a[^>]+href=["']#([^"']*)["'][^>]*>""", HTML)
for h in orphan:
    # check if same tag has data-nav — approximate
    pass

# price links
if 'id="proLink" href="#"' in HTML or "id=\"proLink\" href=\"#\"" in HTML:
    # only bug if never updated and user clicks — meta may set
    pass

print("\n=== VIEW_MAP ===", sorted(views))
print("=== data-nav ===", sorted(navs))
print("=== JS APIs ===", sorted(js_apis))
print("=== Server routes ===", sorted(server_paths))
print(f"\n=== ISSUES ({len(issues)}) ===")
for sev, msg in issues:
    print(f"[{sev}] {msg}")
if not issues:
    print("(none)")

bugs = [m for s, m in issues if s == "bug"]
sys.exit(1 if bugs else 0)
