"""Atomic file write utility.

Prevents data corruption from interrupted writes by writing to a temp file
in the same directory, fsyncing, then atomically replacing the target.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write *content* to *path* atomically.

    Creates a temp file in the same directory as *path*, writes content,
    fsyncs to disk, then uses ``os.replace()`` for an atomic rename.
    The original file is preserved if anything fails mid-write.

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
        os.replace(str(tmp_path), str(path))
        tmp_path = None  # Rename succeeded, nothing to clean up
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
