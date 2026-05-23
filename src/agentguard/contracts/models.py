from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ActionStatus(str, Enum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentAction(BaseModel):
    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_approval: bool = False
    session_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tool_name")
    @classmethod
    def tool_name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("tool_name cannot be empty")
        return v


class ActionResult(BaseModel):
    status: ActionStatus
    output: Any = None
    violations: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    allowed: bool
    reason: str
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)
    policy_name: str = ""


class ViolationError(Exception):
    def __init__(self, rule: str, context: dict[str, Any] | None = None) -> None:
        self.rule = rule
        self.context = context or {}
        super().__init__(f"Contract violation: {rule}")
