#!/usr/bin/env python3
"""Tests for render_codec_preview and mono_fold_check MCP tools (issue #296)."""
from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import shutil
import sys
import types
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    spec = importlib.util.spec_from_file_location("state_server_ms", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers.processing import _helpers as _processing_helpers
from handlers import _shared as _shared_mod


SAMPLE_STATE = {
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
            "status": "In Progress",
            "genre": "electronic",
            "path": "/tmp/test-content/artists/test-artist/albums/electronic/test-album",
            "track_count": 2,
            "tracks": {
                "01-first": {"title": "First", "status": "Generated", "mtime": 1.0},
                "02-second": {"title": "Second", "status": "Generated", "mtime": 2.0},
            },
            "mtime": 1234567890.0,
        },
    },
    "ideas": {"total": 0, "by_status": {}, "items": []},
    "session": {
        "last_album": None,
        "last_track": None,
        "last_phase": None,
        "pending_actions": [],
        "updated_at": None,
    },
    "meta": {"rebuilt_at": "2026-01-01T00:00:00Z", "plugin_version": "0.50.0"},
}


def _run(coro):
    return asyncio.run(coro)


def _fresh_state():
    return copy.deepcopy(SAMPLE_STATE)


class MockStateCache:
    def __init__(self, state=None):
        self._state = state if state is not None else _fresh_state()

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}

    def rebuild(self):
        return self._state


def _write_stereo_wav(path: Path, freq=1000.0, duration=1.0, rate=44100,
                     right_scale=1.0, amplitude=0.3):
    t = np.linspace(0, duration, int(rate * duration), endpoint=False)
    left = amplitude * np.sin(2 * np.pi * freq * t)
    right = right_scale * amplitude * np.sin(2 * np.pi * freq * t)
    data = np.column_stack([left, right]).astype(np.float32)
    sf.write(str(path), data, rate, subtype="PCM_16")


def _make_mastered_album(tmp_path: Path, right_scale=1.0):
    """Build a minimal audio dir with mastered/ containing 2 WAVs."""
    audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
    mastered = audio_dir / "mastered"
    mastered.mkdir(parents=True)
    _write_stereo_wav(mastered / "01-first.wav", right_scale=right_scale)
    _write_stereo_wav(mastered / "02-second.wav", right_scale=right_scale)
    state = _fresh_state()
    state["config"]["audio_root"] = str(tmp_path)
    return audio_dir, state


ffmpeg_available = shutil.which("ffmpeg") is not None
skip_if_no_ffmpeg = pytest.mark.skipif(not ffmpeg_available, reason="ffmpeg not installed")


class TestRenderCodecPreview:
    @skip_if_no_ffmpeg
    def test_writes_aac_m4a_to_mastering_samples(self, tmp_path):
        audio_dir, state = _make_mastered_album(tmp_path)
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.render_codec_preview("test-album")))
        assert "error" not in result
        samples_dir = audio_dir / "mastering_samples"
        assert samples_dir.is_dir()
        assert (samples_dir / "01-first.aac.m4a").exists()
        assert (samples_dir / "02-second.aac.m4a").exists()
        # Does NOT touch mastered/
        assert sorted(p.name for p in (audio_dir / "mastered").iterdir()) == [
            "01-first.wav", "02-second.wav",
        ]

    @skip_if_no_ffmpeg
    def test_returns_per_track_summary(self, tmp_path):
        audio_dir, state = _make_mastered_album(tmp_path)
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.render_codec_preview("test-album")))
        assert "previews" in result
        assert len(result["previews"]) == 2
        for entry in result["previews"]:
            assert "input" in entry
            assert "output_path" in entry
            assert "bitrate_kbps" in entry

    def test_no_mastered_dir_returns_error(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.render_codec_preview("test-album")))
        assert "error" in result


class TestMonoFoldCheck:
    def test_in_phase_album_returns_pass_verdict(self, tmp_path):
        audio_dir, state = _make_mastered_album(tmp_path, right_scale=1.0)
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.mono_fold_check("test-album")))
        assert "error" not in result
        assert result["verdict"] == "PASS"
        assert result["summary"]["failed"] == 0

    def test_writes_report_and_sample_to_mastering_samples(self, tmp_path):
        audio_dir, state = _make_mastered_album(tmp_path, right_scale=1.0)
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache):
            _run(server.mono_fold_check("test-album"))
        samples_dir = audio_dir / "mastering_samples"
        assert (samples_dir / "01-first.MONO_FOLD.md").exists()
        assert (samples_dir / "02-second.MONO_FOLD.md").exists()
        assert (samples_dir / "01-first.mono.wav").exists()
        assert (samples_dir / "02-second.mono.wav").exists()

    def test_mastered_dir_remains_wav_only(self, tmp_path):
        audio_dir, state = _make_mastered_album(tmp_path, right_scale=1.0)
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache):
            _run(server.mono_fold_check("test-album"))
        mastered_files = sorted(p.name for p in (audio_dir / "mastered").iterdir())
        assert mastered_files == ["01-first.wav", "02-second.wav"]

    def test_inverted_channels_hard_fail_with_offending_band(self, tmp_path):
        audio_dir, state = _make_mastered_album(tmp_path, right_scale=-1.0)
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.mono_fold_check("test-album")))
        assert result["verdict"] == "FAIL"
        assert result["summary"]["failed"] == 2
        # Each failed track should surface the offending band with its Hz range
        failing = [t for t in result["tracks"] if t["verdict"] == "FAIL"]
        assert len(failing) == 2
        for track in failing:
            assert track["worst_band"]["name"] is not None
            assert track["worst_band"]["delta_db"] < -6.0

    def test_skip_sample_audio_when_disabled(self, tmp_path):
        audio_dir, state = _make_mastered_album(tmp_path, right_scale=1.0)
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache):
            _run(server.mono_fold_check("test-album", write_audio=False))
        samples_dir = audio_dir / "mastering_samples"
        # Report still written
        assert (samples_dir / "01-first.MONO_FOLD.md").exists()
        # But no .mono.wav
        assert not (samples_dir / "01-first.mono.wav").exists()

    def test_no_mastered_dir_returns_error(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.mono_fold_check("test-album")))
        assert "error" in result
