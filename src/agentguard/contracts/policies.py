from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Any

from agentguard.contracts.models import AgentAction, PolicyDecision


@dataclass(frozen=True, slots=True)
class Policy:
    name: str
    allowed_tools: frozenset[str] = field(default_factory=frozenset)
    denied_tools: frozenset[str] = field(default_factory=frozenset)
    max_risk_score: float = 1.0
    conditions: list[Callable[[AgentAction], bool]] = field(default_factory=list)

    def evaluate(self, action: AgentAction) -> PolicyDecision:
        if self.denied_tools and action.tool_name in self.denied_tools:
            return PolicyDecision(
                allowed=False,
                reason=f"Tool '{action.tool_name}' is in deny list",
                risk_score=action.risk_score,
                policy_name=self.name,
            )

        if self.allowed_tools and action.tool_name not in self.allowed_tools:
            return PolicyDecision(
                allowed=False,
                reason=f"Tool '{action.tool_name}' is not in allow list",
                risk_score=action.risk_score,
                policy_name=self.name,
            )

        if action.risk_score > self.max_risk_score:
            return PolicyDecision(
                allowed=False,
                reason=f"Risk score {action.risk_score} exceeds max {self.max_risk_score}",
                risk_score=action.risk_score,
                policy_name=self.name,
            )

        for condition in self.conditions:
            if not condition(action):
                return PolicyDecision(
                    allowed=False,
                    reason=f"Condition '{condition.__name__}' failed",
                    risk_score=action.risk_score,
                    policy_name=self.name,
                )

        return PolicyDecision(
            allowed=True,
            reason="All checks passed",
            risk_score=action.risk_score,
            policy_name=self.name,
        )


class PolicyEngine:
    def __init__(self, policies: list[Policy] | None = None) -> None:
        self._policies: list[Policy] = policies or []

    def add_policy(self, policy: Policy) -> None:
        self._policies.append(policy)

    def evaluate(self, action: AgentAction) -> PolicyDecision:
        """Evaluate all policies (AND logic). First denial wins."""
        for policy in self._policies:
            decision = policy.evaluate(action)
            if not decision.allowed:
                return decision

        return PolicyDecision(
            allowed=True,
            reason="All policies passed",
            risk_score=action.risk_score,
        )

    @property
    def policies(self) -> list[Policy]:
        return list(self._policies)
