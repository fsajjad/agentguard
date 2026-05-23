"""Basic example: A single tool with safety guards."""

from agentguard import (
    agent_guard,
    ViolationError,
    TamperEvidentLog,
)
from agentguard.contracts.conditions import no_shell_injection, no_pii_in_output


audit_log = TamperEvidentLog()


@agent_guard(
    pre=[no_shell_injection],
    post=[no_pii_in_output],
    on_violation=lambda err: f"BLOCKED: {err.rule} — {err.context}",
)
def read_file(path: str) -> str:
    """Simulated file read tool."""
    return f"Contents of {path}: Hello, World!"


def main() -> None:
    print("=== Basic Guarded Agent Example ===\n")

    # Safe call
    result = read_file(path="/tmp/readme.txt")
    print(f"Safe call result: {result}")
    audit_log.append("tool_call", {"tool": "read_file", "path": "/tmp/readme.txt", "status": "success"})

    # Blocked call (shell injection attempt)
    result = read_file(path="/tmp/file; rm -rf /")
    print(f"Injection attempt result: {result}")
    audit_log.append("tool_call", {"tool": "read_file", "path": "/tmp/file; rm -rf /", "status": "blocked"})

    # Verify audit log integrity
    is_valid, _ = audit_log.verify_integrity()
    print(f"\nAudit log entries: {audit_log.size}")
    print(f"Audit log integrity valid: {is_valid}")
    print(f"Root hash: {audit_log.root_hash}")


if __name__ == "__main__":
    main()
