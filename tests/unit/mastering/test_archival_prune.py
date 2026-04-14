"""Tests for tools/mastering/archival.py prune helper (#290 phase 4, PR #304 A5)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.archival import prune_archival_orphans  # noqa: E402


def test_prune_removes_orphans_keeps_matched(tmp_path: Path) -> None:
    archival = tmp_path / "archival"
    archival.mkdir()
    (archival / "01-keep.wav").write_bytes(b"keep")
    (archival / "02-keep.wav").write_bytes(b"keep")
    (archival / "old-orphan.wav").write_bytes(b"orphan")

    pruned = prune_archival_orphans(
        archival, expected_names={"01-keep.wav", "02-keep.wav"}
    )

    assert pruned == ["old-orphan.wav"]
    assert (archival / "01-keep.wav").exists()
    assert (archival / "02-keep.wav").exists()
    assert not (archival / "old-orphan.wav").exists()


def test_prune_on_empty_archival_dir_is_noop(tmp_path: Path) -> None:
    archival = tmp_path / "archival"
    archival.mkdir()
    assert prune_archival_orphans(archival, expected_names={"01-track.wav"}) == []


def test_prune_on_missing_archival_dir_is_noop(tmp_path: Path) -> None:
    # Called before the stage creates the dir — should not raise.
    assert prune_archival_orphans(
        tmp_path / "does-not-exist", expected_names={"01-track.wav"}
    ) == []


def test_prune_skips_subdirectories(tmp_path: Path) -> None:
    """Nested dirs (e.g. archival/2024-01/) are left alone — the helper
    only removes files."""
    archival = tmp_path / "archival"
    archival.mkdir()
    (archival / "keep.wav").write_bytes(b"keep")
    (archival / "subdir").mkdir()
    (archival / "subdir" / "something.wav").write_bytes(b"nested")

    pruned = prune_archival_orphans(archival, expected_names={"keep.wav"})
    assert pruned == []  # subdir is not a file → skipped
    assert (archival / "subdir" / "something.wav").exists()


def test_prune_returns_sorted_names(tmp_path: Path) -> None:
    """Deterministic ordering makes the handler's JSON output stable."""
    archival = tmp_path / "archival"
    archival.mkdir()
    for name in ("z.wav", "a.wav", "m.wav"):
        (archival / name).write_bytes(b"x")
    pruned = prune_archival_orphans(archival, expected_names=set())
    assert pruned == ["a.wav", "m.wav", "z.wav"]
