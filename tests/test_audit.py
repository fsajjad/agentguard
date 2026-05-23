import tempfile
from pathlib import Path

import pytest

from agentguard.audit.log import TamperEvidentLog, LogEntry, GENESIS_HASH
from agentguard.audit.serializer import LogSerializer
from agentguard.audit.checkpoint import CheckpointManager


class TestTamperEvidentLog:
    def test_append_creates_entry(self, audit_log):
        entry = audit_log.append("test_event", {"key": "value"})
        assert entry.sequence == 0
        assert entry.event_type == "test_event"
        assert entry.prev_hash == GENESIS_HASH
        assert len(entry.entry_hash) == 64

    def test_chain_links_entries(self, audit_log):
        e1 = audit_log.append("event_1", {})
        e2 = audit_log.append("event_2", {})
        assert e2.prev_hash == e1.entry_hash

    def test_verify_integrity_valid(self, audit_log):
        for i in range(10):
            audit_log.append(f"event_{i}", {"index": i})
        is_valid, broken_at = audit_log.verify_integrity()
        assert is_valid is True
        assert broken_at is None

    def test_verify_integrity_detects_tampering(self, audit_log):
        for i in range(5):
            audit_log.append(f"event_{i}", {"index": i})

        # Tamper with an entry's payload
        tampered = LogEntry(
            sequence=2,
            timestamp=audit_log.get_entry(2).timestamp,
            event_type="TAMPERED",
            payload={"hacked": True},
            prev_hash=audit_log.get_entry(2).prev_hash,
        )
        audit_log._entries[2] = tampered

        is_valid, broken_at = audit_log.verify_integrity()
        assert is_valid is False
        assert broken_at == 3

    def test_root_hash_changes(self, audit_log):
        h1 = audit_log.root_hash
        audit_log.append("event", {})
        h2 = audit_log.root_hash
        assert h1 != h2

    def test_iteration(self, audit_log):
        for i in range(3):
            audit_log.append(f"event_{i}", {})
        entries = list(audit_log)
        assert len(entries) == 3
        assert entries[0].sequence == 0
        assert entries[2].sequence == 2


class TestLogSerializer:
    def test_save_and_load_compressed(self, audit_log):
        for i in range(5):
            audit_log.append(f"event_{i}", {"data": f"payload_{i}"})

        with tempfile.NamedTemporaryFile(suffix=".json.gz", delete=False) as f:
            path = Path(f.name)

        LogSerializer.save(audit_log, path, compress=True)
        loaded = LogSerializer.load(path, compress=True)

        assert loaded.size == 5
        assert loaded.root_hash == audit_log.root_hash
        path.unlink()

    def test_save_and_load_uncompressed(self, audit_log):
        for i in range(3):
            audit_log.append(f"event_{i}", {"data": i})

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        LogSerializer.save(audit_log, path, compress=False)
        loaded = LogSerializer.load(path, compress=False)

        assert loaded.size == 3
        assert loaded.root_hash == audit_log.root_hash
        path.unlink()

    def test_load_detects_tampering(self, audit_log):
        for i in range(3):
            audit_log.append(f"event_{i}", {})

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        LogSerializer.save(audit_log, path, compress=False)

        # Tamper with the file
        import json
        data = json.loads(path.read_text())
        data["entries"][1]["payload"] = {"tampered": True}
        path.write_text(json.dumps(data))

        with pytest.raises(ValueError, match="hash mismatch"):
            LogSerializer.load(path, compress=False)
        path.unlink()


class TestCheckpointManager:
    def test_checkpoint_creation(self, audit_log):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                log=audit_log,
                checkpoint_dir=Path(tmpdir),
                interval=5,
            )

            for i in range(5):
                audit_log.append(f"event_{i}", {})

            path = manager.maybe_checkpoint()
            assert path is not None
            assert path.exists()

    def test_no_checkpoint_below_interval(self, audit_log):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                log=audit_log,
                checkpoint_dir=Path(tmpdir),
                interval=10,
            )

            for i in range(3):
                audit_log.append(f"event_{i}", {})

            path = manager.maybe_checkpoint()
            assert path is None

    def test_verify_against_checkpoint(self, audit_log):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CheckpointManager(
                log=audit_log,
                checkpoint_dir=Path(tmpdir),
                interval=3,
            )

            for i in range(5):
                audit_log.append(f"event_{i}", {})

            cp_path = manager.force_checkpoint()
            assert manager.verify_against_checkpoint(cp_path) is True

            # Add more entries — checkpoint should still verify
            for i in range(5, 10):
                audit_log.append(f"event_{i}", {})

            assert manager.verify_against_checkpoint(cp_path) is True
