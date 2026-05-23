from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RateDetector:
    """Detects when tool call frequency exceeds a threshold within a time window."""

    max_calls: int = 10
    window_seconds: float = 60.0
    _timestamps: deque[float] = field(default_factory=deque, init=False)

    def record(self) -> bool:
        """Record a call. Returns True if rate is exceeded."""
        now = time.monotonic()
        self._timestamps.append(now)
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        return len(self._timestamps) > self.max_calls

    def reset(self) -> None:
        self._timestamps.clear()

    @property
    def current_rate(self) -> int:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
        return len(self._timestamps)


@dataclass
class BudgetDetector:
    """Tracks resource consumption against budgets."""

    max_tokens: int = 100_000
    max_tool_calls: int = 50
    max_wall_seconds: float = 300.0
    _tokens_used: int = field(default=0, init=False)
    _tool_calls: int = field(default=0, init=False)
    _start_time: float = field(default_factory=time.monotonic, init=False)

    def record_tokens(self, count: int) -> bool:
        """Record token usage. Returns True if budget exceeded."""
        self._tokens_used += count
        return self._tokens_used > self.max_tokens

    def record_tool_call(self) -> bool:
        """Record a tool call. Returns True if budget exceeded."""
        self._tool_calls += 1
        return self._tool_calls > self.max_tool_calls

    def is_time_exceeded(self) -> bool:
        return (time.monotonic() - self._start_time) > self.max_wall_seconds

    def is_any_exceeded(self) -> bool:
        return (
            self._tokens_used > self.max_tokens
            or self._tool_calls > self.max_tool_calls
            or self.is_time_exceeded()
        )

    def usage_summary(self) -> dict[str, Any]:
        elapsed = time.monotonic() - self._start_time
        return {
            "tokens": {"used": self._tokens_used, "max": self.max_tokens},
            "tool_calls": {"used": self._tool_calls, "max": self.max_tool_calls},
            "wall_seconds": {"used": round(elapsed, 2), "max": self.max_wall_seconds},
        }

    def reset(self) -> None:
        self._tokens_used = 0
        self._tool_calls = 0
        self._start_time = time.monotonic()


@dataclass
class PatternDetector:
    """Detects repeated identical tool calls (loop detection)."""

    max_repeats: int = 3
    window_size: int = 10
    _recent_calls: deque[str] = field(default_factory=deque, init=False)

    def record(self, call_signature: str) -> bool:
        """Record a call signature. Returns True if repetition pattern detected."""
        self._recent_calls.append(call_signature)
        if len(self._recent_calls) > self.window_size:
            self._recent_calls.popleft()

        if len(self._recent_calls) >= self.max_repeats:
            last_n = list(self._recent_calls)[-self.max_repeats:]
            if len(set(last_n)) == 1:
                return True
        return False

    def reset(self) -> None:
        self._recent_calls.clear()
