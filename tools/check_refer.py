# -*- coding: utf-8 -*-
"""친구 추천 등불이 실제로 지급되는지 검사한다.

FAQ·상품 안내에 「친구를 데려오면 두 분 모두 30개씩」이라고 적어 두었다.
그건 손님과의 약속이라 코드가 바뀌면 여기서 걸려야 한다.

  DATA_DIR=<빈 폴더> python tools/check_refer.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from modules import lamps as L

A, B, C = "inviter@test.kr", "friend@test.kr", "other@test.kr"

r1 = L.welcome(A)
code = L.refer_code(A)
r2 = L.welcome(B, code)
again = L.claim_refer(B, code)      # 두 번째는 못 받는다
myself = L.claim_refer(A, code)     # 내 코드로 나는 못 받는다
bogus = L.claim_refer(C, "deadbeef")
st = L.refer_stats(A)

W, R = L.WELCOME_LAMPS, L.REFER_LAMPS
rows = [
    ("데려온 분 가입 선물", r1["given"], W),
    ("따라온 분 받은 등불", r2["given"], W + R),
    ("따라온 분 추천 보너스", r2["referred"], R),
    ("데려온 분 잔액", L.balance(A), W + R),
    ("추천 인원", st["count"], 1),
    ("두 번째 시도", again["given"], 0),
    ("자기 코드 시도", myself["given"], 0),
    ("없는 코드", bogus["given"], 0),
]
bad = 0
for name, got, want in rows:
    ok = got == want
    bad += not ok
    print(f"{'OK ' if ok else '🛑 '}{name:<20} {got}  (기대 {want})")

print("\n" + ("전부 통과" if not bad else f"어긋난 곳 {bad}개"))
sys.exit(1 if bad else 0)
