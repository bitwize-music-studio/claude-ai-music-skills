#!/usr/bin/env python3
"""
Unit tests for handlers/processing/mixing.py — mix polish handler functions.

Tests polish_audio, analyze_mix_issues, and polish_album using real audio
fixtures with mocked path resolution.
"""

import asyncio
import importlib
import importlib.util
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Mock MCP SDK if not installed
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
    spec = importlib.util.spec_from_file_location("state_server_mixing", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

from handlers.processing import mixing as _mixing_mod
from handlers.processing import _helpers as _helpers_mod
from handlers import _shared as _shared_mod

from tests.fixtures.audio import (
    make_full_mix,
    make_noisy,
    make_vocal,
    write_wav,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(coro):
    """Run an async coroutine synchronously."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def _setup_audio_dir(tmp_path, num_tracks=2):
    """Create a temp audio dir with WAV files and return the path."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    for i in range(num_tracks):
        data, rate = make_full_mix(duration=1.5)
        write_wav(str(audio_dir / f"0{i+1}-track.wav"), data, rate)

    return audio_dir


def _setup_stems_dir(tmp_path):
    """Create a temp audio dir with stems/ subdirectory."""
    audio_dir = tmp_path / "audio"
    audio_dir.mkdir()

    stems = audio_dir / "stems" / "01-test-track"
    stems.mkdir(parents=True)

    for name, gen in [("vocals", make_vocal), ("bass", make_full_mix)]:
        data, rate = gen(duration=1.0)
        write_wav(str(stems / f"{name}.wav"), data, rate)

    return audio_dir


# ---------------------------------------------------------------------------
# Tests: polish_audio
# ---------------------------------------------------------------------------


class TestPolishAudio:
    """Tests for the polish_audio handler."""

    def test_missing_deps_returns_error(self, tmp_path):
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value="deps missing"):
            result = json.loads(_run(_mixing_mod.polish_audio("test-album")))
        assert "error" in result
        assert "deps" in result["error"]

    def test_missing_audio_dir_returns_error(self, tmp_path):
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=('{"error": "not found"}', None)):
            result = _run(_mixing_mod.polish_audio("test-album"))
        assert "not found" in result

    def test_full_mix_mode(self, tmp_path):
        audio_dir = _setup_audio_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.polish_audio("test", use_stems=False, dry_run=True))
        result = json.loads(raw)
        assert "tracks" in result
        assert result["settings"]["use_stems"] is False
        assert result["settings"]["dry_run"] is True

    def test_full_mix_mode_writes_output(self, tmp_path):
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.polish_audio("test", use_stems=False, dry_run=False))
        result = json.loads(raw)
        assert result["summary"]["mode"] == "full_mix"
        assert result["summary"]["tracks_processed"] >= 1
        # Verify polished/ dir was created
        assert (audio_dir / "polished").is_dir()

    def test_stems_mode_falls_back_when_no_stems_dir(self, tmp_path):
        """When use_stems=True but no stems/ dir, gracefully fall back to full-mix."""
        audio_dir = _setup_audio_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.polish_audio("test", use_stems=True, dry_run=True))
        result = json.loads(raw)
        assert "error" not in result
        assert result["summary"]["mode"] == "full_mix"

    def test_stems_mode_with_stems(self, tmp_path):
        audio_dir = _setup_stems_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.polish_audio("test", use_stems=True, dry_run=True))
        result = json.loads(raw)
        assert "tracks" in result
        assert result["summary"]["mode"] == "stems"

    def test_invalid_genre(self, tmp_path):
        audio_dir = _setup_audio_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.polish_audio("test", genre="nonexistent-genre-xyz"))
        result = json.loads(raw)
        assert "error" in result
        assert "genre" in result["error"].lower()

    def test_no_wav_files_returns_error(self, tmp_path):
        audio_dir = tmp_path / "empty"
        audio_dir.mkdir()
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.polish_audio("test", use_stems=False))
        result = json.loads(raw)
        assert "error" in result


# ---------------------------------------------------------------------------
# Tests: analyze_mix_issues
# ---------------------------------------------------------------------------


