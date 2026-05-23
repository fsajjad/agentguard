import asyncio

import pytest

from agentguard.monitor.events import AgentEvent, EventType
from agentguard.monitor.bus import AsyncEventBus, SyncEventBus
from agentguard.monitor.detectors import RateDetector, BudgetDetector, PatternDetector


class TestAsyncEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish(self):
        bus = AsyncEventBus()
        received = []

        async def handler(event: AgentEvent):
            received.append(event)

        bus.subscribe(EventType.ACTION_EXECUTED, handler)
        await bus.start()

        event = AgentEvent(
            type=EventType.ACTION_EXECUTED,
            session_id="test-session",
            payload={"tool": "read_file"},
        )
        await bus.publish(event)
        await asyncio.sleep(0.1)
        await bus.stop()

        assert len(received) == 1
        assert received[0].type == EventType.ACTION_EXECUTED

    @pytest.mark.asyncio
    async def test_wildcard_subscription(self):
        bus = AsyncEventBus()
        received = []

        async def handler(event: AgentEvent):
            received.append(event)

        bus.subscribe_all(handler)
        await bus.start()

        await bus.publish(AgentEvent(type=EventType.ACTION_EXECUTED, session_id="s1"))
        await bus.publish(AgentEvent(type=EventType.CIRCUIT_OPENED, session_id="s1"))
        await asyncio.sleep(0.1)
        await bus.stop()

        assert len(received) == 2

    @pytest.mark.asyncio
    async def test_handler_error_doesnt_crash_bus(self):
        bus = AsyncEventBus()
        received = []

        async def broken_handler(event: AgentEvent):
            raise RuntimeError("Handler crashed")

        async def good_handler(event: AgentEvent):
            received.append(event)

        bus.subscribe(EventType.ACTION_EXECUTED, broken_handler)
        bus.subscribe(EventType.ACTION_EXECUTED, good_handler)
        await bus.start()

        await bus.publish(AgentEvent(type=EventType.ACTION_EXECUTED, session_id="s1"))
        await asyncio.sleep(0.1)
        await bus.stop()

        assert len(received) == 1


class TestSyncEventBus:
    def test_publish_and_receive(self):
        bus = SyncEventBus()
        received = []

        bus.subscribe(EventType.ACTION_BLOCKED, lambda e: received.append(e))
        bus.publish(AgentEvent(type=EventType.ACTION_BLOCKED, session_id="s1"))

        assert len(received) == 1


class TestRateDetector:
    def test_under_limit(self):
        detector = RateDetector(max_calls=5, window_seconds=60.0)
        for _ in range(5):
            assert detector.record() is False

    def test_over_limit(self):
        detector = RateDetector(max_calls=3, window_seconds=60.0)
        for _ in range(3):
            detector.record()
        assert detector.record() is True

    def test_current_rate(self):
        detector = RateDetector(max_calls=10, window_seconds=60.0)
        for _ in range(5):
            detector.record()
        assert detector.current_rate == 5


class TestBudgetDetector:
    def test_token_budget(self):
        detector = BudgetDetector(max_tokens=100)
        assert detector.record_tokens(50) is False
        assert detector.record_tokens(60) is True

    def test_tool_call_budget(self):
        detector = BudgetDetector(max_tool_calls=3)
        assert detector.record_tool_call() is False
        assert detector.record_tool_call() is False
        assert detector.record_tool_call() is False
        assert detector.record_tool_call() is True

    def test_usage_summary(self):
        detector = BudgetDetector(max_tokens=1000, max_tool_calls=10)
        detector.record_tokens(500)
        detector.record_tool_call()
        summary = detector.usage_summary()
        assert summary["tokens"]["used"] == 500
        assert summary["tool_calls"]["used"] == 1


class TestPatternDetector:
    def test_no_pattern(self):
        detector = PatternDetector(max_repeats=3)
        assert detector.record("call_a") is False
        assert detector.record("call_b") is False
        assert detector.record("call_c") is False

    def test_detects_repetition(self):
        detector = PatternDetector(max_repeats=3)
        detector.record("same_call")
        detector.record("same_call")
        assert detector.record("same_call") is True

    def test_mixed_calls_no_pattern(self):
        detector = PatternDetector(max_repeats=3)
        detector.record("call_a")
        detector.record("call_b")
        assert detector.record("call_a") is False
