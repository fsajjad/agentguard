from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


class BreakerState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitOpenError(Exception):
    def __init__(self, breaker_name: str) -> None:
        self.breaker_name = breaker_name
        super().__init__(f"Circuit breaker '{breaker_name}' is OPEN — calls blocked")


@dataclass
class AgentCircuitBreaker:
    """Circuit breaker with multi-signal failure detection for AI agents."""

    name: str
    failure_threshold: int = 5
    reset_timeout: float = 60.0
    half_open_probe_limit: int = 1

    _state: BreakerState = field(default=BreakerState.CLOSED, init=False, repr=False)
    _failure_count: int = field(default=0, init=False, repr=False)
    _last_failure_time: float = field(default=0.0, init=False, repr=False)
    _probe_count: int = field(default=0, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _on_state_change: Callable[[BreakerState, BreakerState], None] | None = field(
        default=None, init=True, repr=False
    )

    @property
    def state(self) -> BreakerState:
        with self._lock:
            return self._evaluate_state()

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def call(
        self,
        fn: Callable[..., Any],
        *args: Any,
        failure_predicate: Callable[[Any], bool] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Execute fn through the circuit breaker.

        Args:
            fn: The callable to execute.
            failure_predicate: Optional callable that receives the result
                and returns True if the result should count as a failure.
        """
        with self._lock:
            state = self._evaluate_state()

        match state:
            case BreakerState.OPEN:
                raise CircuitOpenError(self.name)
            case BreakerState.HALF_OPEN:
                with self._lock:
                    if self._probe_count >= self.half_open_probe_limit:
                        raise CircuitOpenError(self.name)
                    self._probe_count += 1

        try:
            result = fn(*args, **kwargs)
        except Exception:
            self._record_failure()
            raise

        if failure_predicate and failure_predicate(result):
            self._record_failure()
            raise CircuitOpenError(self.name)

        self._record_success()
        return result

    async def call_async(
        self,
        fn: Callable[..., Any],
        *args: Any,
        failure_predicate: Callable[[Any], bool] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Async version of call()."""
        with self._lock:
            state = self._evaluate_state()

        match state:
            case BreakerState.OPEN:
                raise CircuitOpenError(self.name)
            case BreakerState.HALF_OPEN:
                with self._lock:
                    if self._probe_count >= self.half_open_probe_limit:
                        raise CircuitOpenError(self.name)
                    self._probe_count += 1

        try:
            result = await fn(*args, **kwargs)
        except Exception:
            self._record_failure()
            raise

        if failure_predicate and failure_predicate(result):
            self._record_failure()
            raise CircuitOpenError(self.name)

        self._record_success()
        return result

    def trip(self) -> None:
        """Manually open the circuit breaker."""
        with self._lock:
            old = self._state
            self._state = BreakerState.OPEN
            self._last_failure_time = time.monotonic()
            if self._on_state_change and old != BreakerState.OPEN:
                self._on_state_change(old, BreakerState.OPEN)

    def reset(self) -> None:
        """Manually reset the circuit breaker to CLOSED."""
        with self._lock:
            old = self._state
            self._state = BreakerState.CLOSED
            self._failure_count = 0
            self._probe_count = 0
            if self._on_state_change and old != BreakerState.CLOSED:
                self._on_state_change(old, BreakerState.CLOSED)

    def _evaluate_state(self) -> BreakerState:
        if self._state == BreakerState.OPEN:
            if (time.monotonic() - self._last_failure_time) >= self.reset_timeout:
                old = self._state
                self._state = BreakerState.HALF_OPEN
                self._probe_count = 0
                if self._on_state_change:
                    self._on_state_change(old, BreakerState.HALF_OPEN)
        return self._state

    def _record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                old = self._state
                self._state = BreakerState.OPEN
                if self._on_state_change and old != BreakerState.OPEN:
                    self._on_state_change(old, BreakerState.OPEN)

    def _record_success(self) -> None:
        with self._lock:
            old = self._state
            self._failure_count = 0
            self._state = BreakerState.CLOSED
            self._probe_count = 0
            if self._on_state_change and old != BreakerState.CLOSED:
                self._on_state_change(old, BreakerState.CLOSED)
