"""Lambda handler for the AgentGuard demo API."""

import asyncio
import json
import os
import sys
from typing import Any

import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agentguard import (
    GuardConfig,
    Policy,
    PolicyEngine,
    AsyncEventBus,
    TamperEvidentLog,
    BreakerRegistry,
    AgentSession,
    BedrockAgentWrapper,
    ToolUseInterceptor,
    ToolSchema,
)
from agentguard.monitor.events import AgentEvent


def create_pipeline():
    """Create the safety pipeline components."""
    config = GuardConfig(
        max_risk_score=0.8,
        max_tool_calls_per_session=10,
        circuit_failure_threshold=3,
        circuit_reset_timeout=30.0,
    )

    policy = Policy(
        name="demo_policy",
        allowed_tools=frozenset({"read_file", "list_files", "calculate"}),
        denied_tools=frozenset({"delete_file", "execute_shell", "send_email"}),
        max_risk_score=config.max_risk_score,
    )
    policy_engine = PolicyEngine([policy])

    interceptor = ToolUseInterceptor(policy_engine)

    async def read_file_handler(path: str) -> str:
        return f"Contents of {path}: [project_name=agentguard, version=0.1.0, env=production]"

    async def list_files_handler(directory: str) -> str:
        return json.dumps(["config.json", "app.py", "requirements.txt", "data/"])

    async def calculate_handler(expression: str) -> str:
        return f"Result: 45"

    async def delete_file_handler(path: str) -> str:
        return f"Deleted {path}"

    async def execute_shell_handler(command: str) -> str:
        return f"Executed: {command}"

    interceptor.register_tool(
        ToolSchema(
            name="read_file",
            description="Read contents of a file given its path",
            risk_score=0.1,
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path to read"}},
                "required": ["path"],
            },
        ),
        handler=read_file_handler,
    )
    interceptor.register_tool(
        ToolSchema(
            name="list_files",
            description="List files in a directory",
            risk_score=0.1,
            input_schema={
                "type": "object",
                "properties": {"directory": {"type": "string", "description": "Directory path"}},
                "required": ["directory"],
            },
        ),
        handler=list_files_handler,
    )
    interceptor.register_tool(
        ToolSchema(
            name="calculate",
            description="Calculate a math expression",
            risk_score=0.1,
            input_schema={
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "Math expression"}},
                "required": ["expression"],
            },
        ),
        handler=calculate_handler,
    )
    interceptor.register_tool(
        ToolSchema(
            name="delete_file",
            description="Delete a file from disk",
            risk_score=0.9,
            input_schema={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path to delete"}},
                "required": ["path"],
            },
        ),
        handler=delete_file_handler,
    )
    interceptor.register_tool(
        ToolSchema(
            name="execute_shell",
            description="Execute a shell command",
            risk_score=1.0,
            input_schema={
                "type": "object",
                "properties": {"command": {"type": "string", "description": "Shell command"}},
                "required": ["command"],
            },
        ),
        handler=execute_shell_handler,
    )

    return config, policy_engine, interceptor


async def run_scenario(prompt: str) -> dict[str, Any]:
    """Run a scenario through the full safety pipeline."""
    config, policy_engine, interceptor = create_pipeline()

    region = os.environ.get("AWS_REGION", "us-east-1")
    model_id = os.environ.get("BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")

    bedrock_client = boto3.client("bedrock-runtime", region_name=region)

    event_bus = AsyncEventBus(max_queue_size=100)
    audit_log = TamperEvidentLog()
    breaker_registry = BreakerRegistry(
        default_failure_threshold=config.circuit_failure_threshold,
        default_reset_timeout=config.circuit_reset_timeout,
    )

    collected_events: list[dict[str, Any]] = []
    activity_log: list[dict[str, Any]] = []
    action_counter = {"count": 0}

    async def collect(event: AgentEvent) -> None:
        status = "info"
        if "blocked" in event.type.value:
            status = "blocked"
        elif "executed" in event.type.value:
            status = "success"
        elif "exceeded" in event.type.value or "pattern" in event.type.value:
            status = "warning"

        collected_events.append({
            "type": event.type.value.replace("_", " ").title(),
            "detail": json.dumps(event.payload, default=str),
            "status": status,
        })

        if event.type.value == "action_proposed":
            action_counter["count"] += 1
            action_data = event.payload.get("action", {})
            tool_name = action_data.get("tool_name", "unknown")
            params = action_data.get("parameters", {})
            risk = action_data.get("risk_score", 0.0)
            activity_log.append({
                "timestamp": f"T+{action_counter['count']}",
                "action": "tool_call",
                "tool": tool_name,
                "params": json.dumps(params, default=str),
                "outcome": "pending",
                "risk_score": risk,
            })

        elif event.type.value == "action_blocked":
            if activity_log:
                activity_log[-1]["outcome"] = "blocked"
                activity_log[-1]["reason"] = event.payload.get("reason", "Policy violation")

        elif event.type.value == "action_executed":
            if activity_log:
                activity_log[-1]["outcome"] = "allowed"

        elif event.type.value == "action_failed":
            if activity_log:
                activity_log[-1]["outcome"] = "failed"
                activity_log[-1]["reason"] = event.payload.get("error", "Unknown error")

    event_bus.subscribe_all(collect)
    await event_bus.start()

    wrapper = BedrockAgentWrapper(
        bedrock_client=bedrock_client,
        model_id=model_id,
        policy_engine=policy_engine,
        interceptor=interceptor,
        config=config,
        event_bus=event_bus,
        audit_log=audit_log,
        breaker_registry=breaker_registry,
    )

    session = AgentSession(
        max_tokens=config.max_tokens_per_session,
        max_tool_calls=config.max_tool_calls_per_session,
        max_wall_seconds=config.session_timeout_seconds,
    )

    messages = [{"role": "user", "content": [{"text": prompt}]}]

    await wrapper.converse(
        messages=messages,
        session=session,
        system=[{"text": "You are a helpful assistant. Use the tools available to complete tasks. Always use the appropriate tool when asked to read files, list directories, calculate, delete files, or execute commands. Do not refuse tool usage."}],
    )

    await asyncio.sleep(0.1)
    await event_bus.stop()

    violations = [v["rule"] for v in session.violations] if session.violations else []
    actions_blocked = len(violations)

    return {
        "events": collected_events,
        "activity_log": activity_log,
        "result": {
            "session_state": session.state.value,
            "actions_executed": session.action_count,
            "actions_blocked": actions_blocked,
            "violations": violations,
            "trust_score": session.trust_score,
            "audit_entries": audit_log.size,
            "audit_valid": audit_log.verify_integrity()[0],
        },
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entry point."""
    headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }

    if event.get("httpMethod") == "OPTIONS" or event.get("requestContext", {}).get("http", {}).get("method") == "OPTIONS":
        return {"statusCode": 200, "headers": headers, "body": ""}

    try:
        body = json.loads(event.get("body", "{}"))
        prompt = body.get("prompt", "")

        if not prompt:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "prompt is required"}),
            }

        result = asyncio.run(run_scenario(prompt))

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(result, default=str),
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)}),
        }
