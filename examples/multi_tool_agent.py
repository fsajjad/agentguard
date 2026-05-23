"""Example: Multiple tools with per-tool policies and circuit breakers."""

from agentguard import (
    Policy,
    PolicyEngine,
    AgentAction,
    AgentCircuitBreaker,
    BreakerRegistry,
    BreakerState,
    TamperEvidentLog,
    CircuitOpenError,
)


def simulate_read_file(path: str) -> str:
    return f"[file contents of {path}]"


def simulate_write_file(path: str, content: str) -> str:
    return f"Written {len(content)} bytes to {path}"


def simulate_delete_file(path: str) -> str:
    raise RuntimeError("Simulated failure: disk I/O error")


def main() -> None:
    print("=== Multi-Tool Agent with Policies & Circuit Breakers ===\n")

    # Define policies
    read_policy = Policy(
        name="read_only",
        allowed_tools=frozenset({"read_file", "list_dir", "search"}),
        max_risk_score=0.5,
    )
    write_policy = Policy(
        name="write_restricted",
        denied_tools=frozenset({"delete_file", "execute_command"}),
        max_risk_score=0.8,
    )
    engine = PolicyEngine([read_policy, write_policy])

    # Circuit breaker registry
    registry = BreakerRegistry(default_failure_threshold=2, default_reset_timeout=5.0)

    # Audit log
    log = TamperEvidentLog()

    # Test cases
    actions = [
        AgentAction(tool_name="read_file", parameters={"path": "/tmp/data.json"}, risk_score=0.1),
        AgentAction(tool_name="write_file", parameters={"path": "/tmp/out.txt", "content": "hello"}, risk_score=0.6),
        AgentAction(tool_name="delete_file", parameters={"path": "/tmp/important.db"}, risk_score=0.9),
        AgentAction(tool_name="read_file", parameters={"path": "/etc/shadow"}, risk_score=0.7),
    ]

    handlers = {
        "read_file": simulate_read_file,
        "write_file": simulate_write_file,
        "delete_file": simulate_delete_file,
    }

    for action in actions:
        print(f"--- Action: {action.tool_name} (risk={action.risk_score}) ---")

        # Policy check
        decision = engine.evaluate(action)
        log.append("policy_check", {"action": action.tool_name, "allowed": decision.allowed, "reason": decision.reason})

        if not decision.allowed:
            print(f"  BLOCKED by policy '{decision.policy_name}': {decision.reason}")
            continue

        # Circuit breaker check
        breaker = registry.get(action.tool_name)
        handler = handlers.get(action.tool_name)
        if handler is None:
            print(f"  SKIPPED: no handler")
            continue

        try:
            result = breaker.call(handler, **action.parameters)
            print(f"  SUCCESS: {result}")
            log.append("action_success", {"action": action.tool_name})
        except CircuitOpenError as e:
            print(f"  CIRCUIT OPEN: {e}")
            log.append("circuit_open", {"action": action.tool_name})
        except Exception as e:
            print(f"  FAILED: {e}")
            log.append("action_failed", {"action": action.tool_name, "error": str(e)})

    # Print final status
    print(f"\n=== Final Status ===")
    print(f"Audit log entries: {log.size}")
    print(f"Log integrity: {log.verify_integrity()[0]}")
    print(f"Breaker status: {registry.status()}")


if __name__ == "__main__":
    main()
