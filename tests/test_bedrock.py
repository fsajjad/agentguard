import pytest

from agentguard.bedrock.session import AgentSession, SessionState
from agentguard.bedrock.tool_use import ToolUseInterceptor, ToolSchema
from agentguard.contracts.models import AgentAction
from agentguard.contracts.policies import Policy, PolicyEngine


class TestAgentSession:
    def test_initial_state(self, session):
        assert session.state == SessionState.ACTIVE
        assert session.trust_score == 1.0
        assert session.action_count == 0

    def test_record_action(self, session):
        session.record_action("read_file", "read_file:{}")
        assert session.action_count == 1

    def test_record_violation_decreases_trust(self, session):
        session.record_violation("test_rule")
        assert session.trust_score == pytest.approx(0.8)
        session.record_violation("another_rule")
        assert session.trust_score == pytest.approx(0.6)

    def test_trust_score_floors_at_zero(self, session):
        for _ in range(10):
            session.record_violation("rule")
        assert session.trust_score == 0.0

    def test_halt_changes_state(self, session):
        session.halt("test reason")
        assert session.state == SessionState.HALTED
        assert not session.is_active()

    def test_complete_changes_state(self, session):
        session.complete()
        assert session.state == SessionState.COMPLETED

    def test_summary(self, session):
        session.record_action("tool_a", "sig_a")
        summary = session.summary()
        assert summary["session_id"] == session.session_id
        assert summary["action_count"] == 1
        assert summary["state"] == "active"


class TestToolUseInterceptor:
    @pytest.fixture
    def interceptor(self, policy_engine):
        interceptor = ToolUseInterceptor(policy_engine)
        interceptor.register_tool(
            ToolSchema(
                name="read_file",
                description="Read a file",
                input_schema={"type": "object", "properties": {"path": {"type": "string"}}},
                risk_score=0.1,
            ),
            handler=lambda path: f"contents of {path}",
        )
        return interceptor

    def test_parse_tool_use_block(self, interceptor):
        block = {
            "type": "toolUse",
            "toolUseId": "abc123",
            "name": "read_file",
            "input": {"path": "/tmp/test.txt"},
        }
        action = interceptor.parse_tool_use_block(block)
        assert action is not None
        assert action.tool_name == "read_file"
        assert action.parameters == {"path": "/tmp/test.txt"}
        assert action.risk_score == 0.1

    def test_parse_nested_tool_use_block(self, interceptor):
        block = {
            "toolUse": {
                "toolUseId": "abc123",
                "name": "read_file",
                "input": {"path": "/home/user/file.txt"},
            }
        }
        action = interceptor.parse_tool_use_block(block)
        assert action is not None
        assert action.tool_name == "read_file"

    def test_parse_non_tool_block_returns_none(self, interceptor):
        block = {"type": "text", "text": "Hello"}
        action = interceptor.parse_tool_use_block(block)
        assert action is None

    def test_unregistered_tool_gets_default_risk(self, interceptor):
        block = {
            "type": "toolUse",
            "name": "unknown_tool",
            "input": {},
        }
        action = interceptor.parse_tool_use_block(block)
        assert action is not None
        assert action.risk_score == 0.5
        assert action.requires_approval is True

    def test_evaluate_action(self, interceptor):
        action = AgentAction(tool_name="read_file", risk_score=0.1)
        decision = interceptor.evaluate_action(action)
        assert decision.allowed is True

    def test_get_handler(self, interceptor):
        handler = interceptor.get_handler("read_file")
        assert handler is not None
        assert handler(path="/tmp/x") == "contents of /tmp/x"

    def test_to_bedrock_tool_config(self, interceptor):
        config = interceptor.to_bedrock_tool_config()
        assert len(config) == 1
        assert config[0]["toolSpec"]["name"] == "read_file"

    def test_get_tool_signature(self, interceptor):
        action = AgentAction(
            tool_name="read_file",
            parameters={"path": "/tmp/test.txt"},
        )
        sig = interceptor.get_tool_signature(action)
        assert "read_file" in sig
        assert "/tmp/test.txt" in sig
