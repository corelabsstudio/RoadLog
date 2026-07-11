"""
간단한 인메모리 슬라이딩 윈도우 레이트리밋.
단일 프로세스(uvicorn workers=1) 기준. 다중 워커 시 워커별 독립 집계.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def allow(self, key: str, *, limit: int, window_sec: int) -> bool:
        """limit 회 / window_sec 초. 허용이면 True."""
        if limit <= 0 or window_sec <= 0:
            return True
        now = time.time()
        with self._lock:
            bucket = self._hits[key]
            cutoff = now - window_sec
            # in-place trim
            i = 0
            for t in bucket:
                if t >= cutoff:
                    break
                i += 1
            if i:
                del bucket[:i]
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def remaining(self, key: str, *, limit: int, window_sec: int) -> int:
        now = time.time()
        with self._lock:
            bucket = [t for t in self._hits.get(key, []) if now - t < window_sec]
            self._hits[key] = bucket
            return max(0, limit - len(bucket))


# 전역 싱글톤
limiter = RateLimiter()

# 정책 (정식 런칭 기본값)
AUTH_LIMIT = 20          # 로그인/가입: IP당 20회 / 10분
AUTH_WINDOW = 600
GENERATE_LIMIT = 30      # 생성: 계정/IP당 30회 / 10분
GENERATE_WINDOW = 600
REGISTER_LIMIT = 8       # 가입: IP당 8회 / 1시간
REGISTER_WINDOW = 3600
