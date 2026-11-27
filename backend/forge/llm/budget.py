"""Budget enforcement and rate limiting, so unattended runs always end with a report.

A share of the budget (RESERVE) is held back for the last stages (holdout test + report). Normal stages can only
spend up to `limit - reserve`; the pipeline calls `release_reserve()` before the final stages, so a run that used
up its working budget still finishes in one go instead of stopping half-way.
"""

from __future__ import annotations

import threading
import time
from collections import deque

from forge.config import BudgetCfg
from forge.errors import BudgetExceeded

RESERVE = 0.2

# A chat answer is not a factory run: each question gets this small, fixed allowance (about 0.01 USD on gpt-4o-mini).
CHAT_BUDGET = BudgetCfg(max_llm_calls=12, max_tokens=60000, max_seconds=180)


class Budget:
    def __init__(self, cfg: BudgetCfg, requests_per_minute: int = 0):
        self.cfg = cfg
        self.started_at = time.time()
        self.calls = 0
        self.tokens = 0
        self.cached_calls = 0
        self.rpm = requests_per_minute
        self.reserve_released = False
        self._window: deque[float] = deque()
        self._lock = threading.Lock()

    def elapsed(self) -> float:
        return time.time() - self.started_at

    # limits that apply right now (with or without the reserve)
    def _limits(self) -> tuple[float, float, float]:
        f = 1.0 if self.reserve_released else 1.0 - RESERVE
        return self.cfg.max_llm_calls * f, self.cfg.max_tokens * f, self.cfg.max_seconds * f

    def release_reserve(self) -> None:
        self.reserve_released = True

    def check(self) -> None:
        max_calls, max_tokens, max_seconds = self._limits()
        if self.calls >= max_calls:
            raise BudgetExceeded(f"LLM call budget reached ({self.calls}/{int(max_calls)})")
        if self.tokens >= max_tokens:
            raise BudgetExceeded(f"token budget reached ({self.tokens}/{int(max_tokens)})")
        if self.elapsed() >= max_seconds:
            raise BudgetExceeded(f"time budget reached ({int(self.elapsed())}s/{int(max_seconds)}s)")

    def can_afford(self, tokens: float, calls: float, seconds: float = 0.0) -> bool:
        """Would a step of this estimated size fit in the working budget (reserve excluded)?"""
        max_calls, max_tokens, max_seconds = self._limits()
        return (self.tokens + tokens <= max_tokens and self.calls + calls <= max_calls
                and self.elapsed() + seconds <= max_seconds)

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
        max_calls, max_tokens, max_seconds = self._limits()
        parts = [1 - self.calls / max(1, max_calls), 1 - self.tokens / max(1, max_tokens),
                 1 - self.elapsed() / max(1, max_seconds)]
        return max(0.0, min(parts))

    def snapshot(self) -> dict:
        return {"tokens": self.tokens, "calls": self.calls, "t": self.elapsed()}

    def reset(self, cfg: BudgetCfg | None = None) -> None:
        """Start a fresh allowance. Used for every chat answer, so a long-running server does not add up
        the calls, tokens and time of all earlier questions (that exhausted the budget after ~32 minutes)."""
        with self._lock:
            if cfg is not None:
                self.cfg = cfg
            self.calls = 0
            self.tokens = 0
            self.started_at = time.time()
            self.reserve_released = True

    def summary(self) -> dict:
        return {"llm_calls": self.calls, "cached_calls": self.cached_calls, "tokens": self.tokens,
                "elapsed_s": round(self.elapsed(), 1), "reserve_released": self.reserve_released, "limits": {
                    "max_llm_calls": self.cfg.max_llm_calls, "max_tokens": self.cfg.max_tokens,
                    "max_seconds": self.cfg.max_seconds}}

    # a resumed run starts a new process: restore what the earlier attempt already spent
    def restore(self, tokens: int, calls: int) -> None:
        self.tokens += max(0, tokens)
        self.calls += max(0, calls)
