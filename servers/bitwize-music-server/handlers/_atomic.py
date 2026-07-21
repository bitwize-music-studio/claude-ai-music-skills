"""Atomic file write utility.

Prevents data corruption from interrupted writes by writing to a temp file
in the same directory, fsyncing, then atomically replacing the target.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

# Bounded retry budget for os.replace on Windows sharing violations.
#
# Source of truth: tools/state/indexer.py (_retry_on_windows_sharing_violation,
# added in PR #488) — the semantics here are deliberately identical. The logic is
# duplicated rather than imported to keep this module a zero-dependency leaf: it
# is imported both by handlers/* and, from the other direction, by
# tools/mastering/signature_persistence.py, which injects only the server dir on
# sys.path. Importing tools.state.indexer here would invert that layering and pull
# a ~110-module transitive graph into every atomic write. Keep the two in sync.
#
# Windows enforces mandatory locking on open file handles, so os.replace over a
# target raises PermissionError with winerror 5 (ERROR_ACCESS_DENIED) or 32
# (ERROR_SHARING_VIOLATION) whenever another process holds it open — an editor
# with the README open, an antivirus scan, or a OneDrive/Dropbox sync pass.
# POSIX rename-over-open-file is atomic and never hits this, so retrying is
# Windows-only. Budget: 10 attempts with a 10ms backoff doubling to a 100ms cap
# keeps the total retry window under ~1s (9 sleeps sum to 650ms) — long enough to
# outlast a transient handle, short enough to fail loudly on a stuck file.
_REPLACE_RETRY_ATTEMPTS = 10
_REPLACE_RETRY_INITIAL_WAIT = 0.01  # 10ms
_REPLACE_RETRY_MAX_WAIT = 0.1  # 100ms per-sleep cap
_WINDOWS_SHARING_VIOLATION_ERRNOS = (5, 32)


def _atomic_replace_with_retry(src: str, dst: str) -> None:
    """Atomically replace *dst* with *src*, retrying Windows sharing violations.

    On POSIX this is a single ``os.replace``: an atomic rename never fails on an
    open target, so there is nothing transient to retry and the call runs exactly
    once. On Windows a concurrent open handle on *dst* makes ``os.replace`` raise
    ``PermissionError`` with ``winerror`` 5 or 32 until that handle closes; only
    those transient errors are retried, with a bounded backoff. Every other error
    (and the final attempt) propagates immediately, so a genuinely stuck file
    still fails loudly rather than being silently swallowed or misclassified.
    ``getattr(e, "winerror", ...)`` is platform-safe: the attribute only exists on
    Windows OSErrors.
    """
    if sys.platform == "win32":
        wait = _REPLACE_RETRY_INITIAL_WAIT
        for attempt in range(_REPLACE_RETRY_ATTEMPTS):
            try:
                os.replace(src, dst)
                return
            except OSError as e:
                transient = (
                    getattr(e, "winerror", None) in _WINDOWS_SHARING_VIOLATION_ERRNOS
                )
                if not transient or attempt == _REPLACE_RETRY_ATTEMPTS - 1:
                    raise
                time.sleep(wait)
                wait = min(wait * 2, _REPLACE_RETRY_MAX_WAIT)
    # POSIX: nothing transient to retry — run once and let errors propagate.
    # (Also the win32 fall-through, which the loop above never actually reaches
    # since its final attempt returns or raises; kept so mypy sees a return on
    # every path and matches how it skips the platform-guarded block on POSIX.)
    os.replace(src, dst)


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write *content* to *path* atomically.

    Creates a temp file in the same directory as *path*, writes content,
    fsyncs to disk, then uses ``os.replace()`` for an atomic rename.
    The original file is preserved if anything fails mid-write. On Windows the
    rename retries transient sharing violations (see
    :func:`_atomic_replace_with_retry`); on POSIX it runs exactly once.

    Args:
        path: Destination file path.
        content: Text content to write.
        encoding: Text encoding (default utf-8).

    Raises:
        OSError: If the write, fsync, or rename fails.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            suffix=".tmp",
            prefix=f".{path.stem}_",
            delete=False,
            encoding=encoding,
        ) as tmp_fd:
            tmp_path = Path(tmp_fd.name)
            tmp_fd.write(content)
            tmp_fd.flush()
            os.fsync(tmp_fd.fileno())
        _atomic_replace_with_retry(str(tmp_path), str(path))
        tmp_path = None  # Rename succeeded, nothing to clean up
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
