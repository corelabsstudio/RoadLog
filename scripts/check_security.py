"""
로드로그 배포 보안 점검 스크립트.

사용:
  python scripts/check_security.py
  python scripts/check_security.py --strict   # warn 도 실패로 처리

exit 0 = PASS, exit 1 = FAIL
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="RoadLog deploy security check")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat warnings as failures",
    )
    args = parser.parse_args()

    from modules.config import (
        ALLOW_DEMO_BILLING_UPGRADE,
        APP_ENV,
        is_production,
        security_issues,
    )

    print("RoadLog security check")
    print(f"  APP_ENV={APP_ENV}  production={is_production()}")
    print(f"  ALLOW_DEMO_BILLING_UPGRADE={ALLOW_DEMO_BILLING_UPGRADE}")
    print()

    issues = security_issues()
    # .env tracked by git?
    try:
        r = subprocess.run(
            ["git", "ls-files", ".env"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if r.stdout.strip():
            issues.append(
                {
                    "level": "critical",
                    "code": "env_tracked",
                    "message": ".env 가 git 에 추적되고 있습니다. 즉시 git rm --cached .env 하세요.",
                }
            )
    except Exception:
        pass

    # conflict markers in source (split tokens so this file itself is not a hit)
    mark_head = "<" * 7
    mark_tail = ">" * 7
    for p in ROOT.rglob("*"):
        if p.suffix not in {".py", ".js", ".html", ".css", ".gitignore"}:
            continue
        if any(x in p.parts for x in (".venv", ".git", "__pycache__", "node_modules")):
            continue
        if p.name == "check_security.py":
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if mark_head in t or mark_tail in t:
            issues.append(
                {
                    "level": "critical",
                    "code": "merge_conflict",
                    "message": f"머지 충돌 마커: {p.relative_to(ROOT)}",
                }
            )

    by_level = {"critical": [], "warn": [], "info": []}
    for i in issues:
        by_level.setdefault(i["level"], []).append(i)

    for level in ("critical", "warn", "info"):
        for i in by_level.get(level, []):
            print(f"[{level.upper():8}] {i['code']}: {i['message']}")

    print()
    n_c = len(by_level.get("critical", []))
    n_w = len(by_level.get("warn", []))
    n_i = len(by_level.get("info", []))
    print(f"summary: critical={n_c}  warn={n_w}  info={n_i}")

    fail = n_c > 0 or (args.strict and n_w > 0)
    if fail:
        print("RESULT: FAIL")
        print("See docs/ops/DEPLOY_SECURITY_CHECKLIST.md")
        return 1

    print("RESULT: PASS")
    if n_w:
        print("(warnings present — review before public launch)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
