from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from agentguard.audit.log import TamperEvidentLog


class CheckpointManager:
    """Periodically saves root hash checkpoints for external verification."""

    def __init__(
        self,
        log: TamperEvidentLog,
        checkpoint_dir: Path,
        interval: int = 100,
    ) -> None:
        self._log = log
        self._checkpoint_dir = checkpoint_dir
        self._interval = interval
        self._last_checkpoint_size = 0
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def maybe_checkpoint(self) -> Path | None:
        """Create a checkpoint if enough entries have accumulated since last one."""
        if (self._log.size - self._last_checkpoint_size) >= self._interval:
            return self.force_checkpoint()
        return None

    def force_checkpoint(self) -> Path:
        """Create a checkpoint immediately."""
        checkpoint = {
            "timestamp": time.time(),
            "root_hash": self._log.root_hash,
            "entry_count": self._log.size,
            "sequence": self._log.size - 1 if self._log.size > 0 else -1,
        }

        filename = f"checkpoint_{self._log.size:08d}.json"
        path = self._checkpoint_dir / filename
        path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")

        self._last_checkpoint_size = self._log.size
        return path

    def verify_against_checkpoint(self, checkpoint_path: Path) -> bool:
        """Verify current log state against a stored checkpoint."""
        data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        expected_count = data["entry_count"]

        if self._log.size < expected_count:
            return False

        if expected_count == 0:
            return True

        entry = self._log.get_entry(expected_count - 1)
        return entry.entry_hash == data["root_hash"]

    def list_checkpoints(self) -> list[Path]:
        """List all checkpoint files in order."""
        return sorted(self._checkpoint_dir.glob("checkpoint_*.json"))
