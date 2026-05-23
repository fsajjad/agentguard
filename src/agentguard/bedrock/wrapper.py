from __future__ import annotations

import json
from typing import Any

from agentguard.audit.log import TamperEvidentLog
from agentguard.bedrock.session import AgentSession
from agentguard.bedrock.tool_use import ToolUseInterceptor
from agentguard.circuit.breaker import CircuitOpenError
from agentguard.circuit.registry import BreakerRegistry
from agentguard.config import GuardConfig
from agentguard.contracts.models import ActionResult, ActionStatus, AgentAction
from agentguard.contracts.policies import PolicyEngine
from agentguard.monitor.bus import AsyncEventBus
from agentguard.monitor.events import AgentEvent, EventType


class BedrockAgentWrapper:
    """Wraps Bedrock converse() calls with the full safety pipeline.

    Pipeline: PolicyEngine -> CircuitBreaker -> ToolDispatch -> AuditLog
    """

    def __init__(
        self,
        bedrock_client: Any,
        model_id: str,
        policy_engine: PolicyEngine,
        interceptor: ToolUseInterceptor,
        config: GuardConfig | None = None,
        event_bus: AsyncEventBus | None = None,
        audit_log: TamperEvidentLog | None = None,
        breaker_registry: BreakerRegistry | None = None,
    ) -> None:
        self._client = bedrock_client
        self._model_id = model_id
        self._policy_engine = policy_engine
        self._interceptor = interceptor
        self._config = config or GuardConfig()
        self._event_bus = event_bus
        self._audit_log = audit_log if audit_log is not None else TamperEvidentLog()
        self._breakers = breaker_registry if breaker_registry is not None else BreakerRegistry(
            default_failure_threshold=self._config.circuit_failure_threshold,
            default_reset_timeout=self._config.circuit_reset_timeout,
        )

    async def converse(
        self,
        messages: list[dict[str, Any]],
        session: AgentSession,
        system: list[dict[str, Any]] | None = None,
        max_turns: int = 10,
    ) -> dict[str, Any]:
        """Run a multi-turn conversation with safety controls.

        Handles the tool-use loop: sends messages to Bedrock, intercepts
        tool_use responses, evaluates safety, executes approved tools,
        and feeds results back until the model stops requesting tools.
        """
        if not session.is_active():
            return {"error": "Session is not active", "session": session.summary()}

        await self._emit(EventType.SESSION_STARTED, session, {})

        tool_config = self._interceptor.to_bedrock_tool_config()
        current_messages = list(messages)
        final_response: dict[str, Any] = {}

        for turn in range(max_turns):
            if not session.is_active():
                break

            if session.budget.is_any_exceeded():
                session.halt("Budget exceeded")
                await self._emit(EventType.BUDGET_EXCEEDED, session, session.budget.usage_summary())
                break

            converse_params: dict[str, Any] = {
                "modelId": self._model_id,
                "messages": current_messages,
            }
            if system:
                converse_params["system"] = system
            if tool_config:
                converse_params["toolConfig"] = {"tools": tool_config}

            response = await self._call_bedrock(converse_params)
            final_response = response

            if "usage" in response:
                total_tokens = response["usage"].get("totalTokens", 0)
                session.record_tokens(total_tokens)

            stop_reason = response.get("stopReason", "")
            if stop_reason != "tool_use":
                break

            output_message = response.get("output", {}).get("message", {})
            tool_results = await self._process_tool_uses(
                output_message.get("content", []),
                session,
            )

            if not tool_results:
                break

            current_messages.append(output_message)
            current_messages.append({
                "role": "user",
                "content": tool_results,
            })

        if session.is_active():
            session.complete()

        await self._emit(EventType.SESSION_ENDED, session, session.summary())
        return final_response

    async def _process_tool_uses(
        self,
        content_blocks: list[dict[str, Any]],
        session: AgentSession,
    ) -> list[dict[str, Any]]:
        """Process all tool_use blocks in a response."""
        results = []

        for block in content_blocks:
            action = self._interceptor.parse_tool_use_block(block)
            if action is None:
                continue

            action.session_id = session.session_id
            result = await self._execute_guarded_action(action, session)

            tool_use_id = block.get("toolUseId", block.get("toolUse", {}).get("toolUseId", ""))
            tool_result: dict[str, Any] = {
                "toolResult": {
                    "toolUseId": tool_use_id,
                    "content": [{"text": json.dumps(result.output, default=str)}],
                }
            }
            if result.status == ActionStatus.BLOCKED:
                tool_result["toolResult"]["status"] = "error"
                tool_result["toolResult"]["content"] = [
                    {"text": f"Action blocked: {'; '.join(result.violations)}"}
                ]

            results.append(tool_result)

        return results

    async def _execute_guarded_action(
        self,
        action: AgentAction,
        session: AgentSession,
    ) -> ActionResult:
        """Run a single action through the full safety pipeline."""
        await self._emit(EventType.ACTION_PROPOSED, session, {"action": action.model_dump()})

        decision = self._policy_engine.evaluate(action)
        if not decision.allowed:
            session.record_violation(decision.reason)
            await self._emit(EventType.ACTION_BLOCKED, session, {
                "action": action.tool_name,
                "reason": decision.reason,
            })
            self._audit_log.append("action_blocked", {
                "action": action.model_dump(),
                "decision": decision.model_dump(),
            })
            return ActionResult(
                status=ActionStatus.BLOCKED,
                violations=[decision.reason],
            )

        breaker = self._breakers.get(action.tool_name)
        handler = self._interceptor.get_handler(action.tool_name)

        if handler is None:
            return ActionResult(
                status=ActionStatus.FAILED,
                violations=[f"No handler registered for tool '{action.tool_name}'"],
            )

        signature = self._interceptor.get_tool_signature(action)
        session.record_action(action.tool_name, signature)

        if session.rate.current_rate > session.max_call_rate:
            await self._emit(EventType.RATE_EXCEEDED, session, {"tool": action.tool_name})

        if session.pattern.record(signature):
            await self._emit(EventType.PATTERN_DETECTED, session, {
                "tool": action.tool_name,
                "signature": signature,
            })
            session.record_violation("repeated_pattern_detected")

        try:
            result = await breaker.call_async(handler, **action.parameters)
            await self._emit(EventType.ACTION_EXECUTED, session, {
                "action": action.tool_name,
            })
            self._audit_log.append("action_executed", {
                "action": action.model_dump(),
                "success": True,
            })
            return ActionResult(status=ActionStatus.SUCCESS, output=result)

        except CircuitOpenError:
            await self._emit(EventType.CIRCUIT_OPENED, session, {"tool": action.tool_name})
            session.halt(f"Circuit breaker open for '{action.tool_name}'")
            self._audit_log.append("circuit_opened", {"tool": action.tool_name})
            return ActionResult(
                status=ActionStatus.BLOCKED,
                violations=[f"Circuit breaker open for '{action.tool_name}'"],
            )

        except Exception as e:
            await self._emit(EventType.ACTION_FAILED, session, {
                "action": action.tool_name,
                "error": str(e),
            })
            self._audit_log.append("action_failed", {
                "action": action.model_dump(),
                "error": str(e),
            })
            return ActionResult(
                status=ActionStatus.FAILED,
                output=str(e),
            )

    async def _call_bedrock(self, params: dict[str, Any]) -> dict[str, Any]:
        """Call Bedrock converse API (async-compatible)."""
        try:
            response = self._client.converse(**params)
            return response  # type: ignore[no-any-return]
        except Exception as e:
            return {"error": str(e), "stopReason": "error"}

    async def _emit(
        self,
        event_type: EventType,
        session: AgentSession,
        payload: dict[str, Any],
    ) -> None:
        if self._event_bus:
            event = AgentEvent(
                type=event_type,
                session_id=session.session_id,
                payload=payload,
            )
            await self._event_bus.publish(event)

    @property
    def audit_log(self) -> TamperEvidentLog:
        return self._audit_log

    @property
    def breaker_registry(self) -> BreakerRegistry:
        return self._breakers
