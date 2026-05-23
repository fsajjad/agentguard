import time

import pytest

from agentguard.circuit.breaker import AgentCircuitBreaker, BreakerState, CircuitOpenError
from agentguard.circuit.registry import BreakerRegistry


class TestAgentCircuitBreaker:
    def test_closed_by_default(self):
        cb = AgentCircuitBreaker(name="test")
        assert cb.state == BreakerState.CLOSED

    def test_successful_calls_stay_closed(self):
        cb = AgentCircuitBreaker(name="test", failure_threshold=3)
        result = cb.call(lambda: "ok")
        assert result == "ok"
        assert cb.state == BreakerState.CLOSED

    def test_opens_after_threshold_failures(self):
        cb = AgentCircuitBreaker(name="test", failure_threshold=3)

        def failing():
            raise ValueError("boom")

        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(failing)

        assert cb.state == BreakerState.OPEN

    def test_open_circuit_blocks_calls(self):
        cb = AgentCircuitBreaker(name="test", failure_threshold=1)

        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError("x")))

        with pytest.raises(CircuitOpenError):
            cb.call(lambda: "should not reach")

    def test_half_open_after_timeout(self):
        cb = AgentCircuitBreaker(name="test", failure_threshold=1, reset_timeout=0.1)

        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))

        assert cb.state == BreakerState.OPEN
        time.sleep(0.15)
        assert cb.state == BreakerState.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = AgentCircuitBreaker(name="test", failure_threshold=1, reset_timeout=0.1)

        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))

        time.sleep(0.15)
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.state == BreakerState.CLOSED

    def test_semantic_failure_predicate(self):
        cb = AgentCircuitBreaker(name="test", failure_threshold=2)

        def is_error_result(result):
            return result.get("status") == "error"

        with pytest.raises(CircuitOpenError):
            cb.call(lambda: {"status": "error"}, failure_predicate=is_error_result)

        with pytest.raises(CircuitOpenError):
            cb.call(lambda: {"status": "error"}, failure_predicate=is_error_result)

    def test_manual_trip(self):
        cb = AgentCircuitBreaker(name="test")
        cb.trip()
        assert cb.state == BreakerState.OPEN

    def test_manual_reset(self):
        cb = AgentCircuitBreaker(name="test")
        cb.trip()
        cb.reset()
        assert cb.state == BreakerState.CLOSED

    def test_state_change_callback(self):
        changes = []
        cb = AgentCircuitBreaker(
            name="test",
            failure_threshold=1,
            _on_state_change=lambda old, new: changes.append((old, new)),
        )

        with pytest.raises(RuntimeError):
            cb.call(lambda: (_ for _ in ()).throw(RuntimeError("x")))

        assert changes[-1] == (BreakerState.CLOSED, BreakerState.OPEN)


class TestBreakerRegistry:
    def test_auto_creates_breakers(self, breaker_registry):
        breaker = breaker_registry.get("my_tool")
        assert breaker.name == "my_tool"
        assert breaker.state == BreakerState.CLOSED

    def test_same_name_returns_same_breaker(self, breaker_registry):
        b1 = breaker_registry.get("tool_a")
        b2 = breaker_registry.get("tool_a")
        assert b1 is b2

    def test_emergency_stop(self, breaker_registry):
        breaker_registry.get("tool_a")
        breaker_registry.get("tool_b")
        breaker_registry.emergency_stop()

        status = breaker_registry.status()
        assert all(v["state"] == "OPEN" for v in status.values())

    def test_reset_all(self, breaker_registry):
        breaker_registry.get("tool_a").trip()
        breaker_registry.get("tool_b").trip()
        breaker_registry.reset_all()

        status = breaker_registry.status()
        assert all(v["state"] == "CLOSED" for v in status.values())

    def test_status(self, breaker_registry):
        breaker_registry.get("read_file")
        status = breaker_registry.status()
        assert "read_file" in status
        assert status["read_file"]["state"] == "CLOSED"
