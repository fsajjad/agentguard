from __future__ import annotations

import threading
from typing import Any

from agentguard.circuit.breaker import AgentCircuitBreaker, BreakerState


class BreakerRegistry:
    """Registry of per-tool circuit breakers with emergency stop."""

    def __init__(
        self,
        default_failure_threshold: int = 5,
        default_reset_timeout: float = 60.0,
    ) -> None:
        self._breakers: dict[str, AgentCircuitBreaker] = {}
        self._lock = threading.Lock()
        self._default_failure_threshold = default_failure_threshold
        self._default_reset_timeout = default_reset_timeout

    def get(self, tool_name: str) -> AgentCircuitBreaker:
        with self._lock:
            if tool_name not in self._breakers:
                self._breakers[tool_name] = AgentCircuitBreaker(
                    name=tool_name,
                    failure_threshold=self._default_failure_threshold,
                    reset_timeout=self._default_reset_timeout,
                )
            return self._breakers[tool_name]

    def register(self, breaker: AgentCircuitBreaker) -> None:
        with self._lock:
            self._breakers[breaker.name] = breaker

    def emergency_stop(self) -> None:
        """Open ALL circuit breakers immediately."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.trip()

    def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED."""
        with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()

    def status(self) -> dict[str, dict[str, Any]]:
        """Return health status of all registered breakers."""
        with self._lock:
            return {
                name: {
                    "state": breaker.state.name,
                    "failure_count": breaker.failure_count,
                }
                for name, breaker in self._breakers.items()
            }

    @property
    def breaker_names(self) -> list[str]:
        with self._lock:
            return list(self._breakers.keys())
