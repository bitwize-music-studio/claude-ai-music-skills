"""Tests for lock acquisition with exponential backoff."""

from __future__ import annotations

import errno
import fcntl
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.state.indexer import _acquire_lock_with_timeout


class TestAcquireLockWithTimeout:
    """Tests for _acquire_lock_with_timeout()."""

    def test_acquires_immediately_when_unlocked(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        with open(lock_file) as fd:
            _acquire_lock_with_timeout(fd, timeout=2)

    def test_timeout_raises_when_lock_held(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        holder = open(lock_file)
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with open(lock_file) as contender:
                with pytest.raises(TimeoutError, match="Could not acquire state lock"):
                    _acquire_lock_with_timeout(contender, timeout=0.5)
        finally:
            fcntl.flock(holder, fcntl.LOCK_UN)
            holder.close()

    def test_no_mtime_check(self, tmp_path: Path) -> None:
        """Verify stale detection via mtime was removed."""
        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        import os
        old_time = time.time() - 300
        os.utime(lock_file, (old_time, old_time))
        holder = open(lock_file)
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with open(lock_file) as contender:
                with pytest.raises(TimeoutError):
                    _acquire_lock_with_timeout(contender, timeout=0.5)
        finally:
            fcntl.flock(holder, fcntl.LOCK_UN)
            holder.close()

    def test_acquires_after_holder_releases(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        holder = open(lock_file)
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        import threading
        def release_after_delay():
            time.sleep(0.3)
            fcntl.flock(holder, fcntl.LOCK_UN)
            holder.close()
        t = threading.Thread(target=release_after_delay)
        t.start()
        with open(lock_file) as contender:
            _acquire_lock_with_timeout(contender, timeout=2)
        t.join()
