from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class LogEntry:
    sequence: int
    timestamp: float
    event_type: str
    payload: dict[str, Any]
    prev_hash: str
    entry_hash: str = field(init=False)

    def __post_init__(self) -> None:
        digest = self._compute_hash()
        object.__setattr__(self, "entry_hash", digest)

    def _compute_hash(self) -> str:
        content = json.dumps(
            {
                "sequence": self.sequence,
                "timestamp": self.timestamp,
                "event_type": self.event_type,
                "payload": self.payload,
                "prev_hash": self.prev_hash,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }


class TamperEvidentLog:
    """Append-only log with cryptographic hash chaining for tamper detection."""

    def __init__(self) -> None:
        self._entries: list[LogEntry] = []
        self._last_hash: str = GENESIS_HASH

    def append(self, event_type: str, payload: dict[str, Any]) -> LogEntry:
        entry = LogEntry(
            sequence=len(self._entries),
            timestamp=time.time(),
            event_type=event_type,
            payload=payload,
            prev_hash=self._last_hash,
        )
        self._entries.append(entry)
        self._last_hash = entry.entry_hash
        return entry

    def verify_integrity(self) -> tuple[bool, int | None]:
        """Verify the entire hash chain.

        Returns:
            Tuple of (is_valid, first_broken_index).
            If valid, returns (True, None).
        """
        prev = GENESIS_HASH
        for i, entry in enumerate(self._entries):
            if entry.prev_hash != prev:
                return False, i
            if entry._compute_hash() != entry.entry_hash:
                return False, i
            prev = entry.entry_hash
        return True, None

    @property
    def root_hash(self) -> str:
        return self._last_hash

    @property
    def size(self) -> int:
        return len(self._entries)

    def get_entry(self, index: int) -> LogEntry:
        return self._entries[index]

    def __iter__(self) -> Iterator[LogEntry]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)
