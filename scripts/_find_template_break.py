# -*- coding: utf-8 -*-
from pathlib import Path

s = Path("web/app.js").read_text(encoding="utf-8")
lines = s.splitlines()
in_t = False
start = None
esc = False
bs = "\\"

for i, line in enumerate(lines, 1):
    j = 0
    while j < len(line):
        c = line[j]
        if esc:
            esc = False
            j += 1
            continue
        if c == bs and in_t:
            esc = True
            j += 1
            continue
        if c == "`":
            if not in_t:
                in_t = True
                start = i
            else:
                # check if this is \`
                in_t = False
                if i > 3885 and i < 4250:
                    print(f"template close at line {i}: {line[:80]!r}")
                start = None
        j += 1

print("ends_in_template", in_t, "open_since", start)
if start:
    print("--- from open ---")
    for n in range(start, min(start + 30, len(lines) + 1)):
        print(f"{n}: {lines[n-1][:120]}")
    print("--- near openPrint ---")
    for n in range(4200, min(4230, len(lines) + 1)):
        print(f"{n}: {lines[n-1][:120]}")
