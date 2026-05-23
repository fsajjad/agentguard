"""Full pipeline example: All safety features wired together with a mock Bedrock agent."""

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock

from agentguard import (
    GuardConfig,
    Policy,
    PolicyEngine,
    AsyncEventBus,
    TamperEvidentLog,
    LogSerializer,
    CheckpointManager,
    BreakerRegistry,
    AgentSession,
    BedrockAgentWrapper,
    ToolUseInterceptor,
    ToolSchema,
    EventType,
)
from agentguard.monitor.events import AgentEvent
from agentguard.monitor.handlers import ConsoleHandler


def create_mock_bedrock_client(tool_calls: list[dict[str, Any]]) -> MagicMock:
    """Create a mock Bedrock client that returns tool_use responses."""
    client = MagicMock()
    responses = []

    for tc in tool_calls:
        responses.append({
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "toolUse",
                            "toolUseId": f"id_{tc['name']}",
                            "name": tc["name"],
                            "input": tc["input"],
                        }
                    ],
                }
            },
            "stopReason": "tool_use",
            "usage": {"totalTokens": 150},
        })

    # Final response (no more tool calls)
    responses.append({
        "output": {
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Task completed successfully."}],
            }
        },
        "stopReason": "end_turn",
        "usage": {"totalTokens": 50},
    })

    client.converse = MagicMock(side_effect=responses)
    return client


async def run_pipeline() -> None:
    print("=== Full Safety Pipeline Demo ===\n")

    # 1. Configuration
    config = GuardConfig(
        max_risk_score=0.8,
        max_tool_calls_per_session=10,
        circuit_failure_threshold=3,
        circuit_reset_timeout=30.0,
        audit_checkpoint_interval=5,
    )

    # 2. Policy engine
    policy = Policy(
        name="sandbox_policy",
        allowed_tools=frozenset({"read_file", "list_files", "calculate"}),
        denied_tools=frozenset({"delete_file", "execute_shell", "send_email"}),
        max_risk_score=config.max_risk_score,
    )
    policy_engine = PolicyEngine([policy])

    # 3. Tool interceptor with registered tools
    interceptor = ToolUseInterceptor(policy_engine)

    async def read_file_handler(path: str) -> str:
        return f"File contents: [simulated data from {path}]"

    async def list_files_handler(directory: str) -> str:
        return json.dumps(["file1.txt", "file2.py", "data.json"])

    async def calculate_handler(expression: str) -> str:
        return f"Result: 42"

    interceptor.register_tool(
        ToolSchema(name="read_file", description="Read a file", risk_score=0.1),
        handler=read_file_handler,
    )
    interceptor.register_tool(
        ToolSchema(name="list_files", description="List directory", risk_score=0.1),
        handler=list_files_handler,
    )
    interceptor.register_tool(
        ToolSchema(name="calculate", description="Evaluate expression", risk_score=0.2),
        handler=calculate_handler,
    )

    # 4. Event bus with monitoring
    event_bus = AsyncEventBus(max_queue_size=config.event_bus_max_queue)

    events_received: list[AgentEvent] = []

    async def collect_events(event: AgentEvent) -> None:
        events_received.append(event)
        print(f"  [EVENT] {event.type.value}: {json.dumps(event.payload, default=str)[:80]}")

    event_bus.subscribe_all(collect_events)
    await event_bus.start()

    # 5. Audit log
    audit_log = TamperEvidentLog()

    # 6. Breaker registry
    breaker_registry = BreakerRegistry(
        default_failure_threshold=config.circuit_failure_threshold,
        default_reset_timeout=config.circuit_reset_timeout,
    )

    # 7. Mock Bedrock client with planned tool calls
    tool_calls = [
        {"name": "list_files", "input": {"directory": "/workspace"}},
        {"name": "read_file", "input": {"path": "/workspace/config.json"}},
        {"name": "delete_file", "input": {"path": "/workspace/important.db"}},  # Should be blocked
        {"name": "calculate", "input": {"expression": "2 + 2"}},
    ]
    mock_client = create_mock_bedrock_client(tool_calls)

    # 8. Create the wrapper
    wrapper = BedrockAgentWrapper(
        bedrock_client=mock_client,
        model_id="anthropic.claude-3-sonnet-20240229-v1:0",
        policy_engine=policy_engine,
        interceptor=interceptor,
        config=config,
        event_bus=event_bus,
        audit_log=audit_log,
        breaker_registry=breaker_registry,
    )

    # 9. Run the agent conversation
    session = AgentSession(
        max_tokens=config.max_tokens_per_session,
        max_tool_calls=config.max_tool_calls_per_session,
        max_wall_seconds=config.session_timeout_seconds,
    )

    messages = [
        {
            "role": "user",
            "content": [{"text": "List files, read the config, and calculate 2+2."}],
        }
    ]

    print("Starting agent conversation...\n")
    response = await wrapper.converse(
        messages=messages,
        session=session,
        system=[{"text": "You are a helpful assistant with access to file and math tools."}],
    )

    # 10. Print results
    await asyncio.sleep(0.2)
    await event_bus.stop()

    print(f"\n=== Results ===")
    print(f"Session state: {session.state.value}")
    print(f"Actions executed: {session.action_count}")
    print(f"Trust score: {session.trust_score}")
    print(f"Violations: {len(session.violations)}")
    print(f"Audit log entries: {audit_log.size}")
    print(f"Audit log integrity: {audit_log.verify_integrity()[0]}")
    print(f"Root hash: {audit_log.root_hash[:32]}...")
    print(f"Events received: {len(events_received)}")
    print(f"Breaker status: {breaker_registry.status()}")

    # Print violations
    if session.violations:
        print(f"\nViolations:")
        for v in session.violations:
            print(f"  - {v['rule']}")


def main() -> None:
    asyncio.run(run_pipeline())


if __name__ == "__main__":
    main()
