"""Archival-dir helpers for the mastering pipeline (#290 phase 4).

Pure-Python, no MCP coupling. The archival stage of ``master_album``
consumes ``prune_archival_orphans`` before writing new 32-bit float
copies, so the archival dir stays a mirror of ``mastered/`` — re-masters
that drop or rename tracks don't leave stale entries behind.
"""

from __future__ import annotations

from pathlib import Path


def prune_archival_orphans(
    archival_dir: Path,
    expected_names: set[str],
) -> list[str]:
    """Remove files in ``archival_dir`` whose basename is not in ``expected_names``.

    Args:
        archival_dir: The archival directory path. Missing directory is
            a silent no-op (the caller hasn't created it yet).
        expected_names: The set of basenames that SHOULD remain — typically
            the filenames in ``mastered/``.

    Returns:
        Sorted list of pruned basenames. Empty when nothing was removed.
        Does not raise on individual unlink failures — callers that want
        to surface errors should check ``expected_names`` against the
        directory contents afterwards.
    """
    if not archival_dir.is_dir():
        return []
    pruned: list[str] = []
    for entry in archival_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.name in expected_names:
            continue
        try:
            entry.unlink()
            pruned.append(entry.name)
        except OSError:
            # Caller-level verification catches leftovers; keep the helper
            # pure.
            continue
    return sorted(pruned)
