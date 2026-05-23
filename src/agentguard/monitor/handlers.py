from __future__ import annotations

import json
import sys
from typing import Callable, Awaitable, TYPE_CHECKING

from agentguard.monitor.events import AgentEvent, EventType

if TYPE_CHECKING:
    from agentguard.audit.log import TamperEvidentLog


class ConsoleHandler:
    """Prints events to stdout as structured JSON."""

    def __init__(self, stream: object = None) -> None:
        self._stream = stream or sys.stdout

    async def __call__(self, event: AgentEvent) -> None:
        line = json.dumps(event.to_dict(), default=str)
        print(line, file=self._stream)  # type: ignore[arg-type]


class AuditHandler:
    """Routes events to a TamperEvidentLog."""

    def __init__(self, log: TamperEvidentLog) -> None:
        self._log = log

    async def __call__(self, event: AgentEvent) -> None:
        self._log.append(event.type.value, event.to_dict())


class AlertHandler:
    """Fires a callback on critical events."""

    CRITICAL_EVENTS = frozenset({
        EventType.CIRCUIT_OPENED,
        EventType.BUDGET_EXCEEDED,
        EventType.EMERGENCY_STOP,
        EventType.CONTRACT_VIOLATED,
    })

    def __init__(
        self,
        callback: Callable[[AgentEvent], None] | Callable[[AgentEvent], Awaitable[None]],
        event_types: frozenset[EventType] | None = None,
    ) -> None:
        self._callback = callback
        self._event_types = event_types or self.CRITICAL_EVENTS

    async def __call__(self, event: AgentEvent) -> None:
        if event.type in self._event_types:
            result = self._callback(event)
            if hasattr(result, "__await__"):
                await result  # type: ignore[misc]
