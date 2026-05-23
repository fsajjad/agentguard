from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    ACTION_PROPOSED = "action_proposed"
    ACTION_APPROVED = "action_approved"
    ACTION_BLOCKED = "action_blocked"
    ACTION_EXECUTED = "action_executed"
    ACTION_FAILED = "action_failed"
    CONTRACT_VIOLATED = "contract_violated"
    CIRCUIT_OPENED = "circuit_opened"
    CIRCUIT_CLOSED = "circuit_closed"
    CIRCUIT_HALF_OPEN = "circuit_half_open"
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXCEEDED = "budget_exceeded"
    RATE_EXCEEDED = "rate_exceeded"
    PATTERN_DETECTED = "pattern_detected"
    SESSION_STARTED = "session_started"
    SESSION_ENDED = "session_ended"
    EMERGENCY_STOP = "emergency_stop"


@dataclass(frozen=True, slots=True)
class AgentEvent:
    type: EventType
    session_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type.value,
            "session_id": self.session_id,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }
