from __future__ import annotations

import gzip
import json
from pathlib import Path
from typing import Any

from agentguard.audit.log import TamperEvidentLog, LogEntry, GENESIS_HASH


class LogSerializer:
    """Handles persistence of TamperEvidentLog to disk."""

    @staticmethod
    def save(log: TamperEvidentLog, path: Path, compress: bool = True) -> None:
        data = {
            "version": 1,
            "root_hash": log.root_hash,
            "entry_count": log.size,
            "entries": [entry.to_dict() for entry in log],
        }
        content = json.dumps(data, default=str)

        if compress:
            with gzip.open(path, "wt", encoding="utf-8") as f:
                f.write(content)
        else:
            path.write_text(content, encoding="utf-8")

    @staticmethod
    def load(path: Path, compress: bool = True) -> TamperEvidentLog:
        """Load and verify a log from disk.

        Raises:
            ValueError: If the log fails integrity verification.
        """
        if compress:
            with gzip.open(path, "rt", encoding="utf-8") as f:
                data = json.loads(f.read())
        else:
            data = json.loads(path.read_text(encoding="utf-8"))

        log = TamperEvidentLog()

        for record in data["entries"]:
            entry = LogEntry(
                sequence=record["sequence"],
                timestamp=record["timestamp"],
                event_type=record["event_type"],
                payload=record["payload"],
                prev_hash=record["prev_hash"],
            )
            if entry.entry_hash != record["entry_hash"]:
                raise ValueError(
                    f"Entry {record['sequence']} hash mismatch — possible tampering"
                )
            log._entries.append(entry)
            log._last_hash = entry.entry_hash

        is_valid, broken_at = log.verify_integrity()
        if not is_valid:
            raise ValueError(
                f"Hash chain broken at entry {broken_at} — possible tampering"
            )

        if log.root_hash != data["root_hash"]:
            raise ValueError("Root hash mismatch — log may have been truncated")

        return log
