from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from agentguard.monitor.detectors import BudgetDetector, RateDetector, PatternDetector


class SessionState(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    HALTED = "halted"


@dataclass
class AgentSession:
    """Tracks per-conversation state with safety invariants."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    max_tokens: int = 100_000
    max_tool_calls: int = 50
    max_wall_seconds: float = 300.0
    max_call_rate: int = 10
    rate_window: float = 60.0

    _state: SessionState = field(default=SessionState.ACTIVE, init=False)
    _start_time: float = field(default_factory=time.monotonic, init=False)
    _action_count: int = field(default=0, init=False)
    _violations: list[dict[str, Any]] = field(default_factory=list, init=False)
    _trust_score: float = field(default=1.0, init=False)

    budget: BudgetDetector = field(init=False)
    rate: RateDetector = field(init=False)
    pattern: PatternDetector = field(init=False)

    def __post_init__(self) -> None:
        self.budget = BudgetDetector(
            max_tokens=self.max_tokens,
            max_tool_calls=self.max_tool_calls,
            max_wall_seconds=self.max_wall_seconds,
        )
        self.rate = RateDetector(
            max_calls=self.max_call_rate,
            window_seconds=self.rate_window,
        )
        self.pattern = PatternDetector()

    @property
    def state(self) -> SessionState:
        return self._state

    @property
    def trust_score(self) -> float:
        return self._trust_score

    @property
    def action_count(self) -> int:
        return self._action_count

    @property
    def violations(self) -> list[dict[str, Any]]:
        return list(self._violations)

    def record_action(self, tool_name: str, params_signature: str) -> None:
        self._action_count += 1
        self.budget.record_tool_call()
        self.rate.record()
        self.pattern.record(params_signature)

    def record_tokens(self, count: int) -> None:
        self.budget.record_tokens(count)

    def record_violation(self, rule: str, details: dict[str, Any] | None = None) -> None:
        self._violations.append({
            "rule": rule,
            "details": details or {},
            "timestamp": time.time(),
        })
        self._trust_score = max(0.0, self._trust_score - 0.2)

    def halt(self, reason: str) -> None:
        self._state = SessionState.HALTED
        self._violations.append({
            "rule": "session_halted",
            "details": {"reason": reason},
            "timestamp": time.time(),
        })

    def complete(self) -> None:
        self._state = SessionState.COMPLETED

    def is_active(self) -> bool:
        return self._state == SessionState.ACTIVE

    def elapsed_seconds(self) -> float:
        return time.monotonic() - self._start_time

    def summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self._state.value,
            "action_count": self._action_count,
            "trust_score": self._trust_score,
            "violations": len(self._violations),
            "elapsed_seconds": round(self.elapsed_seconds(), 2),
            "budget": self.budget.usage_summary(),
        }
