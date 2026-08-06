"""Compare roadlog.co.kr vs railway.app health."""
from __future__ import annotations

import json
import re
import urllib.request


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"Cache-Control": "no-cache", "Pragma": "no-cache"}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> None:
    hosts = [
        "https://roadlog.co.kr",
        "https://web-production-e4153e.up.railway.app",
    ]
    for host in hosts:
        print(f"======== {host} ========")
        try:
            health = json.loads(fetch(f"{host}/api/health"))
            print("health:", json.dumps(health, ensure_ascii=False))
            print(
                "  env={env} openai={openai} production={production}".format(
                    env=health.get("env"),
                    openai=health.get("openai"),
                    production=health.get("production"),
                )
            )
            print(
                "  cost_mode={cm} keys={keys}".format(
                    cm=health.get("cost_mode"),
                    keys=sorted(health.keys()),
                )
            )
        except Exception as e:
            print("health ERR:", e)

        try:
            html = fetch(f"{host}/")
            m = re.search(r'name="rl-build"\s+content="([^"]+)"', html)
            print("build:", m.group(1) if m else "not found")
        except Exception as e:
            print("home ERR:", e)
        print()


if __name__ == "__main__":
    main()
