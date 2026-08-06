# -*- coding: utf-8 -*-
import os, tempfile, sys, re, json
from pathlib import Path
td = Path(tempfile.mkdtemp(prefix="rlq2_"))
os.environ["DATA_DIR"] = str(td)
os.environ.setdefault("APP_ENV", "development")
sys.path.insert(0, ".")
import modules.config as c
c.DATA_DIR = td
from fastapi.testclient import TestClient
from server import app

cl = TestClient(app)
js = Path("web/app.js").read_text(encoding="utf-8")
html = Path("web/index.html").read_text(encoding="utf-8")
html_ids = set(re.findall(r'id=["\']([^"\']+)["\']', html))
gids = set(re.findall(r'getElementById\(["\']([^"\']+)["\']\)', js))
doll = set(re.findall(r'\$\(["\']#?([^"\'#\)]+)["\']\)', js))
created = set(re.findall(r'\.id\s*=\s*["\']([^"\']+)["\']', js))
dyn_skip = {
    "engineNotice", "resultWarnings", "freeModeBanner", "demo",
}
missing = []
for m in sorted((gids | doll) - html_ids - created):
    if m.startswith("stamp-") or m in dyn_skip:
        continue
    if m in ("body", "html", "document"):
        continue
    # class selectors false positives from $
    if m.startswith(".") or " " in m:
        continue
    missing.append(m)
print("maybe missing ids:", missing[:40], "count", len(missing))

# proper generate like suite
n = 999001
email = f"fix_{n}@roadlog.test"
pw = "TestPass9x"
cl.post("/api/auth/register", json={"email": email, "password": pw, "name": "Fix"})
tok = cl.post("/api/auth/login", json={"email": email, "password": pw}).json()["token"]
h = {"Authorization": f"Bearer {tok}"}
r = cl.put("/api/settings", headers=h, json={"settings": {"vehicle_number": "12가3456", "driver_name": "홍길동", "company_name": "코어랩스"}})
print("settings", r.status_code)
r = cl.post("/api/generate", headers=h, json={
    "raw_text": "오전 강남 고객 방문, 점심 김밥, 오후 판교 미팅 후 복귀",
    "vehicle_number": "12가3456",
    "odometer_start": 10000,
    "odometer_end": 10085,
    "lunch_restaurant": "김밥천국",
    "morning_places": "강남 고객사",
    "afternoon_places": "판교 미팅",
    "report_type": "driving",
    "settings": {"driver_name": "홍길동", "company_name": "코어랩스", "vehicle_number": "12가3456"},
})
body = r.json()
print("gen", r.status_code, "success", body.get("success"), "trips", len((body.get("log") or {}).get("trips") or []), "engine", body.get("engine"), "err", body.get("errors"))
log_data = body.get("log")
r = cl.post("/api/validate", headers=h, json={"log": log_data})
print("validate", r.status_code, r.text[:120])

# template files
man = cl.get("/assets/templates/manifest.json").json()
print("manifest keys", man.keys() if isinstance(man, dict) else type(man))
items = man.get("templates") or man.get("files") or man.get("items") or []
if isinstance(man, list):
    items = man
for t in items:
    if isinstance(t, str):
        path = t
    else:
        path = t.get("file") or t.get("path") or t.get("url") or t.get("href") or ""
    if not path:
        print(" item", t)
        continue
    if not path.startswith("/"):
        path = "/assets/templates/" + path.lstrip("./")
    rr = cl.get(path)
    print(" tpl", path, rr.status_code, len(rr.content))

# resources pack
for p in ["/resources/roadlog-driving-log-templates.xlsx", "/resources/%EB%A1%9C%EB%93%9C%EB%A1%9C%EA%B7%B8_%EB%AC%B4%EB%A3%8C_%EC%9A%B4%ED%96%89%EC%9D%BC%EC%A7%80_%EC%84%9C%EC%8B%9D%ED%8C%A9.xlsx"]:
    rr = cl.get(p)
    print("res", p, rr.status_code, len(rr.content))
