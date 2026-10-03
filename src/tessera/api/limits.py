"""Spend control for a public inference endpoint.

A demo URL is a public inference endpoint, and it must survive until judging
closes on 2026-12-15. One crawler in November would otherwise drain the
credits and leave a dead demo for the judges. Both limits fail toward the
seeded demo, never toward an error page.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Callable

DAY = 86_400


class RateLimiter:
    """Sliding-window limit per caller, in memory.

    In memory is enough: the API runs as one process, and a restart resetting
    the windows costs at most one extra burst. Refused calls are not recorded,
    so hammering a closed door does not keep it closed.
    """

    def __init__(self, max_calls: int, per_seconds: float,
                 clock: Callable[[], float] = time.monotonic):
        self.max_calls = max_calls
        self.per_seconds = per_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.per_seconds:
                hits.popleft()
            if len(hits) >= self.max_calls:
                return False
            hits.append(now)
            return True


class SpendCeiling:
    """A global daily budget, read from the same telemetry the ablations use.

    The router already records the cost of every model call, so the ceiling is
    measured spend rather than an estimate - and it cannot drift from the
    number the README reports.
    """

    def __init__(self, spent_since: Callable[[float], float], usd_per_day: float,
                 clock: Callable[[], float] = time.time):
        self._spent_since = spent_since
        self.usd_per_day = usd_per_day
        self._clock = clock

    def exceeded(self) -> bool:
        now = self._clock()
        midnight_utc = now - (now % DAY)
        return self._spent_since(midnight_utc) >= self.usd_per_day
