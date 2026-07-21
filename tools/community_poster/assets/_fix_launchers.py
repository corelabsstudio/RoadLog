from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REDIR = b'@echo off\r\ncd /d "%~dp0"\r\ncall "%~dp0ReachKit.bat"\r\n'

for p in ROOT.glob("*.bat"):
    if p.name == "ReachKit.bat":
        continue
    p.write_bytes(REDIR)
    print("redirect", p.name)
print("done")
