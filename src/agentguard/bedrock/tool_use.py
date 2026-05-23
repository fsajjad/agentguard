from __future__ import annotations

import json
from typing import Any, Callable

from pydantic import BaseModel

from agentguard.contracts.models import AgentAction, PolicyDecision
from agentguard.contracts.policies import PolicyEngine


class ToolSchema(BaseModel):
    """Schema definition for a registered tool."""
    name: str
    description: str = ""
    input_schema: dict[str, Any] | None = None
    risk_score: float = 0.0
    requires_approval: bool = False


class ToolUseInterceptor:
    """Intercepts Bedrock tool_use blocks and routes them through safety checks."""

    def __init__(self, policy_engine: PolicyEngine) -> None:
        self._policy_engine = policy_engine
        self._registered_tools: dict[str, ToolSchema] = {}
        self._tool_handlers: dict[str, Callable[..., Any]] = {}

    def register_tool(
        self,
        schema: ToolSchema,
        handler: Callable[..., Any],
    ) -> None:
        self._registered_tools[schema.name] = schema
        self._tool_handlers[schema.name] = handler

    def parse_tool_use_block(self, content_block: dict[str, Any]) -> AgentAction | None:
        """Parse a Bedrock tool_use content block into an AgentAction."""
        if content_block.get("type") != "toolUse":
            if "toolUse" not in content_block:
                return None
            tool_data = content_block["toolUse"]
        else:
            tool_data = content_block

        tool_name = tool_data.get("name", "")
        parameters = tool_data.get("input", {})

        schema = self._registered_tools.get(tool_name)
        risk_score = schema.risk_score if schema else 0.5
        requires_approval = schema.requires_approval if schema else True

        return AgentAction(
            tool_name=tool_name,
            parameters=parameters,
            risk_score=risk_score,
            requires_approval=requires_approval,
        )

    def evaluate_action(self, action: AgentAction) -> PolicyDecision:
        """Run the action through the policy engine."""
        return self._policy_engine.evaluate(action)

    def get_handler(self, tool_name: str) -> Callable[..., Any] | None:
        return self._tool_handlers.get(tool_name)

    def get_tool_signature(self, action: AgentAction) -> str:
        """Generate a signature string for pattern detection."""
        return f"{action.tool_name}:{json.dumps(action.parameters, sort_keys=True)}"

    @property
    def registered_tool_names(self) -> list[str]:
        return list(self._registered_tools.keys())

    def to_bedrock_tool_config(self) -> list[dict[str, Any]]:
        """Generate Bedrock-compatible toolConfig from registered tools."""
        tools = []
        for schema in self._registered_tools.values():
            tool_spec: dict[str, Any] = {
                "toolSpec": {
                    "name": schema.name,
                    "description": schema.description,
                }
            }
            if schema.input_schema:
                tool_spec["toolSpec"]["inputSchema"] = {
                    "json": schema.input_schema
                }
            tools.append(tool_spec)
        return tools
