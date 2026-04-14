"""Tests for the prune_archival MCP tool."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from handlers.processing import _helpers as processing_helpers  # noqa: E402
from handlers.processing import audio as audio_mod  # noqa: E402


def test_prune_archival_noop_when_directory_missing(tmp_path: Path) -> None:
    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.prune_archival("test-album"))

    result = json.loads(result_json)
    assert "error" not in result
    assert result["kept"] == []
    assert result["removed"] == []


def test_prune_archival_removes_all_when_keep_is_zero(tmp_path: Path) -> None:
    archival_dir = tmp_path / "archival"
    archival_dir.mkdir()
    for name in ("01-old.wav", "02-old.wav"):
        (archival_dir / name).write_bytes(b"")

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.prune_archival("test-album", keep=0))

    result = json.loads(result_json)
    assert sorted(result["removed"]) == ["01-old.wav", "02-old.wav"]
    assert result["kept"] == []
    # Directory is empty
    assert not any(archival_dir.iterdir())


def test_prune_archival_keeps_latest_n_by_mtime(tmp_path: Path) -> None:
    archival_dir = tmp_path / "archival"
    archival_dir.mkdir()
    # Create files with increasing mtimes
    for name in ("a.wav", "b.wav", "c.wav", "d.wav"):
        (archival_dir / name).write_bytes(b"")
        time.sleep(0.01)

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.prune_archival("test-album", keep=2))

    result = json.loads(result_json)
    # "c.wav" and "d.wav" are the two newest
    assert sorted(result["kept"]) == ["c.wav", "d.wav"]
    assert sorted(result["removed"]) == ["a.wav", "b.wav"]
    # Verify filesystem matches
    remaining = sorted(p.name for p in archival_dir.iterdir())
    assert remaining == ["c.wav", "d.wav"]


def test_prune_archival_keep_exceeds_count_is_noop(tmp_path: Path) -> None:
    archival_dir = tmp_path / "archival"
    archival_dir.mkdir()
    for name in ("a.wav", "b.wav"):
        (archival_dir / name).write_bytes(b"")

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.prune_archival("test-album", keep=10))

    result = json.loads(result_json)
    assert sorted(result["kept"]) == ["a.wav", "b.wav"]
    assert result["removed"] == []


def test_prune_archival_negative_keep_treated_as_zero(tmp_path: Path) -> None:
    archival_dir = tmp_path / "archival"
    archival_dir.mkdir()
    (archival_dir / "x.wav").write_bytes(b"")

    def _fake_resolve(slug: str, *_: object, **__: object) -> tuple[str | None, Path]:
        return None, tmp_path

    with patch.object(processing_helpers, "_resolve_audio_dir", _fake_resolve):
        result_json = asyncio.run(audio_mod.prune_archival("test-album", keep=-5))

    result = json.loads(result_json)
    assert result["removed"] == ["x.wav"]
    assert result["kept"] == []