class TestAnalyzeMixIssues:
    """Tests for the analyze_mix_issues handler."""

    def test_missing_deps_returns_error(self):
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value="deps missing"):
            result = json.loads(_run(_mixing_mod.analyze_mix_issues("test-album")))
        assert "error" in result

    def test_missing_audio_dir(self):
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=('{"error": "not found"}', None)):
            result = _run(_mixing_mod.analyze_mix_issues("test"))
        assert "not found" in result

    def test_analyzes_tracks(self, tmp_path):
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=2)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.analyze_mix_issues("test"))
        result = json.loads(raw)
        assert "tracks" in result
        assert len(result["tracks"]) == 2
        assert "album_summary" in result
        assert result["album_summary"]["tracks_analyzed"] == 2

    def test_per_track_metrics(self, tmp_path):
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.analyze_mix_issues("test"))
        result = json.loads(raw)
        track = result["tracks"][0]
        assert "filename" in track
        assert "peak" in track
        assert "rms" in track
        assert "noise_floor" in track
        assert "issues" in track

    def test_noisy_audio_detected(self, tmp_path):
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        # Create an extremely noisy signal
        rate = 44100
        rng = np.random.default_rng(seed=300)
        noise = rng.normal(0, 0.3, (rate * 2, 2)).astype(np.float64)
        write_wav(str(audio_dir / "noisy.wav"), noise, rate)

        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.analyze_mix_issues("test"))
        result = json.loads(raw)
        track = result["tracks"][0]
        assert track["noise_floor"] > 0.005

    def test_no_wav_files(self, tmp_path):
        audio_dir = tmp_path / "empty"
        audio_dir.mkdir()
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.analyze_mix_issues("test"))
        result = json.loads(raw)
        assert "error" in result

    def test_falls_back_to_stems_when_no_root_wavs(self, tmp_path):
        """When no root WAVs exist but stems/ has tracks, analyze stems."""
        audio_dir = _setup_stems_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.analyze_mix_issues("test"))
        result = json.loads(raw)
        assert "error" not in result
        assert result["album_summary"]["tracks_analyzed"] >= 1
        assert result["album_summary"]["source_mode"] == "stems"

    def test_stems_mode_analyzes_every_stem_per_track(self, tmp_path):
        """Each stem in a track gets its own analysis, not just the first alphabetically."""
        audio_dir = _setup_stems_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.analyze_mix_issues("test"))
        result = json.loads(raw)
        assert result["album_summary"]["tracks_analyzed"] == 1
        track = result["tracks"][0]
        assert track["track"] == "01-test-track"
        assert set(track["stems"].keys()) == {"vocals", "bass"}
        for stem_name, stem_analysis in track["stems"].items():
            assert "peak" in stem_analysis
            assert "issues" in stem_analysis
        assert "issues" in track


# ---------------------------------------------------------------------------
# Tests: polish_album (3-stage pipeline)
# ---------------------------------------------------------------------------


class TestPolishAlbum:
    """Tests for the polish_album pipeline handler."""

    def test_missing_deps(self):
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value="deps missing"):
            raw = _run(_mixing_mod.polish_album("test"))
        result = json.loads(raw)
        assert result["stage_reached"] == "pre_flight"
        assert result["failed_stage"] == "pre_flight"

    def test_missing_audio_dir(self):
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir",
                          return_value=('{"error": "Album not found"}', None)):
            raw = _run(_mixing_mod.polish_album("test"))
        result = json.loads(raw)
        assert result["stage_reached"] == "pre_flight"

    def test_full_pipeline(self, tmp_path):
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.polish_album("test"))
        result = json.loads(raw)
        assert result["stage_reached"] == "complete"
        assert "stages" in result
        assert result["stages"]["pre_flight"]["status"] == "pass"
        assert result["stages"]["analysis"]["status"] == "pass"
        assert result["stages"]["polish"]["status"] == "pass"
        # verify now runs the full qc_track suite; synthetic test audio can
        # legitimately trigger FAIL on spectral/silence — we only care that
        # the stage ran and produced a verdict.
        assert result["stages"]["verify"]["status"] in ("pass", "warn", "fail")
        assert "tracks_verified" in result["stages"]["verify"]

    def test_stems_mode_pipeline(self, tmp_path):
        audio_dir = _setup_stems_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.polish_album("test"))
        result = json.loads(raw)
        # Analysis now falls back to stems when no root WAVs exist,
        # so the full pipeline should complete with stems-only audio
        assert "stages" in result
        assert result["stages"]["pre_flight"]["mode"] == "stems"

    def test_pipeline_next_step_suggestion(self, tmp_path):
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.polish_album("test"))
        result = json.loads(raw)
        if result["stage_reached"] == "complete":
            assert "master_audio" in result.get("next_step", "")
