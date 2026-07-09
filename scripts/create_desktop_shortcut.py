"""바탕화면에 로드로그 바로가기 생성 (PWA 앱 아이콘)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAUNCHER = ROOT / "scripts" / "launch_roadlog.vbs"
ICO = ROOT / "web" / "icons" / "roadlog.ico"


def desktop_dir() -> Path:
    home = Path(os.environ.get("USERPROFILE", str(Path.home())))
    for c in (
        home / "Desktop",
        home / "OneDrive" / "Desktop",
        home / "OneDrive" / "바탕 화면",
    ):
        if c.is_dir():
            return c
    return home / "Desktop"


def esc_vbs(p: Path | str) -> str:
    return str(p).replace("\\", "\\\\").replace('"', '""')


def main() -> int:
    if not LAUNCHER.is_file():
        print("launcher missing:", LAUNCHER, file=sys.stderr)
        return 1
    if not ICO.is_file():
        print("icon missing:", ICO, file=sys.stderr)
        return 1

    desk = desktop_dir()
    lnk = desk / "로드로그.lnk"
    tmp = ROOT / "scripts" / "_mk_shortcut_tmp.vbs"

    # 깨진 이름 포함, launch_roadlog 를 가리키는 기존 lnk 정리
    for p in desk.glob("*.lnk"):
        try:
            raw = p.read_bytes()
            if b"launch_roadlog" in raw and p.resolve() != lnk.resolve():
                p.unlink(missing_ok=True)
        except Exception:
            pass

    tmp.write_text(
        "\r\n".join(
            [
                'Set sh = CreateObject("WScript.Shell")',
                f'Set sc = sh.CreateShortcut("{esc_vbs(lnk)}")',
                'sc.TargetPath = "wscript.exe"',
                f'sc.Arguments = Chr(34) & "{esc_vbs(LAUNCHER)}" & Chr(34)',
                f'sc.WorkingDirectory = "{esc_vbs(ROOT)}"',
                "sc.WindowStyle = 7",
                'sc.Description = "RoadLog by CoreLabs"',
                f'sc.IconLocation = "{esc_vbs(ICO)},0"',
                "sc.Save",
            ]
        ),
        encoding="utf-8",
        newline="\r\n",
    )
    # VBS is often read as system ANSI; write UTF-16 LE with BOM for Korean path reliability
    content = tmp.read_text(encoding="utf-8")
    tmp.write_bytes(content.encode("utf-16"))

    r = subprocess.run(["wscript.exe", str(tmp)], capture_output=True)
    tmp.unlink(missing_ok=True)
    if r.returncode != 0:
        print("wscript failed", r.returncode, r.stderr, file=sys.stderr)
        return 1
    if not lnk.exists():
        print("shortcut not created:", lnk, file=sys.stderr)
        return 1
    print("OK", lnk)
    print("icon", ICO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
