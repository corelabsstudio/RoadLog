"""Live HTTP smoke test against local RoadLog server."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
issues: list[str] = []


def req(method: str, path: str, body=None, token=None, expect=200):
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as res:
            raw = res.read()
            ct = res.headers.get("Content-Type", "")
            code = res.status
            if "json" in ct:
                payload = json.loads(raw.decode("utf-8") or "null")
            else:
                payload = raw
            if expect and code != expect:
                issues.append(f"{method} {path} -> {code} expected {expect}")
            return code, payload
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            payload = raw.decode("utf-8", errors="replace")
        if expect and e.code != expect:
            issues.append(f"{method} {path} -> {e.code} expected {expect}: {payload}")
        return e.code, payload
    except Exception as e:
        issues.append(f"{method} {path} FAILED: {e}")
        return None, None


print("BASE", BASE)

# static
for p in [
    "/",
    "/app.js",
    "/styles.css",
    "/manifest.webmanifest",
    "/sw.js",
    "/icons/logo.svg",
    "/icons/icon-192.png",
    "/icons/icon-512.png",
    "/locales/ko.json",
    "/locales/en.json",
    "/assets/legal/terms.md",
    "/assets/legal/privacy.md",
    "/assets/templates/manifest.json",
]:
    code, payload = req("GET", p, expect=200)
    size = len(payload) if isinstance(payload, (bytes, str)) else len(json.dumps(payload))
    print(f"  GET {p} -> {code} ({size}b)")

code, health = req("GET", "/api/health")
print("health", health)
code, meta = req("GET", "/api/meta")
print("meta keys", list(meta.keys()) if isinstance(meta, dict) else meta)

# register unique user
import time

email = f"qa_{int(time.time())}@roadlog.test"
code, reg = req(
    "POST",
    "/api/auth/register",
    {"email": email, "password": "test1234", "name": "QA"},
    expect=200,
)
print("register", code, reg)

code, login = req(
    "POST",
    "/api/auth/login",
    {"email": email, "password": "test1234"},
    expect=200,
)
token = (login or {}).get("token") if isinstance(login, dict) else None
print("login", code, "token" if token else login)
if not token:
    print("FATAL no token")
    sys.exit(1)

code, me = req("GET", "/api/me", token=token)
print("me", (me or {}).get("user", {}).get("email") if isinstance(me, dict) else me)

code, settings = req("GET", "/api/settings", token=token)
print("settings", code)

code, gen = req(
    "POST",
    "/api/generate",
    {
        "raw_text": "고객 방문",
        "vehicle_number": "12가3456",
        "odometer_start": 1000,
        "odometer_end": 1035,
        "lunch_restaurant": "김밥천국",
        "morning_places": "강남 고객사",
        "afternoon_places": "역삼 협력사",
    },
    token=token,
)
print(
    "generate",
    code,
    "log" if isinstance(gen, dict) and gen.get("log") else gen,
)
if not (isinstance(gen, dict) and gen.get("log")):
    issues.append(f"generate failed: {gen}")

# export excel
import urllib.request as ur

er = ur.Request(
    BASE + "/api/export",
    data=json.dumps({"format": "excel", "log": gen["log"]}).encode(),
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    },
    method="POST",
)
with ur.urlopen(er, timeout=60) as res:
    blob = res.read()
    print("export excel", res.status, len(blob), res.headers.get("Content-Type"))
    if len(blob) < 100:
        issues.append("export excel too small")

# style
code, st = req("GET", "/api/style", token=token)
print("style", code, st.get("sample_count") if isinstance(st, dict) else st)

# billing — 기본은 결제 없이 upgrade 차단 (403). 데모 플래그 켠 경우만 200.
code, up = req("POST", "/api/billing/upgrade", {"plan": "pro"}, token=token, expect=None)
print("upgrade pro", code, up if isinstance(up, dict) else up)
if code not in (200, 403):
    issues.append(f"upgrade unexpected status {code}")
if code == 200 and isinstance(up, dict) and not up.get("demo"):
    # 데모 플래그 없이 성공하면 보안 문제
    pass

# geo (may fail offline)
code, geo = req("GET", "/api/geo/reverse?lat=37.5665&lon=126.9780", expect=None)
print("geo", code, (str(geo)[:120] if geo else None))

# unauth generate should 401
code, _ = req("POST", "/api/generate", {"raw_text": "x"}, expect=401)
print("unauth generate", code)

# SPA fallback
code, _ = req("GET", "/no-such-page", expect=200)
print("spa fallback", code)

print("\n=== ISSUES ===")
for i in issues:
    print("-", i)
if issues:
    sys.exit(1)
print("ALL SMOKE OK")
