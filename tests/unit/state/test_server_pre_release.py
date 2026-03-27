#!/usr/bin/env python3
"""
Unit tests for run_pre_release_gates MCP tool.

Usage:
    python -m pytest tests/unit/state/test_server_pre_release.py -v
"""

import asyncio
import copy
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure project root is on sys.path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Import server module from hyphenated directory via importlib.
# Same mock setup as test_server.py — the server requires mcp.server.fastmcp
# which may not be installed in the test environment.
# ---------------------------------------------------------------------------

SERVER_PATH = PROJECT_ROOT / "servers" / "bitwize-music-server" / "server.py"

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
    """Import the server module from the hyphenated directory."""
    spec = importlib.util.spec_from_file_location("state_server_pre_release", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers import _shared as _shared_mod
from handlers import gates as _gates_mod


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _make_sample_state(*, album_status="Complete", track_status="Final",
                       album_explicit=False, track_explicit=False,
                       streaming_urls=None):
    """Build a sample state dict with configurable album/track settings."""
    return {
        "version": 2,
        "config": {
            "content_root": "/tmp/test-content",
            "audio_root": "/tmp/test-audio",
            "documents_root": "/tmp/test-docs",
            "artist_name": "test-artist",
            "overrides_path": "/tmp/test-content/overrides",
            "ideas_file": "/tmp/test-content/IDEAS.md",
        },
        "albums": {
            "test-album": {
                "title": "Test Album",
                "status": album_status,
                "genre": "electronic",
                "explicit": album_explicit,
                "path": "/tmp/test-content/artists/test-artist/albums/electronic/test-album",
                "streaming_urls": streaming_urls or {},
                "track_count": 2,
                "tracks": {
                    "01-first-track": {
                        "title": "First Track",
                        "status": track_status,
                        "explicit": track_explicit,
                        "has_suno_link": True,
                        "sources_verified": "N/A",
                        "path": "",
                        "mtime": 1234567890.0,
                    },
                    "02-second-track": {
                        "title": "Second Track",
                        "status": track_status,
                        "explicit": track_explicit,
                        "has_suno_link": True,
                        "sources_verified": "N/A",
                        "path": "",
                        "mtime": 1234567891.0,
                    },
                },
                "mtime": 1234567890.0,
            },
        },
        "ideas": {"total": 0, "by_status": {}, "items": []},
        "session": {
            "last_album": None, "last_track": None,
            "last_phase": None, "pending_actions": [],
            "updated_at": None,
        },
        "meta": {"rebuilt_at": "2026-01-01T00:00:00Z", "plugin_version": "0.50.0"},
    }


class MockStateCache:
    """A mock StateCache that holds state in memory."""

    def __init__(self, state=None):
        self._state = state if state is not None else _make_sample_state()

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}


def _make_track_file(content: str = "") -> str:
    """Build minimal track markdown with streaming lyrics section."""
    if not content:
        content = (
            "---\ntitle: Test\n---\n"
            "## Streaming Lyrics\n\n"
            "```\n"
            "These are real streaming lyrics\n"
            "With proper capitalization\n"
            "And enough words to pass validation\n"
            "```\n"
        )
    return content


def _setup_audio_dir(tmp_path, *, with_originals=True, with_mastered=True, with_art=True):
    """Create a realistic audio directory structure.

    Returns the album audio path.
    """
    audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
    audio_dir.mkdir(parents=True, exist_ok=True)

    if with_originals:
        originals = audio_dir / "originals"
        originals.mkdir(exist_ok=True)
        (originals / "01-first-track.wav").write_bytes(b"\x00" * 100)
        (originals / "02-second-track.wav").write_bytes(b"\x00" * 100)

    if with_mastered:
        mastered = audio_dir / "mastered"
        mastered.mkdir(exist_ok=True)
        (mastered / "01-first-track.wav").write_bytes(b"\x00" * 100)
        (mastered / "02-second-track.wav").write_bytes(b"\x00" * 100)

    if with_art:
        (audio_dir / "album.png").write_bytes(b"\x89PNG")

    return audio_dir


def _setup_track_files(tmp_path, state, *, streaming_lyrics=True, placeholder=False):
    """Create track markdown files and update state paths.

    Returns the tracks directory.
    """
    content_dir = tmp_path / "content" / "artists" / "test-artist" / "albums" / "electronic" / "test-album" / "tracks"
    content_dir.mkdir(parents=True, exist_ok=True)

    for t_slug in state["albums"]["test-album"]["tracks"]:
        if streaming_lyrics:
            if placeholder:
                lyrics_block = "Plain lyrics here\nCapitalize first letter of each line"
            else:
                lyrics_block = (
                    "These are real streaming lyrics\n"
                    "With proper capitalization\n"
                    "And enough words to pass the word count check easily\n"
                    "Because we need at least twenty words total here now"
                )
            content = (
                f"---\ntitle: {t_slug}\n---\n"
                f"## Streaming Lyrics\n\n```\n{lyrics_block}\n```\n"
            )
        else:
            content = f"---\ntitle: {t_slug}\n---\n## Notes\n\nNo streaming lyrics yet.\n"

        track_file = content_dir / f"{t_slug}.md"
        track_file.write_text(content, encoding="utf-8")
        state["albums"]["test-album"]["tracks"][t_slug]["path"] = str(track_file)

    return content_dir


