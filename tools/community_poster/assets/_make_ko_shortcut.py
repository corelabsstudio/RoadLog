"""바탕화면 바로가기 생성 · 리치킷."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BAT = ROOT / "ReachKit.bat"
ICO = ROOT / "assets" / "icon.ico"
DESKTOP = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
LNK = DESKTOP / "리치킷.lnk"


def main() -> int:
    if not BAT.is_file():
        print("없음", BAT)
        return 1

    def esc(p: Path) -> str:
        return str(p).replace("\\", "\\\\")

    vbs_path = ROOT / "assets" / "_mk_shortcut.vbs"
    # VBS 파일은 CP949로 저장해야 한글 바로가기 이름이 깨지지 않음
    lines = [
        'Set sh = CreateObject("WScript.Shell")',
        f'Set sc = sh.CreateShortcut("{esc(LNK)}")',
        f'sc.TargetPath = "{esc(BAT)}"',
        f'sc.WorkingDirectory = "{esc(ROOT)}"',
        'sc.Description = "리치킷 — 사이트 분석 · 홍보 문구 · 채널 루틴"',
        f'sc.IconLocation = "{esc(ICO)},0"',
        "sc.Save",
        "",
    ]
    vbs = "\r\n".join(lines)
    try:
        vbs_path.write_text(vbs, encoding="cp949")
    except Exception:
        vbs_path.write_text(vbs, encoding="utf-8")
    r = subprocess.run(["cscript", "//nologo", str(vbs_path)], capture_output=True)
    print("cscript", r.returncode)
    print("exists", LNK.exists(), LNK)
    # 이전 영문 바로가기 정리
    for old in (
        DESKTOP / "ReachKit.lnk",
        DESKTOP / "PromoRoutine.lnk",
        DESKTOP / "홍보루틴 PromoRoutine.lnk",
    ):
        try:
            if old.is_file() and old.resolve() != LNK.resolve():
                old.unlink()
                print("removed old", old.name)
        except Exception as e:
            print("skip remove", old, e)
    return 0 if LNK.exists() else 1


if __name__ == "__main__":
    sys.exit(main())
