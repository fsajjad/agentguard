"""AgentGuard — AI Agent Behavioral Safety Framework for Amazon Bedrock."""

from agentguard._version import __version__
from agentguard.config import GuardConfig
from agentguard.contracts.models import (
    AgentAction,
    ActionResult,
    ActionStatus,
    PolicyDecision,
    ViolationError,
)
from agentguard.contracts.guards import agent_guard
from agentguard.contracts.policies import Policy, PolicyEngine
from agentguard.monitor.events import AgentEvent, EventType
from agentguard.monitor.bus import AsyncEventBus, SyncEventBus
from agentguard.monitor.detectors import RateDetector, BudgetDetector, PatternDetector
from agentguard.circuit.breaker import AgentCircuitBreaker, BreakerState, CircuitOpenError
from agentguard.circuit.registry import BreakerRegistry
from agentguard.audit.log import TamperEvidentLog, LogEntry
from agentguard.audit.serializer import LogSerializer
from agentguard.audit.checkpoint import CheckpointManager
from agentguard.bedrock.wrapper import BedrockAgentWrapper
from agentguard.bedrock.session import AgentSession, SessionState
from agentguard.bedrock.tool_use import ToolUseInterceptor, ToolSchema

__all__ = [
    "__version__",
    "GuardConfig",
    "AgentAction",
    "ActionResult",
    "ActionStatus",
    "PolicyDecision",
    "ViolationError",
    "agent_guard",
    "Policy",
    "PolicyEngine",
    "AgentEvent",
    "EventType",
    "AsyncEventBus",
    "SyncEventBus",
    "RateDetector",
    "BudgetDetector",
    "PatternDetector",
    "AgentCircuitBreaker",
    "BreakerState",
    "CircuitOpenError",
    "BreakerRegistry",
    "TamperEvidentLog",
    "LogEntry",
    "LogSerializer",
    "CheckpointManager",
    "BedrockAgentWrapper",
    "AgentSession",
    "SessionState",
    "ToolUseInterceptor",
    "ToolSchema",
]
