"""Built-in condition functions for use with @agent_guard."""

from __future__ import annotations

import re
from typing import Any

SHELL_INJECTION_PATTERNS = [";", "&&", "||", "|", "`", "$(", "${", "\n"]

PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),  # Email
    re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),  # Credit card
]


def no_shell_injection(**kwargs: Any) -> bool:
    for value in kwargs.values():
        if isinstance(value, str):
            if any(p in value for p in SHELL_INJECTION_PATTERNS):
                return False
    return True


def no_pii_in_output(result: Any) -> bool:
    if not isinstance(result, str):
        return True
    return not any(pattern.search(result) for pattern in PII_PATTERNS)


def max_output_length(max_len: int = 10_000):
    def check(result: Any) -> bool:
        if isinstance(result, str):
            return len(result) <= max_len
        return True
    check.__name__ = f"max_output_length_{max_len}"
    return check


def action_in_allowlist(allowlist: frozenset[str]):
    def check(tool_name: str = "", **kwargs: Any) -> bool:
        return tool_name in allowlist
    check.__name__ = "action_in_allowlist"
    return check


def action_not_in_denylist(denylist: frozenset[str]):
    def check(tool_name: str = "", **kwargs: Any) -> bool:
        return tool_name not in denylist
    check.__name__ = "action_not_in_denylist"
    return check


def risk_below_threshold(threshold: float = 0.8):
    def check(risk_score: float = 0.0, **kwargs: Any) -> bool:
        return risk_score <= threshold
    check.__name__ = f"risk_below_threshold_{threshold}"
    return check
