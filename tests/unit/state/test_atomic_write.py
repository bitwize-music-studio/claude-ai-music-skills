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

import handlers._atomic as _atomic
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


class TestWindowsReplaceRetry:
    """atomic_write_text must retry os.replace on transient Windows sharing violations.

    On Windows, os.replace over a markdown file another process holds open (an
    editor, an antivirus scanner, OneDrive sync) raises PermissionError WinError
    5 / 32. POSIX rename-over-open never hits this. These tests force the Windows
    path deterministically on Linux by monkeypatching the module's ``sys.platform``
    and ``os.replace`` — mirroring the #488 retry tests in test_indexer.py.
    """

    @staticmethod
    def _sharing_violation(winerror: int = 5) -> PermissionError:
        # ``winerror`` only exists on Windows OSErrors; setting it explicitly
        # makes getattr(e, "winerror", None) return it on Linux too.
        err = PermissionError("Access is denied")
        err.winerror = winerror  # type: ignore[attr-defined]
        return err

    def test_retries_then_succeeds_on_windows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "README.md"
        target.write_text("original", encoding="utf-8")
        monkeypatch.setattr(_atomic.sys, "platform", "win32")
        monkeypatch.setattr(_atomic.time, "sleep", lambda *_: None)

        real_replace = os.replace
        calls = {"n": 0}
        fail_times = 3

        def flaky_replace(src: str, dst: str) -> None:
            calls["n"] += 1
            if calls["n"] <= fail_times:
                raise self._sharing_violation(32)  # ERROR_SHARING_VIOLATION
            real_replace(src, dst)

        monkeypatch.setattr(_atomic.os, "replace", flaky_replace)

        atomic_write_text(target, "new content")

        assert calls["n"] == fail_times + 1
        assert target.read_text(encoding="utf-8") == "new content"
        assert list(tmp_path.glob(".README_*.tmp")) == []

    def test_retries_sharing_violation_winerror_5(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "IDEAS.md"
        monkeypatch.setattr(_atomic.sys, "platform", "win32")
        monkeypatch.setattr(_atomic.time, "sleep", lambda *_: None)

        real_replace = os.replace
        calls = {"n": 0}

        def flaky_replace(src: str, dst: str) -> None:
            calls["n"] += 1
            if calls["n"] == 1:
                raise self._sharing_violation(5)  # ERROR_ACCESS_DENIED
            real_replace(src, dst)

        monkeypatch.setattr(_atomic.os, "replace", flaky_replace)

        atomic_write_text(target, "idea list")

        assert calls["n"] == 2
        assert target.read_text(encoding="utf-8") == "idea list"

    def test_non_sharing_oserror_not_retried_on_windows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-sharing OSError (winerror 13) propagates immediately, no retry."""
        target = tmp_path / "test.md"
        monkeypatch.setattr(_atomic.sys, "platform", "win32")
        monkeypatch.setattr(
            _atomic.time,
            "sleep",
            lambda *_: pytest.fail("must not retry a non-sharing error"),
        )

        calls = {"n": 0}

        def fail_other(src: str, dst: str) -> None:
            calls["n"] += 1
            err = OSError("permission denied")
            err.winerror = 13  # ERROR_INVALID_DATA — not a sharing violation
            raise err

        monkeypatch.setattr(_atomic.os, "replace", fail_other)

        with pytest.raises(OSError):
            atomic_write_text(target, "new content")
        assert calls["n"] == 1

    def test_plain_oserror_not_retried_on_windows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An OSError with no winerror at all is not a sharing violation."""
        target = tmp_path / "test.md"
        monkeypatch.setattr(_atomic.sys, "platform", "win32")
        monkeypatch.setattr(
            _atomic.time,
            "sleep",
            lambda *_: pytest.fail("must not retry a plain OSError"),
        )

        calls = {"n": 0}

        def fail_plain(src: str, dst: str) -> None:
            calls["n"] += 1
            raise OSError("cross-device link")

        monkeypatch.setattr(_atomic.os, "replace", fail_plain)

        with pytest.raises(OSError, match="cross-device link"):
            atomic_write_text(target, "new content")
        assert calls["n"] == 1

    def test_gives_up_and_raises_after_budget_on_windows(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Budget exhaustion raises — the write is never silently swallowed."""
        target = tmp_path / "test.md"
        target.write_text("original", encoding="utf-8")
        monkeypatch.setattr(_atomic.sys, "platform", "win32")
        sleeps: list[float] = []
        monkeypatch.setattr(_atomic.time, "sleep", sleeps.append)

        calls = {"n": 0}

        def always_fail(src: str, dst: str) -> None:
            calls["n"] += 1
            raise self._sharing_violation(32)

        monkeypatch.setattr(_atomic.os, "replace", always_fail)

        with pytest.raises(PermissionError):
            atomic_write_text(target, "new content")

        # Bounded: retried (not a single attempt) but did not loop forever.
        assert calls["n"] > 1, "expected bounded retries, not a single attempt"
        assert calls["n"] == _atomic._REPLACE_RETRY_ATTEMPTS
        # Slept only between attempts; total retry window stays ~1s.
        assert len(sleeps) == _atomic._REPLACE_RETRY_ATTEMPTS - 1
        assert sum(sleeps) <= 1.0
        # Original preserved and the temp file cleaned up by the existing finally.
        assert target.read_text(encoding="utf-8") == "original"
        assert list(tmp_path.iterdir()) == [target]

    def test_posix_does_not_retry_replace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """POSIX behavior is byte-for-byte unchanged: replace runs exactly once."""
        target = tmp_path / "test.md"
        monkeypatch.setattr(_atomic.sys, "platform", "linux")
        monkeypatch.setattr(
            _atomic.time,
            "sleep",
            lambda *_: pytest.fail("must not retry os.replace on POSIX"),
        )

        calls = {"n": 0}

        def fail_once(src: str, dst: str) -> None:
            calls["n"] += 1
            # Even with a winerror set, POSIX must re-raise on the first failure.
            raise self._sharing_violation(5)

        monkeypatch.setattr(_atomic.os, "replace", fail_once)

        with pytest.raises(PermissionError):
            atomic_write_text(target, "new content")
        assert calls["n"] == 1
