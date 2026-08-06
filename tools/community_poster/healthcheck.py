"""리치킷 실행 환경 점검 — 설치/이전 후 바로 확인."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent


@dataclass
class CheckItem:
    name: str
    ok: bool
    detail: str
    fix: str = ""


@dataclass
class HealthReport:
    items: list[CheckItem] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(i.ok for i in self.items if i.name != "Chromium (선택)")

    def lines(self) -> list[str]:
        out = []
        for i in self.items:
            mark = "OK" if i.ok else "FAIL"
            out.append(f"[{mark}] {i.name}: {i.detail}")
            if not i.ok and i.fix:
                out.append(f"      → {i.fix}")
        return out

    def text(self) -> str:
        head = "리치킷 환경 점검\n" + ("전체 통과" if self.ok else "일부 보완 필요")
        return head + "\n\n" + "\n".join(self.lines())

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "items": [
                {"name": i.name, "ok": i.ok, "detail": i.detail, "fix": i.fix}
                for i in self.items
            ],
        }


def _has_mod(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def run_healthcheck() -> HealthReport:
    r = HealthReport()

    r.items.append(
        CheckItem(
            "Python",
            sys.version_info >= (3, 10),
            f"{sys.version.split()[0]} ({sys.executable})",
            "Python 3.10 이상을 설치하세요.",
        )
    )

    for mod, fix in (
        ("tkinter", "Python 설치 시 tcl/tk 포함 버전을 쓰세요."),
        ("PIL", "pip install Pillow"),
        ("playwright", "pip install playwright"),
    ):
        ok = _has_mod(mod)
        r.items.append(
            CheckItem(
                f"패키지 {mod}",
                ok,
                "설치됨" if ok else "없음",
                fix if not ok else "",
            )
        )

    # Chromium for playwright (best-effort)
    chromium_ok = False
    chromium_detail = "확인 불가"
    if _has_mod("playwright"):
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                path = p.chromium.executable_path
                chromium_ok = bool(path and Path(path).exists())
                chromium_detail = path if chromium_ok else "실행 파일 없음"
        except Exception as e:
            chromium_detail = str(e)[:120]
    r.items.append(
        CheckItem(
            "Chromium (선택)",
            chromium_ok,
            chromium_detail,
            "playwright install chromium" if not chromium_ok else "",
        )
    )

    data = ROOT / "data"
    try:
        data.mkdir(parents=True, exist_ok=True)
        probe = data / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        write_ok = True
        write_detail = str(data)
    except Exception as e:
        write_ok = False
        write_detail = str(e)[:120]
    r.items.append(
        CheckItem(
            "데이터 폴더 쓰기",
            write_ok,
            write_detail,
            "폴더 권한을 확인하거나 다른 경로에 복사하세요.",
        )
    )

    icon = ROOT / "assets" / "icon.ico"
    r.items.append(
        CheckItem(
            "아이콘 에셋",
            icon.is_file(),
            str(icon) if icon.is_file() else "없음",
            "assets/icon.ico 를 포함해 배포하세요.",
        )
    )

    r.items.append(
        CheckItem(
            "필수 모듈 파일",
            all(
                (ROOT / n).is_file()
                for n in (
                    "app.py",
                    "phrase_gen.py",
                    "site_analyzer.py",
                    "poster.py",
                    "guardrails.py",
                    "product_config.py",
                )
            ),
            str(ROOT),
            "리치킷 폴더 전체가 복사됐는지 확인하세요.",
        )
    )

    return r


if __name__ == "__main__":
    print(run_healthcheck().text())
