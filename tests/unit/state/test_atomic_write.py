"""Tests for atomic file write utility."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers._atomic import atomic_write_text


class TestAtomicWriteText:
    """Tests for atomic_write_text()."""

    def test_writes_content(self, tmp_path: Path) -> None:
        target = tmp_path / "test.md"
        atomic_write_text(target, "hello world")
        assert target.read_text(encoding="utf-8") == "hello world"

    def test_preserves_original_on_flush_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "test.md"
        target.write_text("original", encoding="utf-8")

        with patch("os.fsync", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                atomic_write_text(target, "new content")

        assert target.read_text(encoding="utf-8") == "original"

    def test_no_temp_file_left_on_failure(self, tmp_path: Path) -> None:
        target = tmp_path / "test.md"
        target.write_text("original", encoding="utf-8")

        with patch("os.fsync", side_effect=OSError("disk full")):
            with pytest.raises(OSError):
                atomic_write_text(target, "new content")

        files = list(tmp_path.iterdir())
        assert files == [target], f"Leftover temp files: {files}"

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        target = tmp_path / "sub" / "dir" / "test.md"
        atomic_write_text(target, "nested")
        assert target.read_text(encoding="utf-8") == "nested"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "test.md"
        target.write_text("old", encoding="utf-8")
        atomic_write_text(target, "new")
        assert target.read_text(encoding="utf-8") == "new"

    def test_writes_utf8(self, tmp_path: Path) -> None:
        target = tmp_path / "test.md"
        atomic_write_text(target, "café ☃")
        assert target.read_text(encoding="utf-8") == "café ☃"
