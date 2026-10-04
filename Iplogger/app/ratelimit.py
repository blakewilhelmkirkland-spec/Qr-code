"""Fixed-window per-IP rate limiter backed by in-process dict.

For single-instance deployments this is enough; swap for Redis if scaled out.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class _Bucket:
    window_start: int
    count: int


class RateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self.limit = limit_per_minute
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = int(time.time())
        window = now - (now % 60)
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or bucket.window_start != window:
                self._buckets[key] = _Bucket(window_start=window, count=1)
                self._prune(now)
                return True, 0
            if bucket.count >= self.limit:
                retry_after = 60 - (now - window)
                return False, max(1, retry_after)
            bucket.count += 1
            return True, 0

    def _prune(self, now: int) -> None:
        # Opportunistic cleanup of stale windows (keep dict bounded).
        if len(self._buckets) < 10_000:
            return
        cutoff = now - 120
        stale = [k for k, b in self._buckets.items() if b.window_start < cutoff]
        for k in stale:
            self._buckets.pop(k, None)