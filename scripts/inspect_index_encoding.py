import re
import subprocess

for c in ["bb0e894", "bdea9a8", "f401c76", "94e35af", "2488023", "636a353", "HEAD"]:
    t = subprocess.check_output(["git", "show", f"{c}:web/index.html"])
    u = t.decode("utf-8")
    print("===", c, "len", len(t))
    m = re.search(r'class="brand-name">([^<]+)', u)
    print(" brand:", m.group(1) if m else None)
    m2 = re.search(r'id="view-admin"[\s\S]{0,500}<h2>([^<]+)', u)
    print(" admin h2:", m2.group(1) if m2 else None)
    print(" has 관리자:", "관리자" in u)
    print(" has 로드로그:", "로드로그" in u)
    print(" has mojibake 愿:", "愿" in u)
    # count replacement chars
    print(" replacement char count:", u.count("\ufffd"))
