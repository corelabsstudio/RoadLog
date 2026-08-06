# -*- coding: utf-8 -*-
import json
import re
import subprocess
import urllib.request


def gh(path: str):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        print("gh err", path, (r.stderr or r.stdout)[:250])
        return None
    return json.loads(r.stdout) if r.stdout.strip() else None


def get(u: str):
    try:
        req = urllib.request.Request(
            u, headers={"User-Agent": "x", "Cache-Control": "no-cache"}
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, str(e)


print("=== GitHub latest deploys ===")
for repo in ["corelabsstudio/RoadLog", "corelabsstudio/WakeAgain"]:
    deps = gh(f"repos/{repo}/deployments?per_page=4") or []
    for d in deps:
        st = gh(f"repos/{repo}/deployments/{d['id']}/statuses") or []
        state = st[0]["state"] if st else "no-status"
        print(repo, d["sha"][:7], d["environment"], state, d["created_at"])

print("\n=== Live ===")
checks = [
    ("RL build", "https://roadlog.co.kr/build.json"),
    ("RL js", "https://roadlog.co.kr/ui-sound.js"),
    ("RL html", "https://roadlog.co.kr/"),
    ("WA js", "https://wakeagain.com/js/ui-sound.js?v=20260722a"),
    ("WA html", "https://wakeagain.com/"),
    ("WA railway js", "https://wakeagain-production.up.railway.app/js/ui-sound.js?v=20260722a"),
]
for name, u in checks:
    c, b = get(u)
    if "build" in name:
        print(name, c, b.strip()[:120])
    elif "js" in name:
        if "CoreLabsSound" in b or "playTone" in b:
            tag = "HAS_SOUND"
        elif "<!DOCTYPE" in b:
            tag = "HTML_FALLBACK"
        else:
            tag = "OTHER"
        print(name, c, tag, len(b))
    else:
        has = "ui-sound.js" in b
        m = re.search(r'rl-build" content="([^"]+)', b)
        print(name, c, "HAS_SCRIPT" if has else "NO_SCRIPT", "build", m.group(1) if m else "-")
