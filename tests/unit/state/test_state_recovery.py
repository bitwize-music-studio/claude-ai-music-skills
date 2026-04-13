"""Tests for corrupted state.json recovery."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.state import indexer


class TestReadStateRecovery:
    """Tests for read_state() corruption handling."""

    def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        with patch.object(indexer, "STATE_FILE", tmp_path / "missing.json"):
            result = indexer.read_state()
        assert result is None

    def test_reads_valid_state(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text('{"albums": {}}', encoding="utf-8")
        with patch.object(indexer, "STATE_FILE", state_file):
            result = indexer.read_state()
        assert result == {"albums": {}}

    def test_corrupted_json_creates_backup(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text("{invalid json!!!", encoding="utf-8")

        with patch.object(indexer, "STATE_FILE", state_file), \
             patch.object(indexer, "CACHE_DIR", tmp_path):
            result = indexer.read_state()

        # Should return empty dict (not None)
        assert result == {}

        # Should have created a .corrupt backup
        backups = list(tmp_path.glob("state.*.corrupt"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "{invalid json!!!"

    def test_corrupted_json_logs_error(self, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text("{bad", encoding="utf-8")

        with patch.object(indexer, "STATE_FILE", state_file), \
             patch.object(indexer, "CACHE_DIR", tmp_path), \
             caplog.at_level(logging.ERROR):
            indexer.read_state()

        assert any("corrupt" in r.message.lower() or "backup" in r.message.lower() for r in caplog.records)

    def test_backup_failure_still_returns_empty(self, tmp_path: Path) -> None:
        state_file = tmp_path / "state.json"
        state_file.write_text("{bad", encoding="utf-8")

        with patch.object(indexer, "STATE_FILE", state_file), \
             patch.object(indexer, "CACHE_DIR", tmp_path), \
             patch("shutil.copy2", side_effect=OSError("disk full")):
            result = indexer.read_state()

        assert result == {}
