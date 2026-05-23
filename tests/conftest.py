import pytest

from agentguard.contracts.policies import Policy, PolicyEngine
from agentguard.audit.log import TamperEvidentLog
from agentguard.circuit.registry import BreakerRegistry
from agentguard.bedrock.session import AgentSession


@pytest.fixture
def policy_engine():
    policy = Policy(
        name="test_policy",
        allowed_tools=frozenset({"read_file", "list_files", "search"}),
        denied_tools=frozenset({"delete_file", "execute_shell"}),
        max_risk_score=0.8,
    )
    engine = PolicyEngine([policy])
    return engine


@pytest.fixture
def audit_log():
    return TamperEvidentLog()


@pytest.fixture
def breaker_registry():
    return BreakerRegistry(default_failure_threshold=3, default_reset_timeout=1.0)


@pytest.fixture
def session():
    return AgentSession(
        max_tokens=10_000,
        max_tool_calls=10,
        max_wall_seconds=60.0,
    )
