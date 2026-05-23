from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class GuardConfig:
    max_risk_score: float = 0.8
    require_approval_above: float = 0.75
    max_tool_calls_per_session: int = 50
    max_tokens_per_session: int = 100_000
    session_timeout_seconds: float = 300.0

    circuit_failure_threshold: int = 5
    circuit_reset_timeout: float = 60.0
    circuit_half_open_probes: int = 1

    audit_log_dir: Path = field(default_factory=lambda: Path("./audit_logs"))
    audit_compress: bool = True
    audit_checkpoint_interval: int = 100

    event_bus_max_queue: int = 10_000
