# -*- coding: utf-8 -*-
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(r"C:\Users\hysoo\projects\RoadLog\scripts\_qa_zero_results.json", encoding="utf-8"))
print("rows", len(d["rows"]), "issues", d["issueCount"])
for i in d["issues"]:
    print("ISSUE", i["sev"], i["where"], str(i["msg"])[:200])

flagged = 0
for r in d["rows"]:
    info = r.get("info") or {}
    flags = []
    if r.get("error"):
        flags.append("ERR:" + str(r["error"])[:80])
    if r.get("pageErrs"):
        flags.append("pageErr")
    if r.get("consoleErrs"):
        flags.append("console:" + str(r["consoleErrs"][:2]))
    if r.get("failed"):
        flags.append("net:" + str(r["failed"][:2]))
    if info.get("overflowX"):
        flags.append("ovX")
    if info.get("brokenImgs"):
        flags.append("img")
    if info.get("clippedText"):
        flags.append("clip:" + str(info["clippedText"][:2]))
    if info.get("offenders"):
        # only report if also overflowX or many offenders
        if info.get("overflowX") or len(info["offenders"]) > 3:
            flags.append("off:" + str(info["offenders"][:2]))
    if flags:
        flagged += 1
        print(
            "FLAG",
            r["label"],
            r["vp"],
            flags,
            "active=",
            info.get("activeView"),
            "fab=",
            info.get("fabVis"),
            "guest=",
            info.get("guest"),
            "appTop=",
            info.get("appTop"),
        )

print("flagged_rows", flagged)

# product summary
keys = [
    ("RL-home", "mobile"),
    ("RL-create", "mobile"),
    ("RL-pricing", "mobile"),
    ("WA-app", "mobile"),
    ("WA-home", "mobile"),
    ("WA-guide", "mobile"),
]
for lab, vp in keys:
    matches = [r for r in d["rows"] if r["label"] == lab and r["vp"] == vp]
    if not matches:
        # also desk
        matches = [r for r in d["rows"] if r["label"] == lab]
    if not matches:
        print("missing", lab)
        continue
    r = matches[-1]
    i = r.get("info") or {}
    print(
        "OK-sample",
        lab,
        r["vp"],
        "ov",
        i.get("overflowX"),
        "fab",
        i.get("fabVis"),
        "guest",
        i.get("guest"),
        "active",
        i.get("activeView"),
        "appTop",
        i.get("appTop"),
        "title",
        (i.get("title") or "")[:45],
    )
