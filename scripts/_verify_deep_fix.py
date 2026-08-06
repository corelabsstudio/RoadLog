from pathlib import Path
import re, sys
sys.stdout.reconfigure(encoding="utf-8")
css = Path(r"C:\Users\hysoo\projects\RoadLog\web\styles.css").read_text(encoding="utf-8")
for pat in ["#5eead4", "#67e8f9", "#22d3ee", "167, 139, 250", "14, 116, 144", "45, 212, 191"]:
    print("RL", pat, css.count(pat))
print("braces", css.count("{") - css.count("}"))
ih = Path(r"C:\Users\hysoo\projects\RoadLog\web\index.html").read_text(encoding="utf-8")
print("index cyan", "#5eead4" in ih)
m = re.search(r'name="rl-build"\s+content="([^"]+)"', ih)
print("build", m.group(1) if m else None)
uh = Path(r"C:\Users\hysoo\projects\RoadLog\web\update.html").read_text(encoding="utf-8")
print("update BUILD", re.search(r'BUILD = "([^"]+)"', uh).group(1))
print("build.json", Path(r"C:\Users\hysoo\projects\RoadLog\web\build.json").read_text(encoding="utf-8").strip())