# =============================================================================
# Tests for run_pre_release_gates
# =============================================================================


class TestPreReleaseGatesAlbumNotFound:
    """Album lookup failure."""

    def test_unknown_album_returns_error(self):
        state = _make_sample_state()
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("nonexistent")))
        assert result["found"] is False
        assert "not found" in result["error"]


class TestPreReleaseGatesAllPass:
    """All gates pass — album is release-ready."""

    def test_fully_ready_album(self, tmp_path):
        state = _make_sample_state(
            track_status="Final",
            streaming_urls={"soundcloud": "https://soundcloud.com/test"},
        )
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path)

        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        assert result["found"] is True
        assert result["verdict"] == "READY"
        assert result["blocking"] == 0
        assert result["warnings"] == 0
        assert len(result["gates"]) == 7

        gate_names = [g["gate"] for g in result["gates"]]
        assert "All Tracks Final" in gate_names
        assert "Audio Files Exist" in gate_names
        assert "Mastered Audio Exists" in gate_names
        assert "Album Art Exists" in gate_names
        assert "Streaming Lyrics Ready" in gate_names
        assert "Explicit Flag Consistency" in gate_names
        assert "Streaming URLs Set" in gate_names

        for gate in result["gates"]:
            assert gate["status"] == "PASS", f"Gate '{gate['gate']}' should PASS but got {gate['status']}"


class TestPreReleaseGateTracksNotFinal:
    """Gate 1: All Tracks Final."""

    def test_non_final_tracks_block(self, tmp_path):
        state = _make_sample_state(track_status="Generated")
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        assert result["verdict"] == "NOT READY"
        gate = next(g for g in result["gates"] if g["gate"] == "All Tracks Final")
        assert gate["status"] == "FAIL"
        assert gate["severity"] == "BLOCKING"

    def test_mixed_final_and_generated_blocks(self, tmp_path):
        state = _make_sample_state(track_status="Final")
        state["albums"]["test-album"]["tracks"]["02-second-track"]["status"] = "Generated"
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "All Tracks Final")
        assert gate["status"] == "FAIL"
        assert "1 track(s) not Final" in gate["detail"]


class TestPreReleaseGateAudioFiles:
    """Gate 2: Audio Files Exist."""

    def test_no_audio_dir_blocks(self, tmp_path):
        state = _make_sample_state(track_status="Final")
        _setup_track_files(tmp_path, state)
        state["config"]["audio_root"] = str(tmp_path)
        # Don't create audio dir
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Audio Files Exist")
        assert gate["status"] == "FAIL"

    def test_empty_audio_dir_blocks(self, tmp_path):
        state = _make_sample_state(track_status="Final")
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path, with_originals=False, with_mastered=True, with_art=True)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Audio Files Exist")
        assert gate["status"] == "FAIL"
        assert "No WAV" in gate["detail"]


class TestPreReleaseGateMasteredAudio:
    """Gate 3: Mastered Audio Exists."""

    def test_no_mastered_dir_blocks(self, tmp_path):
        state = _make_sample_state(track_status="Final")
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path, with_mastered=False)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Mastered Audio Exists")
        assert gate["status"] == "FAIL"
        assert "mastering-engineer" in gate["detail"]


class TestPreReleaseGateAlbumArt:
    """Gate 4: Album Art Exists."""

    def test_no_art_blocks(self, tmp_path):
        state = _make_sample_state(track_status="Final")
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path, with_art=False)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Album Art Exists")
        assert gate["status"] == "FAIL"
        assert "No album art" in gate["detail"]

    def test_alternative_art_names_pass(self, tmp_path):
        """Cover various accepted art filenames."""
        for art_name in ["cover.jpg", "artwork.png", "album-art.jpg"]:
            state = _make_sample_state(
                track_status="Final",
                streaming_urls={"soundcloud": "https://example.com"},
            )
            _setup_track_files(tmp_path, state)
            audio_dir = _setup_audio_dir(tmp_path, with_art=False)
            (audio_dir / art_name).write_bytes(b"\x89PNG")
            state["config"]["audio_root"] = str(tmp_path)
            mock_cache = MockStateCache(state)

            with patch.object(_shared_mod, "cache", mock_cache):
                result = json.loads(_run(server.run_pre_release_gates("test-album")))

            gate = next(g for g in result["gates"] if g["gate"] == "Album Art Exists")
            assert gate["status"] == "PASS", f"Art file '{art_name}' should be recognized"


