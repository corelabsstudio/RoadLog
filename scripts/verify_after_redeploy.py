"""Verify path traversal fix + health + AI after Railway redeploy."""
from __future__ import annotations

import json
import secrets
import time
import urllib.error
import urllib.request

BASE = "https://roadlog.co.kr"


def get(url: str) -> tuple[int | None, bytes]:
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return None, str(e).encode()


def main() -> None:
    print("=== health ===")
    st, b = get(BASE + "/api/health")
    print(st, b.decode("utf-8", errors="replace")[:500])
    try:
        health = json.loads(b.decode("utf-8"))
    except Exception:
        health = {}

    print("\n=== path traversal ===")
    paths = [
        "/../../../etc/passwd",
        "/icons/../../server.py",
        "/icons/../../../etc/passwd",
        "/icons/logo.svg",
    ]
    all_safe = True
    for p in paths:
        st, body = get(BASE + p)
        text_head = body[:80]
        leak = (
            body.startswith(b"root:x:")
            or (b"FastAPI" in body[:300] and b"uvicorn" in body[:500])
            or body.lstrip().startswith(b'"""')
            and b"RoadLog" in body[:200]
        )
        if p.endswith("logo.svg"):
            ok = st == 200 and b"<svg" in body[:50]
            print(("PASS" if ok else "FAIL"), st, p, "logo")
            all_safe = all_safe and ok
        else:
            # must NOT leak; 404 is ideal; SPA index 200 without leak is acceptable-ish but prefer 404
            if leak:
                print("FAIL LEAK", st, p, text_head[:40])
                all_safe = False
            else:
                print("PASS safe", st, p, text_head[:40])

    print("\n=== AI generate smoke ===")
    email = f"sec_{secrets.token_hex(3)}@roadlog.test"
    pw = "SecTest9x"
    urllib.request.urlopen(
        urllib.request.Request(
            BASE + "/api/auth/register",
            data=json.dumps({"email": email, "password": pw, "name": "S"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        ),
        timeout=30,
    )
    login = json.loads(
        urllib.request.urlopen(
            urllib.request.Request(
                BASE + "/api/auth/login",
                data=json.dumps({"email": email, "password": pw}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST",
            ),
            timeout=30,
        ).read()
    )
    tok = login["token"]
    body = {
        "raw_text": "오전 강남 방문 후 복귀",
        "vehicle_number": "12가3456",
        "morning_places": "강남",
        "settings": {
            "driver_name": "홍",
            "company_name": "코어",
            "vehicle_number": "12가3456",
        },
    }
    req = urllib.request.Request(
        BASE + "/api/generate",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {tok}",
        },
        method="POST",
    )
    t0 = time.time()
    gen = json.loads(urllib.request.urlopen(req, timeout=120).read().decode())
    print(
        "engine",
        gen.get("engine"),
        "sec",
        round(time.time() - t0, 1),
        "has_log",
        bool(gen.get("log")),
    )

    print("\n=== SUMMARY ===")
    print(
        "health openai=",
        health.get("openai"),
        "production=",
        health.get("production"),
        "path_safe=",
        all_safe,
        "ai=",
        gen.get("engine"),
    )


if __name__ == "__main__":
    main()
