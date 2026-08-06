# -*- coding: utf-8 -*-
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAILWAY = r"C:\Users\hysoo\AppData\Roaming\npm\railway.cmd"


def deployments(cwd: str, service: str | None = None) -> list[dict]:
    cmd = [RAILWAY, "deployment", "list", "--json"]
    if service:
        cmd += ["-s", service]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except Exception:
        print("list fail", r.stderr[:200], r.stdout[:200])
        return []


def get(url: str) -> str:
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "x", "Cache-Control": "no-cache"}
        )
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"ERR:{e}"


def main() -> int:
    rl = str(Path(r"C:\Users\hysoo\Projects\RoadLog"))
    wa = str(Path(r"C:\Users\hysoo\Projects\WakeAgain"))
    for i in range(45):
        print(f"\n=== {i} {time.strftime('%H:%M:%S')}", flush=True)
        d_rl = deployments(rl)
        d_wa = deployments(wa, "wakeagain")
        print(
            "RL",
            [(x.get("status"), x.get("id", "")[:8]) for x in d_rl[:3]],
            flush=True,
        )
        print(
            "WA",
            [(x.get("status"), x.get("id", "")[:8]) for x in d_wa[:3]],
            flush=True,
        )
        rl_build = get("https://roadlog.co.kr/build.json")
        rl_js = get("https://roadlog.co.kr/ui-sound.js")
        rl_html = get("https://roadlog.co.kr/")
        wa_js = get("https://wakeagain.com/js/ui-sound.js?v=20260722a")
        wa_html = get("https://wakeagain.com/")
        ok_rl = ("20260722-sound-v1" in rl_build) or ("playTone" in rl_js) or (
            "ui-sound.js" in rl_html
        )
        ok_wa = ("playTone" in wa_js) or ("CoreLabsSound" in wa_js) or (
            "ui-sound.js" in wa_html
        )
        print(
            "live",
            {
                "rl_build": rl_build.strip()[:70],
                "rl_js": "SOUND" if "playTone" in rl_js else ("HTML" if "<!DOCTYPE" in rl_js else "other"),
                "rl_html_script": "ui-sound.js" in rl_html,
                "wa_js": "SOUND" if ("playTone" in wa_js or "CoreLabsSound" in wa_js) else (
                    "ERR" if wa_js.startswith("ERR") else "no"
                ),
                "wa_html_script": "ui-sound.js" in wa_html,
            },
            flush=True,
        )
        if ok_rl and ok_wa:
            print("ALL LIVE", flush=True)
            return 0
        # fail fast if top deploy failed
        if d_rl and d_rl[0].get("status") == "FAILED":
            print("RoadLog FAILED", flush=True)
        if d_wa and d_wa[0].get("status") == "FAILED":
            print("WakeAgain FAILED", flush=True)
        time.sleep(15)
    print("TIMEOUT", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
