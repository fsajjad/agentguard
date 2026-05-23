import pytest

from agentguard.contracts.models import AgentAction, PolicyDecision, ViolationError
from agentguard.contracts.guards import agent_guard
from agentguard.contracts.conditions import (
    no_shell_injection,
    no_pii_in_output,
    max_output_length,
    action_in_allowlist,
    action_not_in_denylist,
    risk_below_threshold,
)
from agentguard.contracts.policies import Policy, PolicyEngine


class TestAgentAction:
    def test_valid_action(self):
        action = AgentAction(
            tool_name="read_file",
            parameters={"path": "/tmp/test.txt"},
            risk_score=0.2,
        )
        assert action.tool_name == "read_file"
        assert action.risk_score == 0.2

    def test_empty_tool_name_rejected(self):
        with pytest.raises(ValueError):
            AgentAction(tool_name="", parameters={})

    def test_risk_score_bounds(self):
        with pytest.raises(ValueError):
            AgentAction(tool_name="test", risk_score=1.5)
        with pytest.raises(ValueError):
            AgentAction(tool_name="test", risk_score=-0.1)


class TestAgentGuard:
    def test_pre_condition_passes(self):
        def always_true(**kwargs):
            return True

        @agent_guard(pre=[always_true])
        def my_tool(command: str) -> str:
            return f"executed: {command}"

        assert my_tool(command="ls") == "executed: ls"

    def test_pre_condition_blocks(self):
        @agent_guard(pre=[no_shell_injection])
        def my_tool(command: str) -> str:
            return f"executed: {command}"

        with pytest.raises(ViolationError) as exc_info:
            my_tool(command="ls; rm -rf /")
        assert "no_shell_injection" in str(exc_info.value)

    def test_post_condition_blocks(self):
        @agent_guard(post=[no_pii_in_output])
        def my_tool() -> str:
            return "User SSN is 123-45-6789"

        with pytest.raises(ViolationError):
            my_tool()

    def test_on_violation_handler(self):
        @agent_guard(
            pre=[no_shell_injection],
            on_violation=lambda e: f"BLOCKED: {e.rule}",
        )
        def my_tool(command: str) -> str:
            return f"executed: {command}"

        result = my_tool(command="ls && whoami")
        assert result == "BLOCKED: no_shell_injection"

    @pytest.mark.asyncio
    async def test_async_guard(self):
        @agent_guard(pre=[no_shell_injection])
        async def my_async_tool(command: str) -> str:
            return f"executed: {command}"

        result = await my_async_tool(command="ls")
        assert result == "executed: ls"

        with pytest.raises(ViolationError):
            await my_async_tool(command="$(whoami)")


class TestConditions:
    def test_no_shell_injection(self):
        assert no_shell_injection(command="ls -la") is True
        assert no_shell_injection(command="ls; rm -rf /") is False
        assert no_shell_injection(command="$(whoami)") is False
        assert no_shell_injection(command="echo `id`") is False

    def test_no_pii_in_output(self):
        assert no_pii_in_output("Hello world") is True
        assert no_pii_in_output("SSN: 123-45-6789") is False
        assert no_pii_in_output("email: test@example.com") is False
        assert no_pii_in_output("card: 4111 1111 1111 1111") is False

    def test_max_output_length(self):
        check = max_output_length(10)
        assert check("short") is True
        assert check("x" * 11) is False

    def test_action_in_allowlist(self):
        check = action_in_allowlist(frozenset({"read", "write"}))
        assert check(tool_name="read") is True
        assert check(tool_name="delete") is False

    def test_action_not_in_denylist(self):
        check = action_not_in_denylist(frozenset({"delete", "drop"}))
        assert check(tool_name="read") is True
        assert check(tool_name="delete") is False

    def test_risk_below_threshold(self):
        check = risk_below_threshold(0.5)
        assert check(risk_score=0.3) is True
        assert check(risk_score=0.7) is False


class TestPolicyEngine:
    def test_allowed_action(self, policy_engine):
        action = AgentAction(tool_name="read_file", risk_score=0.2)
        decision = policy_engine.evaluate(action)
        assert decision.allowed is True

    def test_denied_tool(self, policy_engine):
        action = AgentAction(tool_name="delete_file", risk_score=0.1)
        decision = policy_engine.evaluate(action)
        assert decision.allowed is False
        assert "deny list" in decision.reason

    def test_unlisted_tool(self, policy_engine):
        action = AgentAction(tool_name="unknown_tool", risk_score=0.1)
        decision = policy_engine.evaluate(action)
        assert decision.allowed is False
        assert "not in allow list" in decision.reason

    def test_high_risk_blocked(self, policy_engine):
        action = AgentAction(tool_name="read_file", risk_score=0.9)
        decision = policy_engine.evaluate(action)
        assert decision.allowed is False
        assert "exceeds" in decision.reason

    def test_multiple_policies(self):
        p1 = Policy(name="p1", allowed_tools=frozenset({"read", "write"}))
        p2 = Policy(name="p2", max_risk_score=0.5)
        engine = PolicyEngine([p1, p2])

        action = AgentAction(tool_name="read", risk_score=0.7)
        decision = engine.evaluate(action)
        assert decision.allowed is False
        assert decision.policy_name == "p2"
