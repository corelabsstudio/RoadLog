# -*- coding: utf-8 -*-
import json
import subprocess
import time
import urllib.request


def gh_json(path: str):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        print("gh err", (r.stderr or r.stdout)[:300])
        return None
    if not r.stdout.strip():
        return None
    return json.loads(r.stdout)


def head_ok(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "CoreLabsDeploy/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read(4000).decode("utf-8", errors="replace")
            return res.status, body
    except Exception as e:
        return 0, str(e)


def main() -> None:
    targets = [
        ("corelabsstudio/RoadLog", 5543200953),
        ("corelabsstudio/WakeAgain", 5543201305),
    ]
    for i in range(20):
        print(f"--- poll {i}")
        states = []
        for repo, dep_id in targets:
            st = gh_json(f"repos/{repo}/deployments/{dep_id}/statuses") or []
            if not st:
                print(repo, "no status yet")
                states.append("pending")
            else:
                s = st[0]
                print(repo, s.get("state"), s.get("description"), s.get("created_at"))
                states.append(s.get("state") or "unknown")
        # live probe
        for label, url in [
            ("RL ui-sound", "https://roadlog.co.kr/ui-sound.js?v=20260722-sound-v1"),
            ("RL index", "https://roadlog.co.kr/"),
            ("WA ui-sound", "https://web-production-8ee81.up.railway.app/js/ui-sound.js?v=20260722a"),
            ("WA index", "https://web-production-8ee81.up.railway.app/"),
        ]:
            code, body = head_ok(url)
            has = "CoreLabsSound" in body or "ui-sound" in body or "playTone" in body
            print(f"  live {label}: HTTP {code} sound_marker={has} len={len(body)}")

        if all(s == "success" for s in states):
            print("ALL SUCCESS")
            break
        if any(s in ("failure", "error") for s in states):
            print("DEPLOY FAILED")
            break
        time.sleep(15)


if __name__ == "__main__":
    main()
