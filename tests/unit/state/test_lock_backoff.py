"""Tests for lock acquisition with exponential backoff."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.state.indexer import _acquire_lock_with_timeout, _flock_nb, _funlock


class TestAcquireLockWithTimeout:
    """Tests for _acquire_lock_with_timeout()."""

    def test_acquires_immediately_when_unlocked(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        with open(lock_file, "r+", encoding="utf-8") as fd:
            _acquire_lock_with_timeout(fd, timeout=2)

    def test_timeout_raises_when_lock_held(self, tmp_path: Path) -> None:
        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        holder = open(lock_file, "r+", encoding="utf-8")
        _flock_nb(holder)
        try:
            with open(lock_file, "r+", encoding="utf-8") as contender:
                with pytest.raises(TimeoutError, match="Could not acquire state lock"):
                    _acquire_lock_with_timeout(contender, timeout=0.5)
        finally:
            _funlock(holder)
            holder.close()

    def test_no_mtime_check(self, tmp_path: Path) -> None:
        """Verify stale detection via mtime was removed."""
        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        import os
        old_time = time.time() - 300
        os.utime(lock_file, (old_time, old_time))
        holder = open(lock_file, "r+", encoding="utf-8")
        _flock_nb(holder)
        try:
            with open(lock_file, "r+", encoding="utf-8") as contender:
                with pytest.raises(TimeoutError):
                    _acquire_lock_with_timeout(contender, timeout=0.5)
        finally:
            _funlock(holder)
            holder.close()

    def test_acquires_after_holder_releases(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The backoff loop retries and succeeds once the holder lets go.

        The releasing thread is sequenced by an ``Event`` the contender's own
        retry sets, not by ``time.sleep(0.3)`` racing the backoff schedule
        (0.05 → 0.1 → 0.2 → 0.4 → 0.8): under load the sleeping releaser could
        be descheduled past the final retry and the contender would time out
        blaming the lock code. Here the release cannot happen *before* a failed
        retry is observed, and the acquisition cannot happen before the
        release — a happens-before chain with no wall-clock dependency.
        """
        import threading

        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        holder = open(lock_file, "r+", encoding="utf-8")
        _flock_nb(holder)

        # The lock is genuinely held: an independent handle cannot take it.
        with open(lock_file, "r+", encoding="utf-8") as probe:
            with pytest.raises(OSError):
                _flock_nb(probe)

        import tools.state.indexer as indexer

        real_flock_nb = indexer._flock_nb
        attempts = 0
        retried = threading.Event()

        def counting_flock_nb(fd: object) -> None:
            nonlocal attempts
            attempts += 1
            if attempts > 1:
                # The contender has failed at least once and is in the
                # backoff loop — only now is releasing meaningful.
                retried.set()
            real_flock_nb(fd)

        monkeypatch.setattr(indexer, "_flock_nb", counting_flock_nb)

        released = threading.Event()

        def release_when_contender_has_retried() -> None:
            assert retried.wait(timeout=10), "contender never retried the lock"
            _funlock(holder)
            holder.close()
            released.set()

        t = threading.Thread(target=release_when_contender_has_retried)
        t.start()
        try:
            with open(lock_file, "r+", encoding="utf-8") as contender:
                _acquire_lock_with_timeout(contender, timeout=30)

                # The contender really owns the lock now: a third, independent
                # handle must be refused. Without this, the test would pass
                # even if _acquire_lock_with_timeout() did nothing at all.
                with open(lock_file, "r+", encoding="utf-8") as after:
                    with pytest.raises(OSError):
                        _flock_nb(after)

                assert released.is_set(), "acquired before the holder released"
                # Acquisition came from a retry, not the first attempt, so the
                # backoff loop itself is exercised.
                assert attempts >= 2, f"expected a retry, saw {attempts} attempt(s)"
        finally:
            t.join(timeout=10)
            assert not t.is_alive()
