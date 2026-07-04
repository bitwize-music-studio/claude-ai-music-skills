#!/usr/bin/env python3
"""Unit tests for handlers/maintenance.py — reset, legacy cleanup, migration.

Covers the three public MCP tools:

    reset_mastering(album_slug, subfolders, dry_run) — delete mastered/polished
    cleanup_legacy_venvs(dry_run)                    — remove stale per-tool venvs
    migrate_audio_layout(album_slug, dry_run)        — move root WAVs into originals/

``migrate_audio_layout`` is the priority: prior to this file it had only
slug-validation coverage, so its behaviour (dry-run, real move, skip reasons,
all-vs-single album) is exercised in depth here. Every destructive path is
driven through ``dry_run`` or a ``tmp_path`` sandbox so nothing real is touched.

Follows the fixture/mocking style of test_handlers_streaming.py: mock
StateCache via ``_shared.cache``, an ``asyncio.run`` helper, and structured-JSON
assertions.

Usage:
    python -m pytest tests/unit/state/test_handlers_maintenance.py -v
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path for imports
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

# ---------------------------------------------------------------------------
# Mock MCP SDK if not installed (same pattern as test_handlers_streaming.py)
# ---------------------------------------------------------------------------

try:
    import mcp  # noqa: F401
except ImportError:

    class _FakeFastMCP:
        def __init__(self, name=""):
            self.name = name
            self._tools = {}

        def tool(self):
            def decorator(fn):
                self._tools[fn.__name__] = fn
                return fn
            return decorator

        def run(self, transport="stdio"):
            pass

    mcp_mod = types.ModuleType("mcp")
    mcp_server_mod = types.ModuleType("mcp.server")
    mcp_fastmcp_mod = types.ModuleType("mcp.server.fastmcp")
    mcp_fastmcp_mod.FastMCP = _FakeFastMCP
    mcp_mod.server = mcp_server_mod
    mcp_server_mod.fastmcp = mcp_fastmcp_mod
    sys.modules["mcp"] = mcp_mod
    sys.modules["mcp.server"] = mcp_server_mod
    sys.modules["mcp.server.fastmcp"] = mcp_fastmcp_mod


def _import_server():
    spec = importlib.util.spec_from_file_location("state_server_maintenance", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod  # noqa: E402
from handlers import maintenance as _maintenance_mod  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Mock cache + helpers
# ---------------------------------------------------------------------------


class MockStateCache:
    def __init__(self, state):
        self._state = state

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}


ARTIST = "test-artist"


def _state(audio_root, albums, artist=ARTIST):
    return {
        "config": {"audio_root": str(audio_root), "artist_name": artist},
        "albums": albums,
    }


def _album_audio_dir(audio_root: Path, genre: str, slug: str, artist: str = ARTIST) -> Path:
    return audio_root / "artists" / artist / "albums" / genre / slug


def _make_album_audio(
    audio_root: Path,
    genre: str,
    slug: str,
    wavs=(),
    originals=False,
    extra_files=(),
) -> Path:
    """Create an on-disk album audio dir; return its Path."""
    audio_dir = _album_audio_dir(audio_root, genre, slug)
    audio_dir.mkdir(parents=True, exist_ok=True)
    for name in wavs:
        (audio_dir / name).write_bytes(b"RIFF0000WAVE")
    for name in extra_files:
        (audio_dir / name).write_text("not audio", encoding="utf-8")
    if originals:
        (audio_dir / "originals").mkdir(exist_ok=True)
    return audio_dir


def _result_for(result: dict, slug: str) -> dict:
    """Pull the per-album result dict for *slug* out of a migrate response."""
    return next(a for a in result["albums"] if a["slug"] == slug)


# ===========================================================================
# migrate_audio_layout — PRIORITY (least-tested before this file)
# ===========================================================================


class TestMigrateAudioLayoutDryRun:
    def test_dry_run_reports_without_moving(self, tmp_path):
        audio_dir = _make_album_audio(
            tmp_path, "electronic", "test-album", wavs=["01-a.wav", "02-b.wav"],
        )
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("test-album", dry_run=True)
            ))

        assert result["dry_run"] is True
        entry = _result_for(result, "test-album")
        assert entry["status"] == "would_migrate"
        assert sorted(entry["files_moved"]) == ["01-a.wav", "02-b.wav"]
        assert result["summary"]["migrated"] == 1
        assert result["summary"]["total_files_moved"] == 2
        # Nothing actually moved.
        assert (audio_dir / "01-a.wav").exists()
        assert not (audio_dir / "originals").exists()

    def test_dry_run_is_the_default(self, tmp_path):
        _make_album_audio(tmp_path, "electronic", "test-album", wavs=["01-a.wav"])
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("test-album")
            ))

        assert result["dry_run"] is True
        assert _result_for(result, "test-album")["status"] == "would_migrate"


class TestMigrateAudioLayoutRealMove:
    def test_moves_root_wavs_into_originals(self, tmp_path):
        audio_dir = _make_album_audio(
            tmp_path, "electronic", "test-album", wavs=["01-a.wav", "02-b.wav"],
        )
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("test-album", dry_run=False)
            ))

        assert result["dry_run"] is False
        assert _result_for(result, "test-album")["status"] == "migrated"
        originals = audio_dir / "originals"
        assert (originals / "01-a.wav").exists()
        assert (originals / "02-b.wav").exists()
        # Root no longer holds the WAV files.
        assert not (audio_dir / "01-a.wav").exists()

    def test_non_wav_files_stay_in_root(self, tmp_path):
        audio_dir = _make_album_audio(
            tmp_path, "electronic", "test-album",
            wavs=["01-a.wav"], extra_files=["notes.txt", "cover.png"],
        )
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("test-album", dry_run=False)
            ))

        entry = _result_for(result, "test-album")
        assert entry["files_moved"] == ["01-a.wav"]
        assert (audio_dir / "originals" / "01-a.wav").exists()
        # Non-audio files are left untouched in the album root.
        assert (audio_dir / "notes.txt").exists()
        assert (audio_dir / "cover.png").exists()

    def test_uppercase_extension_is_migrated(self, tmp_path):
        """The handler matches on a case-insensitive .wav suffix."""
        audio_dir = _make_album_audio(
            tmp_path, "electronic", "test-album", wavs=["Track.WAV"],
        )
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("test-album", dry_run=False)
            ))

        assert _result_for(result, "test-album")["files_moved"] == ["Track.WAV"]
        assert (audio_dir / "originals" / "Track.WAV").exists()


class TestMigrateAudioLayoutSkips:
    def test_already_migrated_when_originals_present(self, tmp_path):
        _make_album_audio(
            tmp_path, "electronic", "test-album", wavs=["01-a.wav"], originals=True,
        )
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("test-album", dry_run=False)
            ))

        entry = _result_for(result, "test-album")
        assert entry["status"] == "already_migrated"
        assert entry["files_moved"] == []
        assert result["summary"]["already_migrated"] == 1

    def test_no_wav_files_skipped(self, tmp_path):
        _make_album_audio(
            tmp_path, "electronic", "test-album", extra_files=["readme.txt"],
        )
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("test-album", dry_run=True)
            ))

        entry = _result_for(result, "test-album")
        assert entry["status"] == "skipped"
        assert entry["skip_reason"] == "no WAV files in root"

    def test_missing_genre_skipped(self, tmp_path):
        state = _state(tmp_path, {"test-album": {"genre": ""}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("test-album", dry_run=True)
            ))

        entry = _result_for(result, "test-album")
        assert entry["status"] == "skipped"
        assert entry["skip_reason"] == "no genre in state"

    def test_missing_audio_dir_skipped(self, tmp_path):
        # Album is in state with a genre, but no audio dir exists on disk.
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("test-album", dry_run=True)
            ))

        entry = _result_for(result, "test-album")
        assert entry["status"] == "skipped"
        assert entry["skip_reason"] == "no audio dir"


class TestMigrateAudioLayoutAllAlbums:
    def test_all_albums_processed_with_mixed_outcomes(self, tmp_path):
        _make_album_audio(tmp_path, "electronic", "fresh-album", wavs=["01-a.wav"])
        _make_album_audio(tmp_path, "rock", "done-album", wavs=["01-b.wav"], originals=True)
        state = _state(tmp_path, {
            "fresh-album": {"genre": "electronic"},
            "done-album": {"genre": "rock"},
        })

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            # Empty album_slug means "all albums".
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("", dry_run=True)
            ))

        assert result["summary"]["total_albums"] == 2
        assert result["summary"]["migrated"] == 1
        assert result["summary"]["already_migrated"] == 1
        assert _result_for(result, "fresh-album")["status"] == "would_migrate"
        assert _result_for(result, "done-album")["status"] == "already_migrated"


class TestMigrateAudioLayoutErrors:
    def test_specific_album_not_in_state(self, tmp_path):
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("ghost-album", dry_run=True)
            ))

        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_unconfigured_audio_root_returns_error(self, tmp_path):
        state = _state("", {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.migrate_audio_layout("test-album", dry_run=True)
            ))

        assert "error" in result
        assert "not configured" in result["error"].lower()


# ===========================================================================
# reset_mastering
# ===========================================================================


class TestResetMastering:
    def _make_audio_with_subfolder(self, tmp_path, subfolder="mastered"):
        audio_dir = _album_audio_dir(tmp_path, "electronic", "test-album")
        target = audio_dir / subfolder
        target.mkdir(parents=True)
        (target / "01-track.wav").write_bytes(b"\x00" * 2048)
        return audio_dir

    def test_dry_run_reports_would_delete(self, tmp_path):
        audio_dir = self._make_audio_with_subfolder(tmp_path)
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.reset_mastering("test-album", dry_run=True)
            ))

        assert result["dry_run"] is True
        assert result["results"]["mastered"]["status"] == "would_delete"
        assert result["results"]["mastered"]["file_count"] == 1
        # Dry run leaves the directory in place.
        assert (audio_dir / "mastered").is_dir()

    def test_actual_delete_removes_subfolder(self, tmp_path):
        audio_dir = self._make_audio_with_subfolder(tmp_path)
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.reset_mastering("test-album", dry_run=False)
            ))

        assert result["results"]["mastered"]["status"] == "deleted"
        assert not (audio_dir / "mastered").exists()

    def test_disallowed_subfolder_rejected(self, tmp_path):
        """originals/ is protected and cannot be reset."""
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.reset_mastering("test-album", subfolders=["originals"])
            ))

        assert "error" in result
        assert "originals" in str(result)
        assert "mastered" in result["allowed"]

    def test_absent_subfolder_reported_not_found(self, tmp_path):
        # Only mastered/ exists; asking for polished/ too reports not_found.
        self._make_audio_with_subfolder(tmp_path, "mastered")
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.reset_mastering(
                    "test-album", subfolders=["mastered", "polished"], dry_run=True,
                )
            ))

        assert result["results"]["mastered"]["status"] == "would_delete"
        assert result["results"]["polished"]["status"] == "not_found"

    def test_missing_audio_dir_returns_error(self, tmp_path):
        # No audio dir on disk for this album at all.
        state = _state(tmp_path, {"test-album": {"genre": "electronic"}})

        with patch.object(_shared_mod, "cache", MockStateCache(state)):
            result = json.loads(_run(
                _maintenance_mod.reset_mastering("test-album", dry_run=True)
            ))

        assert "error" in result


# ===========================================================================
# cleanup_legacy_venvs
# ===========================================================================


class TestCleanupLegacyVenvs:
    def test_dry_run_lists_stale_venv(self, tmp_path):
        tools_root = tmp_path / ".bitwize-music"
        stale = tools_root / "mastering-env"
        stale.mkdir(parents=True)
        (stale / "pyvenv.cfg").write_bytes(b"\x00" * 256)

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = json.loads(_run(_maintenance_mod.cleanup_legacy_venvs(dry_run=True)))

        assert result["dry_run"] is True
        assert result["stale_venvs_found"] == 1
        assert result["results"]["mastering-env"]["status"] == "would_delete"
        assert result["results"]["promotion-env"]["status"] == "not_found"
        # Dry run leaves the directory alone.
        assert stale.exists()

    def test_no_legacy_dirs_all_not_found(self, tmp_path):
        (tmp_path / ".bitwize-music").mkdir()

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = json.loads(_run(_maintenance_mod.cleanup_legacy_venvs(dry_run=True)))

        assert result["stale_venvs_found"] == 0
        for name in ("mastering-env", "promotion-env", "cloud-env"):
            assert result["results"][name]["status"] == "not_found"

    def test_actual_removal_deletes_all(self, tmp_path):
        tools_root = tmp_path / ".bitwize-music"
        for name in ("mastering-env", "promotion-env", "cloud-env"):
            d = tools_root / name
            d.mkdir(parents=True)
            (d / "marker").write_bytes(b"\x00" * 64)

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = json.loads(_run(_maintenance_mod.cleanup_legacy_venvs(dry_run=False)))

        assert result["stale_venvs_found"] == 3
        for name in ("mastering-env", "promotion-env", "cloud-env"):
            assert result["results"][name]["status"] == "deleted"
            assert not (tools_root / name).exists()
