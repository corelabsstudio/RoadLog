# -*- coding: utf-8 -*-
from pathlib import Path

s = Path("web/app.js").read_text(encoding="utf-8")
paren = brace = bracket = 0
in_s = in_d = in_t = False
esc = False
neg_at = None
for i, c in enumerate(s):
    if esc:
        esc = False
        continue
    if c == "\\" and (in_s or in_d or in_t):
        esc = True
        continue
    if in_t:
        if c == "`":
            in_t = False
        continue
    if in_s:
        if c == "'":
            in_s = False
        continue
    if in_d:
        if c == '"':
            in_d = False
        continue
    if c == "`":
        in_t = True
        continue
    if c == "'":
        in_s = True
        continue
    if c == '"':
        in_d = True
        continue
    if c == "(":
        paren += 1
    elif c == ")":
        paren -= 1
    elif c == "{":
        brace += 1
    elif c == "}":
        brace -= 1
    elif c == "[":
        bracket += 1
    elif c == "]":
        bracket -= 1
    if (paren < 0 or brace < 0 or bracket < 0) and neg_at is None:
        neg_at = (i, s[:i].count("\n") + 1, paren, brace, bracket)

print("final", {"paren": paren, "brace": brace, "bracket": bracket, "in_s": in_s, "in_d": in_d, "in_t": in_t})
print("first_neg", neg_at)

# find template strings that might be unclosed - report open template at end
# also locate line around extra close
if brace != 0 or paren != 0:
    # print last 5 function/structure markers
    lines = s.splitlines()
    for n in range(max(1, len(lines) - 40), len(lines) + 1):
        print(f"{n}: {lines[n-1][:120]}")
