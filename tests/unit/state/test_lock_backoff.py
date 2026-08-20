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

    def test_clock_crossing_the_deadline_mid_iteration_still_raises_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A deadline crossed *between* the guard and the sleep must time out.

        Each backoff iteration reads the clock twice: once for the
        ``time.monotonic() >= deadline`` guard, and once more to compute the
        remaining budget for ``time.sleep()``. Between those two reads the
        process can be descheduled — a loaded CI runner, a GC pause, an xdist
        worker losing its slice — and the deadline can pass. The remaining
        budget is then *negative*, and ``time.sleep()`` rejects a negative
        argument with ``ValueError``.

        That would surface as a raw ``ValueError: sleep length must be
        non-negative`` escaping ``read_state``/``write_state``, where every
        caller is written to expect ``TimeoutError`` — a lock contention that
        reports itself as a bug in the indexer. Rare, load-dependent, and
        exactly the kind of thing that only ever reproduces in CI.

        The window is forced rather than raced: the module's ``time`` is
        swapped for a scripted clock, so the guard sees 0.9 (under the 1.0
        deadline, loop continues) and the very next read sees 1.5 (past it,
        remaining budget -0.5). The fake ``sleep`` re-raises the stdlib's own
        ``ValueError`` on a negative argument, so this test fails on the
        unclamped code for the real reason rather than by assertion.
        """
        import errno
        import types

        import tools.state.indexer as indexer

        # 0.0 -> deadline = 1.0; 0.9 -> guard passes; 1.5 -> budget is -0.5;
        # 1.6 -> next guard trips and the loop must raise TimeoutError.
        readings = iter([0.0, 0.9, 1.5, 1.6])
        slept: list[float] = []

        def fake_monotonic() -> float:
            return next(readings)

        def fake_sleep(seconds: float) -> None:
            # Mirrors CPython's own check, so the unclamped code fails here.
            if seconds < 0:
                raise ValueError("sleep length must be non-negative")
            slept.append(seconds)

        monkeypatch.setattr(
            indexer,
            "time",
            types.SimpleNamespace(monotonic=fake_monotonic, sleep=fake_sleep),
        )

        def always_contended(fd: object) -> None:
            raise OSError(errno.EAGAIN, "Resource temporarily unavailable")

        monkeypatch.setattr(indexer, "_flock_nb", always_contended)

        lock_file = tmp_path / "test.lock"
        lock_file.touch()
        with open(lock_file, "r+", encoding="utf-8") as contender:
            with pytest.raises(TimeoutError, match="Could not acquire state lock"):
                indexer._acquire_lock_with_timeout(contender, timeout=1.0)

        # The clamp turns the negative budget into a no-op sleep, not a longer
        # one: a `max(0.0, ...)` that accidentally became `abs()` would still
        # avoid the ValueError while sleeping past the deadline.
        assert slept == [0.0], f"expected one clamped no-op sleep, got {slept}"

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

        The releaser's ordering and its cleanup budget carry their own
        reasoning — see the comments on the thread body below.
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
            try:
                # 30 s, matching the contender's own timeout below. A shorter
                # budget here is not "safer": the releaser would give up first,
                # never unlock, and the contender would then time out — turning
                # a slow runner into a failure that blames the lock code.
                assert retried.wait(timeout=30), "contender never retried the lock"
            finally:
                # In a finally so the holder is released and closed on EVERY
                # exit path. An assert inside a thread does not reach pytest,
                # so without this a failed wait left the file locked forever:
                # the contender hung out its full timeout, holder was never
                # closed, and on Windows tmp_path teardown then failed on the
                # open handle — three confusing failures downstream of one.
                #
                # Flag BEFORE unlock, deliberately: the contender can acquire
                # the instant _funlock() lands and reach its
                # `released.is_set()` assert before this thread is scheduled
                # again, so setting the flag afterwards races that assert (the
                # 2026-08-17 nightly failure). Acquisition requires the unlock,
                # and the unlock requires the flag.
                released.set()
                _funlock(holder)
                holder.close()

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
            # Unblock the releaser however the body exited. On the happy path
            # this is a no-op (counting_flock_nb already set it); on a failure
            # path the thread is still parked on retried.wait and would
            # otherwise hold the join for its full 30 s before its cleanup ran.
            retried.set()
            t.join(timeout=10)
            assert not t.is_alive()
