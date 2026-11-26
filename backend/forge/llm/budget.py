"""Budget enforcement and rate limiting, so unattended runs always end with a report."""

from __future__ import annotations

import threading
import time
from collections import deque

from forge.config import BudgetCfg
from forge.errors import BudgetExceeded


class Budget:
    def __init__(self, cfg: BudgetCfg, requests_per_minute: int = 0):
        self.cfg = cfg
        self.started_at = time.time()
        self.calls = 0
        self.tokens = 0
        self.cached_calls = 0
        self.rpm = requests_per_minute
        self._window: deque[float] = deque()
        self._lock = threading.Lock()

    def elapsed(self) -> float:
        return time.time() - self.started_at

    def check(self) -> None:
        if self.calls >= self.cfg.max_llm_calls:
            raise BudgetExceeded(f"LLM call budget reached ({self.calls}/{self.cfg.max_llm_calls})")
        if self.tokens >= self.cfg.max_tokens:
            raise BudgetExceeded(f"token budget reached ({self.tokens}/{self.cfg.max_tokens})")
        if self.elapsed() >= self.cfg.max_seconds:
            raise BudgetExceeded(f"time budget reached ({int(self.elapsed())}s/{self.cfg.max_seconds}s)")

    def charge_call(self) -> None:
        """Called before every real (non-cached) provider call."""
        with self._lock:
            self.check()
            self._throttle()
            self.calls += 1

    def add_tokens(self, n: int) -> None:
        with self._lock:
            self.tokens += max(0, n)

    def _throttle(self) -> None:
        if self.rpm <= 0:
            return
        now = time.time()
        while self._window and now - self._window[0] > 60:
            self._window.popleft()
        if len(self._window) >= self.rpm:
            time.sleep(max(0.0, 60 - (now - self._window[0])) + 0.1)
        self._window.append(time.time())

    def remaining_fraction(self) -> float:
        parts = [
            1 - self.calls / max(1, self.cfg.max_llm_calls),
            1 - self.tokens / max(1, self.cfg.max_tokens),
            1 - self.elapsed() / max(1, self.cfg.max_seconds),
        ]
        return max(0.0, min(parts))

    def summary(self) -> dict:
        return {"llm_calls": self.calls, "cached_calls": self.cached_calls, "tokens": self.tokens,
                "elapsed_s": round(self.elapsed(), 1), "limits": {
                    "max_llm_calls": self.cfg.max_llm_calls, "max_tokens": self.cfg.max_tokens,
                    "max_seconds": self.cfg.max_seconds}}