class TestPreReleaseGateStreamingLyrics:
    """Gate 5: Streaming Lyrics Ready."""

    def test_missing_streaming_lyrics_blocks(self, tmp_path):
        state = _make_sample_state(track_status="Final")
        _setup_track_files(tmp_path, state, streaming_lyrics=False)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Streaming Lyrics Ready")
        assert gate["status"] == "FAIL"
        assert "2 track(s) not ready" in gate["detail"]

    def test_placeholder_streaming_lyrics_blocks(self, tmp_path):
        state = _make_sample_state(track_status="Final")
        _setup_track_files(tmp_path, state, streaming_lyrics=True, placeholder=True)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Streaming Lyrics Ready")
        assert gate["status"] == "FAIL"
        assert "placeholder" in gate["detail"]

    def test_no_track_path_reported(self, tmp_path):
        state = _make_sample_state(track_status="Final")
        # Don't set up track files — paths remain empty
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Streaming Lyrics Ready")
        assert gate["status"] == "FAIL"
        assert "no track path" in gate["detail"]


class TestPreReleaseGateExplicitConsistency:
    """Gate 6: Explicit Flag Consistency."""

    def test_album_clean_but_tracks_explicit_blocks(self, tmp_path):
        state = _make_sample_state(
            track_status="Final", album_explicit=False, track_explicit=True,
        )
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Explicit Flag Consistency")
        assert gate["status"] == "FAIL"
        assert gate["severity"] == "BLOCKING"
        assert "set album explicit: true" in gate["detail"]

    def test_album_explicit_but_tracks_clean_warns(self, tmp_path):
        state = _make_sample_state(
            track_status="Final", album_explicit=True, track_explicit=False,
        )
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Explicit Flag Consistency")
        assert gate["status"] == "WARN"
        assert gate["severity"] == "WARNING"

    def test_both_explicit_passes(self, tmp_path):
        state = _make_sample_state(
            track_status="Final", album_explicit=True, track_explicit=True,
            streaming_urls={"soundcloud": "https://example.com"},
        )
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Explicit Flag Consistency")
        assert gate["status"] == "PASS"
        assert "explicit" in gate["detail"]

    def test_both_clean_passes(self, tmp_path):
        state = _make_sample_state(
            track_status="Final", album_explicit=False, track_explicit=False,
            streaming_urls={"soundcloud": "https://example.com"},
        )
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Explicit Flag Consistency")
        assert gate["status"] == "PASS"
        assert "clean" in gate["detail"]


class TestPreReleaseGateStreamingUrls:
    """Gate 7: Streaming URLs Set."""

    def test_no_urls_warns(self, tmp_path):
        state = _make_sample_state(track_status="Final", streaming_urls={})
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Streaming URLs Set")
        assert gate["status"] == "WARN"
        assert gate["severity"] == "WARNING"
        # Should not be blocking — URLs are added after upload
        assert result["blocking"] == 0

    def test_urls_set_passes(self, tmp_path):
        state = _make_sample_state(
            track_status="Final",
            streaming_urls={
                "soundcloud": "https://soundcloud.com/test/album",
                "spotify": "https://open.spotify.com/album/123",
            },
        )
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        gate = next(g for g in result["gates"] if g["gate"] == "Streaming URLs Set")
        assert gate["status"] == "PASS"
        assert "2 platform(s)" in gate["detail"]


class TestPreReleaseGatesVerdict:
    """Overall verdict logic."""

    def test_ready_with_warnings(self, tmp_path):
        """No blocking issues but has warnings → READY (with warnings)."""
        state = _make_sample_state(
            track_status="Final", album_explicit=True, track_explicit=False,
            streaming_urls={},
        )
        _setup_track_files(tmp_path, state)
        _setup_audio_dir(tmp_path)
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        assert result["blocking"] == 0
        assert result["warnings"] >= 1
        assert result["verdict"] == "READY (with warnings)"

    def test_not_ready_with_blockers(self, tmp_path):
        """Blocking issues → NOT READY."""
        state = _make_sample_state(track_status="In Progress")
        _setup_track_files(tmp_path, state, streaming_lyrics=False)
        state["config"]["audio_root"] = str(tmp_path)
        # No audio dir created
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        assert result["blocking"] > 0
        assert result["verdict"] == "NOT READY"

    def test_multiple_blocking_gates_counted(self, tmp_path):
        """Multiple failures are all counted."""
        state = _make_sample_state(
            track_status="Generated", album_explicit=False, track_explicit=True,
        )
        _setup_track_files(tmp_path, state, streaming_lyrics=False)
        # No audio dir
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.run_pre_release_gates("test-album")))

        # Should fail: tracks not final, no audio, no mastered, no art,
        # no streaming lyrics, explicit mismatch
        assert result["blocking"] >= 5
