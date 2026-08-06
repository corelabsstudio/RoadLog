"""Check roadlog.co.kr after Railway deploy."""
from __future__ import annotations

import json
import re
import urllib.request


def fetch(url: str) -> tuple[str, dict]:
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read().decode("utf-8", errors="replace")
        headers = {k.lower(): v for k, v in r.headers.items()}
        return body, headers


def main() -> None:
    print("=== /api/health ===")
    text, _ = fetch("https://roadlog.co.kr/api/health")
    print(text)
    d = json.loads(text)
    print("--- summary ---")
    for k in (
        "ok",
        "env",
        "production",
        "openai",
        "cost_mode",
        "free_mode",
        "storage",
        "storage_persistent",
        "llm_provider",
        "launch_ready",
        "demo_billing_upgrade",
        "data_dir",
    ):
        if k in d:
            print(f"  {k}: {d[k]}")

    print("\n=== /api/meta flags ===")
    text, _ = fetch("https://roadlog.co.kr/api/meta")
    m = json.loads(text)
    print(f"  cost_mode: {m.get('cost_mode')}")
    print(f"  free_mode: {m.get('free_mode')}")
    print(f"  has cost_mode: {'cost_mode' in m}")
    print(f"  free_limit: {m.get('free_limit')}")

    print("\n=== home build ===")
    html, _ = fetch("https://roadlog.co.kr/")
    bm = re.search(r'name="rl-build"\s+content="([^"]+)"', html)
    print(f"  rl-build: {bm.group(1) if bm else 'not found'}")
    bm2 = re.search(r'var BUILD = "([^"]+)"', html)
    print(f"  BUILD js: {bm2.group(1) if bm2 else 'not found'}")

    # verdict
    print("\n=== VERDICT ===")
    openai_ok = bool(d.get("openai"))
    prod = bool(d.get("production")) or d.get("env") == "production"
    hybrid = d.get("cost_mode") == "hybrid" or m.get("cost_mode") == "hybrid"
    new_code = "cost_mode" in d or "cost_mode" in m
    if openai_ok and (prod or new_code):
        print("OK-ish: OpenAI key recognized on live.")
    elif openai_ok:
        print("PARTIAL: openai true, but env/code may still be old.")
    else:
        print("NOT READY: openai still false or deploy not updated.")
    print(f"  openai={openai_ok} production={prod} new_code={new_code} hybrid={hybrid}")


if __name__ == "__main__":
    main()
