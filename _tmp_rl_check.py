# -*- coding: utf-8 -*-
from pathlib import Path
import re, json
idx = Path("web/index.html").read_text(encoding="utf-8")
vers = {}
m = re.search(r'rl-build" content="([^"]+)"', idx)
vers["rl-build"] = m.group(1) if m else None
m = re.search(r'var BUILD = "([^"]+)"', idx)
vers["BUILD"] = m.group(1) if m else None
m = re.search(r"styles\.css\?v=([^\"&]+)", idx)
vers["css"] = m.group(1) if m else None
m = re.search(r"app\.js\?v=([^\"&]+)", idx)
vers["js"] = m.group(1) if m else None
sw = re.search(r'const VERSION = "([^"]+)"', Path("web/sw.js").read_text(encoding="utf-8"))
vers["sw"] = sw.group(1) if sw else None
vers["bj"] = json.loads(Path("web/build.json").read_text(encoding="utf-8")).get("build")
print("versions", vers)
print("unique", set(vers.values()))
print("id=demo", 'id="demo"' in idx)
print("id=features", 'id="features"' in idx)
# features target
for fid in ["features", "demo", "view-home", "view-create", "view-pricing", "view-pro-claim", "appHome", "guestHome", "resultBox", "btnGenerate"]:
    print(fid, f'id="{fid}"' in idx)
