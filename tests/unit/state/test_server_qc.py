#!/usr/bin/env python3
"""
Unit tests for qc_audio and master_album MCP tools.

Split from test_server.py to stay under pre-commit file-size limits.

Usage:
    python -m pytest tests/unit/state/test_server_qc.py -v
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

import numpy as np
import pytest
import soundfile as sf


def _write_tiny_stereo_wav(path) -> None:
    """Write a 1-second 44.1k 16-bit stereo sine WAV via raw bytes.

    Bypasses soundfile so tests that patch `soundfile.write` still get a
    real file on disk that downstream code can read. Duration ≥0.4 s to
    satisfy pyloudnorm's integrated-loudness block size.
    """
    import struct
    rate = 44100
    duration = 1.0
    n_samples = int(rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    mono = (0.2 * np.sin(2 * np.pi * 440 * t)) * 32767
    int16 = mono.astype(np.int16)
    interleaved = np.column_stack([int16, int16]).flatten().tobytes()

    n_channels = 2
    bits_per_sample = 16
    byte_rate = rate * n_channels * bits_per_sample // 8
    block_align = n_channels * bits_per_sample // 8
    data_size = len(interleaved)
    fmt_chunk = struct.pack(
        "<4sIHHIIHH",
        b"fmt ", 16, 1, n_channels, rate, byte_rate, block_align, bits_per_sample,
    )
    data_chunk = struct.pack("<4sI", b"data", data_size) + interleaved
    riff_size = 4 + len(fmt_chunk) + len(data_chunk)
    riff = struct.pack("<4sI4s", b"RIFF", riff_size, b"WAVE") + fmt_chunk + data_chunk

    with open(str(path), "wb") as f:
        f.write(riff)

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
    spec = importlib.util.spec_from_file_location("state_server_qc", SERVER_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


server = _import_server()

# Handler modules for mock targeting
from handlers.processing import _helpers as _processing_helpers
from handlers import _shared as _shared_mod


# ---------------------------------------------------------------------------
# Shared helpers (duplicated from test_server.py to keep files independent)
# ---------------------------------------------------------------------------

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
                "01-first-track": {
                    "title": "First Track",
                    "status": "In Progress",
                    "explicit": False,
                    "has_suno_link": False,
                    "sources_verified": "N/A",
                    "mtime": 1234567890.0,
                },
                "02-second-track": {
                    "title": "Second Track",
                    "status": "Not Started",
                    "explicit": False,
                    "has_suno_link": False,
                    "sources_verified": "N/A",
                    "mtime": 1234567891.0,
                },
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
    "meta": {
        "rebuilt_at": "2026-01-01T00:00:00Z",
        "plugin_version": "0.50.0",
    },
}


def _run(coro):
    """Run an async coroutine synchronously."""
    return asyncio.run(coro)


def _fresh_state():
    """Return a deep copy of sample state so tests don't interfere."""
    return copy.deepcopy(SAMPLE_STATE)


class MockStateCache:
    """A mock StateCache that holds state in memory without filesystem I/O."""

    def __init__(self, state=None):
        self._state = state if state is not None else _fresh_state()
        self._rebuild_called = False

    def get_state(self):
        return self._state

    def get_state_ref(self):
        return self._state or {}

    def rebuild(self):
        self._rebuild_called = True
        return self._state

    def update_session(self, **kwargs):
        if not self._state:
            return {"error": "No state available"}
        session = copy.deepcopy(self._state.get("session", {}))
        if kwargs.get("clear"):
            session = {
                "last_album": None,
                "last_track": None,
                "last_phase": None,
                "pending_actions": [],
                "updated_at": None,
            }
        else:
            if kwargs.get("album") is not None:
                session["last_album"] = kwargs["album"]
            if kwargs.get("track") is not None:
                session["last_track"] = kwargs["track"]
            if kwargs.get("phase") is not None:
                session["last_phase"] = kwargs["phase"]
            if kwargs.get("action"):
                session.setdefault("pending_actions", []).append(kwargs["action"])
        self._state["session"] = session
        return session


# =============================================================================
# Tests for qc_audio MCP tool
# =============================================================================


class TestQcAudio:
    """Tests for the qc_audio MCP tool."""

    def test_missing_deps_returns_error(self):
        with patch.object(_processing_helpers, "_check_mastering_deps", return_value="Missing deps"):
            result = json.loads(_run(server.qc_audio("test-album")))
        assert "error" in result
        assert "Missing deps" in result["error"]

    def test_missing_audio_dir_returns_error(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.qc_audio("test-album")))
        assert "error" in result

    def test_no_wav_files_returns_error(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.qc_audio("test-album")))
        assert "error" in result
        assert "No WAV" in result["error"]

    def test_invalid_check_name_returns_error(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "01-test.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.qc_audio("test-album", checks="bogus")))
        assert "error" in result
        assert "Unknown checks" in result["error"]


class TestQcAudioComprehensive:
    """Comprehensive tests for qc_audio: batch, verdicts, filtering."""

    def _make_audio_dir(self, tmp_path, num_tracks=2):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        for i in range(num_tracks):
            (audio_dir / f"{i+1:02d}-track-{i+1}.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        return audio_dir, state

    def _mock_qc_result(self, filename, verdict="PASS",
                        phase_status="PASS", spectral_status="PASS"):
        return {
            "filename": filename,
            "checks": {
                "format": {"status": "PASS", "value": "PCM_16 44100Hz 2ch", "detail": "OK"},
                "mono": {"status": "PASS", "value": "0.0 dB loss", "detail": "OK"},
                "phase": {"status": phase_status, "value": "0.95",
                          "detail": "Phase correlation good" if phase_status == "PASS"
                          else "Out of phase"},
                "clipping": {"status": "PASS", "value": "0 regions", "detail": "No clipping"},
                "clicks": {"status": "PASS", "value": "0 found", "detail": "No clicks"},
                "silence": {"status": "PASS", "value": "L:0.0s T:0.0s", "detail": "OK"},
                "spectral": {"status": spectral_status, "value": "B:30% M:40% H:30%",
                             "detail": "Balanced" if spectral_status == "PASS"
                             else "High-mid spike"},
            },
            "verdict": verdict,
        }

    def test_batch_multiple_tracks(self, tmp_path):
        """QC should process all WAV files and return per-track results."""
        audio_dir, state = self._make_audio_dir(tmp_path, 3)
        mock_cache = MockStateCache(state)

        call_count = []

        def mock_qc(filepath, checks=None, genre=None):
            name = Path(filepath).name
            call_count.append(name)
            return self._mock_qc_result(name)

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc):
            result = json.loads(_run(server.qc_audio("test-album")))

        assert len(result["tracks"]) == 3
        assert result["summary"]["total"] == 3
        assert len(call_count) == 3

    def test_all_pass_verdict(self, tmp_path):
        """All tracks passing should give ALL PASS verdict."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        def mock_qc(filepath, checks=None, genre=None):
            return self._mock_qc_result(Path(filepath).name, verdict="PASS")

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc):
            result = json.loads(_run(server.qc_audio("test-album")))

        assert result["verdict"] == "ALL PASS"
        assert result["summary"]["passed"] == 2
        assert result["summary"]["failed"] == 0

    def test_failure_verdict(self, tmp_path):
        """Any track failing should give FAILURES FOUND verdict."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        call_idx = [0]

        def mock_qc(filepath, checks=None, genre=None):
            idx = call_idx[0]
            call_idx[0] += 1
            if idx == 0:
                return self._mock_qc_result(
                    Path(filepath).name, verdict="FAIL", phase_status="FAIL"
                )
            return self._mock_qc_result(Path(filepath).name, verdict="PASS")

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc):
            result = json.loads(_run(server.qc_audio("test-album")))

        assert result["verdict"] == "FAILURES FOUND"
        assert result["summary"]["failed"] == 1
        assert result["summary"]["passed"] == 1

    def test_warning_verdict(self, tmp_path):
        """Tracks with only warnings should give WARNINGS verdict."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        def mock_qc(filepath, checks=None, genre=None):
            return self._mock_qc_result(
                Path(filepath).name, verdict="WARN", spectral_status="WARN"
            )

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc):
            result = json.loads(_run(server.qc_audio("test-album")))

        assert result["verdict"] == "WARNINGS"
        assert result["summary"]["warned"] == 1

    def test_subfolder_resolves(self, tmp_path):
        """Subfolder parameter should resolve to mastered/ subdir."""
        mastered_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album" / "mastered"
        mastered_dir.mkdir(parents=True)
        (mastered_dir / "01-track.wav").write_bytes(b"")

        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)

        def mock_qc(filepath, checks=None, genre=None):
            return self._mock_qc_result(Path(filepath).name)

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc):
            result = json.loads(_run(server.qc_audio("test-album", subfolder="mastered")))

        assert "tracks" in result
        assert len(result["tracks"]) == 1

    def test_checks_filter_passed_to_qc_track(self, tmp_path):
        """Checks parameter should be parsed and forwarded to qc_track."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        captured_checks = []

        def mock_qc(filepath, checks=None, genre=None):
            captured_checks.append(checks)
            return self._mock_qc_result(Path(filepath).name)

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc):
            _run(server.qc_audio("test-album", checks="format,phase"))

        assert len(captured_checks) == 1
        assert captured_checks[0] == ["format", "phase"]


# =============================================================================
# Tests for master_album MCP tool
# =============================================================================


class TestMasterAlbum:
    """Tests for the master_album MCP tool — error paths and pre-flight."""

    def test_missing_deps_returns_preflight_failure(self):
        with patch.object(_processing_helpers, "_check_mastering_deps", return_value="Missing deps"):
            result = json.loads(_run(server.master_album("test-album")))
        assert result["failed_stage"] == "pre_flight"
        assert result["stage_reached"] == "pre_flight"

    def test_missing_audio_dir_returns_preflight_failure(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent"
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.master_album("test-album")))
        assert result["failed_stage"] == "pre_flight"

    def test_no_wav_files_returns_preflight_failure(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None):
            result = json.loads(_run(server.master_album("test-album")))
        assert result["failed_stage"] == "pre_flight"
        assert "No WAV" in result["stages"]["pre_flight"]["detail"]

    def test_unknown_genre_returns_preflight_failure(self, tmp_path):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        (audio_dir / "01-test.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        mock_cache = MockStateCache(state)
        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}):
            result = json.loads(_run(server.master_album("test-album", genre="bogus")))
        assert result["failed_stage"] == "pre_flight"
        assert "Unknown genre" in result["failure_detail"]["reason"]


class TestMasterAlbumPipeline:
    """Comprehensive tests for master_album pipeline stages."""

    def _make_audio_dir(self, tmp_path, num_tracks=2):
        """Create audio dir with dummy WAV files and matching state."""
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        for i in range(num_tracks):
            (audio_dir / f"{i+1:02d}-track-{i+1}.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        return audio_dir, state

    def _mock_analyze(self, filename, lufs=-14.0, tinniness=0.3, peak_db=-1.5):
        return {
            "filename": filename,
            "duration": 180.0,
            "sample_rate": 44100,
            "lufs": lufs,
            "peak_db": peak_db,
            "rms_db": -18.0,
            "dynamic_range": 17.0,
            "band_energy": {"sub_bass": 5, "bass": 20, "low_mid": 15,
                            "mid": 30, "high_mid": 20, "high": 8, "air": 2},
            "tinniness_ratio": tinniness,
        }

    def _mock_qc_result(self, filename, verdict="PASS", phase_status="PASS"):
        return {
            "filename": filename,
            "checks": {
                "format": {"status": "PASS", "value": "PCM_16 44100Hz 2ch", "detail": "OK"},
                "mono": {"status": "PASS", "value": "0.0 dB", "detail": "OK"},
                "phase": {"status": phase_status, "value": "0.95",
                          "detail": "OK" if phase_status == "PASS" else "Out of phase"},
                "clipping": {"status": "PASS", "value": "0 regions", "detail": "OK"},
                "clicks": {"status": "PASS", "value": "0 found", "detail": "OK"},
                "silence": {"status": "PASS", "value": "L:0.0s T:0.0s", "detail": "OK"},
                "spectral": {"status": "PASS", "value": "B:30% M:40% H:30%", "detail": "OK"},
            },
            "verdict": verdict,
        }

    def _mock_master_result(self, filename):
        return {
            "original_lufs": -20.0,
            "final_lufs": -14.0,
            "gain_applied": 6.0,
            "final_peak": -1.5,
        }

    def test_pre_qc_skips_truepeak_and_clicks(self, tmp_path):
        """Pre-QC must skip truepeak and clicks checks.

        Polished audio is pre-limiter (hot peaks are expected — the master
        stage's limiter brings them down), and polish runs its own declick,
        so a generic click detector here false-positives on legitimate
        percussive transients. The essential checks (format, mono, phase,
        clipping, silence, spectral) remain so pre-QC still catches things
        mastering cannot fix.
        """
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        qc_calls = []

        def mock_qc(filepath, checks=None, genre=None):
            qc_calls.append({"path": Path(filepath).name, "checks": checks})
            return self._mock_qc_result(Path(filepath).name)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        def mock_analyze(filepath):
            return self._mock_analyze(Path(filepath).name, lufs=-14.0)

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc), \
             patch.object(server, "write_state"):
            _run(server.master_album("test-album"))

        assert len(qc_calls) >= 1, "qc_track must be invoked at least once (pre-QC)"
        pre_qc = qc_calls[0]
        assert pre_qc["checks"] is not None, "Pre-QC must pass an explicit checks list"
        assert "truepeak" not in pre_qc["checks"], (
            "Pre-QC must not run truepeak — the limiter brings peaks down; "
            "post-master verification is the real ceiling gate"
        )
        assert "clicks" not in pre_qc["checks"], (
            "Pre-QC must not run clicks — polish already ran declick, so "
            "residual transients here false-positive on percussive content"
        )
        # Essential checks mastering can't fix must remain
        for essential in ("format", "mono", "phase", "clipping", "silence", "spectral"):
            assert essential in pre_qc["checks"], (
                f"Pre-QC must still run '{essential}' — mastering cannot fix it"
            )

    def test_pre_qc_failure_stops_pipeline(self, tmp_path):
        """Pre-QC FAIL should stop pipeline before mastering."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        call_idx = [0]

        def mock_qc(filepath, checks=None, genre=None):
            idx = call_idx[0]
            call_idx[0] += 1
            name = Path(filepath).name
            if idx == 1:
                return self._mock_qc_result(name, verdict="FAIL", phase_status="FAIL")
            return self._mock_qc_result(name)

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name)), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["stage_reached"] == "pre_qc"
        assert result["failed_stage"] == "pre_qc"
        assert len(result["failure_detail"]["tracks_failed"]) == 1
        assert result["failure_detail"]["details"][0]["check"] == "phase"
        # Mastering stage should NOT exist
        assert "mastering" not in result["stages"]

    def test_verification_failure_stops_pipeline(self, tmp_path):
        """Mastered tracks outside LUFS spec should fail verification."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        master_called = [False]

        def mock_master(input_path, output_path, **kwargs):
            master_called[0] = True
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        analyze_call_idx = [0]

        def mock_analyze(filepath):
            idx = analyze_call_idx[0]
            analyze_call_idx[0] += 1
            name = Path(filepath).name
            if idx >= 1:
                return self._mock_analyze(name, lufs=-16.0)
            return self._mock_analyze(name, lufs=-20.0)

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)):
            result = json.loads(_run(server.master_album("test-album")))

        assert master_called[0], "Mastering should have run before verification"
        assert result["stage_reached"] == "verification"
        assert result["failed_stage"] == "verification"
        assert result["stages"]["verification"]["all_within_spec"] is False

    def test_verification_peak_failure(self, tmp_path):
        """Mastered track peak above ceiling should fail verification."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -0.5,
            }

        analyze_call_idx = [0]

        def mock_analyze(filepath):
            idx = analyze_call_idx[0]
            analyze_call_idx[0] += 1
            name = Path(filepath).name
            if idx >= 1:
                return self._mock_analyze(name, lufs=-14.0, peak_db=-0.5)
            return self._mock_analyze(name, lufs=-20.0)

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["failed_stage"] == "verification"
        assert any(
            "Peak" in issue
            for track in result["failure_detail"]["tracks_out_of_spec"]
            for issue in track["issues"]
        )

    def test_post_qc_failure_stops_pipeline(self, tmp_path):
        """Post-QC FAIL on mastered output should stop before status update."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        def mock_analyze(filepath):
            return self._mock_analyze(Path(filepath).name, lufs=-14.0)

        qc_call_idx = [0]

        def mock_qc(filepath, checks=None, genre=None):
            idx = qc_call_idx[0]
            qc_call_idx[0] += 1
            name = Path(filepath).name
            if idx >= 1:
                return self._mock_qc_result(name, verdict="FAIL", phase_status="FAIL")
            return self._mock_qc_result(name)

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["stage_reached"] == "post_qc"
        assert result["failed_stage"] == "post_qc"
        assert "status_update" not in result["stages"]

    def test_full_pipeline_success(self, tmp_path):
        """Complete pipeline with all stages passing should reach 'complete'."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)

        content_dir = tmp_path / "content" / "artists" / "test-artist" / "albums" / "electronic" / "test-album" / "tracks"
        content_dir.mkdir(parents=True)
        for i in range(2):
            slug = f"{i+1:02d}-track-{i+1}"
            track_file = content_dir / f"{slug}.md"
            track_file.write_text(
                f"# Track {i+1}\n\n"
                f"| **Status** | Generated |\n"
                f"| **Explicit** | No |\n",
                encoding="utf-8",
            )
            state["albums"]["test-album"]["tracks"][slug] = {
                "path": str(track_file),
                "title": f"Track {i+1}",
                "status": "Generated",
                "explicit": False,
                "has_suno_link": True,
                "sources_verified": "N/A",
                "mtime": 1234567890.0,
            }

        album_dir = content_dir.parent
        readme = album_dir / "README.md"
        readme.write_text(
            "# Test Album\n\n| **Status** | In Progress |\n",
            encoding="utf-8",
        )
        state["albums"]["test-album"]["path"] = str(album_dir)

        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        def mock_analyze(filepath):
            return self._mock_analyze(Path(filepath).name, lufs=-14.0)

        def mock_qc(filepath, checks=None, genre=None):
            return self._mock_qc_result(Path(filepath).name)

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["stage_reached"] == "complete"
        assert result["failed_stage"] is None
        assert result["failure_detail"] is None

        assert "pre_flight" in result["stages"]
        assert "analysis" in result["stages"]
        assert "pre_qc" in result["stages"]
        assert "mastering" in result["stages"]
        assert "verification" in result["stages"]
        assert "post_qc" in result["stages"]
        assert "status_update" in result["stages"]

        for stage_name, stage_data in result["stages"].items():
            assert stage_data["status"] == "pass", f"Stage '{stage_name}' did not pass"

    def test_full_pipeline_updates_track_status(self, tmp_path):
        """Successful pipeline should write 'Final' to track files."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)

        content_dir = tmp_path / "content" / "tracks"
        content_dir.mkdir(parents=True)
        track_file = content_dir / "01-track-1.md"
        track_file.write_text(
            "# Track 1\n\n| **Status** | Generated |\n| **Explicit** | No |\n",
            encoding="utf-8",
        )
        state["albums"]["test-album"]["tracks"] = {
            "01-track-1": {
                "path": str(track_file),
                "title": "Track 1",
                "status": "Generated",
                "explicit": False,
                "has_suno_link": True,
                "sources_verified": "N/A",
                "mtime": 1234567890.0,
            },
        }

        album_dir = content_dir.parent
        readme = album_dir / "README.md"
        readme.write_text(
            "# Test Album\n\n| **Status** | In Progress |\n",
            encoding="utf-8",
        )
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name, lufs=-14.0)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch.object(server, "write_state"), \
             patch.object(server, "parse_track_file", return_value={"status": "Final"}):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["stage_reached"] == "complete"
        assert result["stages"]["status_update"]["tracks_updated"] == 1

        updated_text = track_file.read_text(encoding="utf-8")
        assert "Final" in updated_text

    def test_full_pipeline_updates_album_status(self, tmp_path):
        """When all tracks become Final, album should be set to Complete."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)

        content_dir = tmp_path / "content" / "tracks"
        content_dir.mkdir(parents=True)
        track_file = content_dir / "01-track-1.md"
        track_file.write_text(
            "# Track 1\n\n| **Status** | Generated |\n| **Explicit** | No |\n",
            encoding="utf-8",
        )
        state["albums"]["test-album"]["tracks"] = {
            "01-track-1": {
                "path": str(track_file),
                "title": "Track 1",
                "status": "Generated",
                "explicit": False,
                "has_suno_link": True,
                "sources_verified": "N/A",
                "mtime": 1234567890.0,
            },
        }
        album_dir = content_dir.parent
        readme = album_dir / "README.md"
        readme.write_text(
            "# Test Album\n\n| **Status** | In Progress |\n",
            encoding="utf-8",
        )
        state["albums"]["test-album"]["path"] = str(album_dir)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name, lufs=-14.0)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch.object(server, "write_state"), \
             patch.object(server, "parse_track_file", return_value={"status": "Final"}):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["stages"]["status_update"]["album_status"] == "Complete"

        updated_readme = readme.read_text(encoding="utf-8")
        assert "Complete" in updated_readme

    def test_settings_returned_in_response(self, tmp_path):
        """Response should include the effective mastering settings."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)
        state["albums"]["test-album"]["tracks"] = {}

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets",
                   return_value={"rock": {"target_lufs": -14.0, "cut_highmid": -2.5, "cut_highs": 0.0, "compress_ratio": 1.5}}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name, lufs=-14.0)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.master_album("test-album", genre="rock")))

        assert result["settings"]["genre"] == "rock"
        assert result["settings"]["target_lufs"] == -14.0
        assert result["settings"]["cut_highmid"] == -2.5
        assert result["settings"]["ceiling_db"] == -1.0

    def test_warnings_collected_from_qc(self, tmp_path):
        """QC WARN items should be collected in the warnings list."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)
        state["albums"]["test-album"]["tracks"] = {}

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        def mock_qc(filepath, checks=None, genre=None):
            name = Path(filepath).name
            r = self._mock_qc_result(name)
            r["checks"]["spectral"]["status"] = "WARN"
            r["checks"]["spectral"]["detail"] = "High-mid spike (tinniness ratio 0.85)"
            r["verdict"] = "WARN"
            return r

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name, lufs=-14.0)), \
             patch("tools.mastering.qc_tracks.qc_track", side_effect=mock_qc), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["stage_reached"] == "complete"
        spectral_warns = [w for w in result["warnings"] if "spectral" in w]
        assert len(spectral_warns) >= 1

    def test_tinny_tracks_in_analysis_warnings(self, tmp_path):
        """Tinny tracks detected during analysis should appear in warnings."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)
        state["albums"]["test-album"]["tracks"] = {}

        call_idx = [0]

        def mock_analyze(filepath):
            idx = call_idx[0]
            call_idx[0] += 1
            name = Path(filepath).name
            tinniness = 0.8 if idx == 0 else 0.2
            return self._mock_analyze(name, lufs=-14.0, tinniness=tinniness)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.master_album("test-album")))

        tinny_warns = [w for w in result["warnings"] if "tinny" in w.lower()]
        assert len(tinny_warns) == 1

    def test_verification_album_range_failure(self, tmp_path):
        """Album LUFS range >= 1.0 dB should fail verification."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        verify_idx = [0]

        def mock_analyze(filepath):
            name = Path(filepath).name
            if "mastered" not in filepath:
                return self._mock_analyze(name, lufs=-20.0)
            idx = verify_idx[0]
            verify_idx[0] += 1
            lufs = -13.4 if idx == 0 else -14.6
            return self._mock_analyze(name, lufs=lufs)

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["failed_stage"] == "verification"
        assert "album_lufs_range" in result["failure_detail"]
        assert result["failure_detail"]["album_lufs_range"] >= 1.0

    def test_all_silent_tracks_fails_mastering(self, tmp_path):
        """If all tracks are skipped (silent), mastering stage should fail."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            return {"skipped": True}

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["failed_stage"] == "mastering"
        assert result["stage_reached"] == "mastering"

    def test_status_update_errors_are_warnings(self, tmp_path):
        """Status update failures should not fail the pipeline — just warn."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        state["albums"]["test-album"]["tracks"] = {
            "01-track-1": {
                "path": str(tmp_path / "nonexistent" / "track.md"),
                "title": "Track 1",
                "status": "Generated",
                "explicit": False,
                "has_suno_link": True,
                "sources_verified": "N/A",
                "mtime": 1234567890.0,
            },
        }

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name, lufs=-14.0)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["stage_reached"] == "complete"
        assert result["failed_stage"] is None
        status_warns = [w for w in result["warnings"] if "Status update" in w]
        assert len(status_warns) >= 1
        assert result["stages"]["status_update"]["tracks_updated"] == 0

    def test_genre_preset_sets_effective_settings(self, tmp_path):
        """Genre preset should change the effective EQ/LUFS settings."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)
        state["albums"]["test-album"]["tracks"] = {}

        captured_kwargs = []

        def mock_master(input_path, output_path, **kwargs):
            captured_kwargs.append(kwargs)
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -13.0,
                "gain_applied": 7.0,
                "final_peak": -1.5,
            }

        presets = {"country": {"target_lufs": -14.0, "cut_highmid": -2.0, "cut_highs": 0.0, "compress_ratio": 1.5}}

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value=presets), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name, lufs=-13.0)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.master_album("test-album", genre="country")))

        assert result["settings"]["genre"] == "country"
        assert result["settings"]["cut_highmid"] == -2.0

        assert len(captured_kwargs) == 1
        eq = captured_kwargs[0]["eq_settings"]
        assert eq == [(3500, -2.0, 1.5)]

    # --- Auto-recovery tests ---

    def test_auto_recovery_triggers_on_dynamic_range(self, tmp_path):
        """LUFS too low + peak at ceiling → fix_dynamic runs, pipeline passes."""
        import numpy as np_
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        # Track analyze calls: Stage 2 gets 2 calls (idx 0-1),
        # Stage 5 verify gets 2 (idx 2-3), re-verify gets 2 (idx 4-5).
        analyze_call_count = [0]

        def mock_analyze(filepath):
            idx = analyze_call_count[0]
            analyze_call_count[0] += 1
            name = Path(filepath).name
            # Re-verify pass (idx >= 4): track 1 now passes after recovery
            if name == "01-track-1.wav" and idx >= 4:
                return self._mock_analyze(name, lufs=-14.0, peak_db=-1.1)
            # Initial verify (idx 2-3) and analysis: track 1 LUFS too low
            if name == "01-track-1.wav":
                return self._mock_analyze(name, lufs=-16.0, peak_db=-1.0)
            return self._mock_analyze(name, lufs=-14.0, peak_db=-1.5)

        fix_dynamic_called = [False]

        def mock_fix_dynamic(data, rate, target_lufs=-14.0, eq_settings=None, ceiling_db=-1.0):
            fix_dynamic_called[0] = True
            return data, {
                "original_lufs": -16.0,
                "final_lufs": -14.0,
                "final_peak_db": -1.1,
            }

        fake_audio = np_.zeros((100, 2))

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch("tools.mastering.fix_dynamic_track.fix_dynamic", side_effect=mock_fix_dynamic), \
             patch("soundfile.read", return_value=(fake_audio, 44100)), \
             patch("soundfile.write"):
            result = json.loads(_run(server.master_album("test-album")))

        assert fix_dynamic_called[0], "fix_dynamic should have been called"
        assert result["stages"]["verification"]["status"] == "pass"
        assert result["stages"]["verification"]["all_within_spec"] is True
        assert len(result["stages"]["verification"]["auto_recovered"]) == 1
        assert result["stages"]["verification"]["auto_recovered"][0]["filename"] == "01-track-1.wav"

    def test_auto_recovery_skips_non_recoverable(self, tmp_path):
        """LUFS too high or peak exceeds ceiling → no fix attempted, fails normally."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        def mock_analyze(filepath):
            name = Path(filepath).name
            # LUFS too HIGH — not recoverable
            return self._mock_analyze(name, lufs=-12.0, peak_db=-1.5)

        fix_dynamic_called = [False]

        def mock_fix_dynamic(data, rate, **kwargs):
            fix_dynamic_called[0] = True
            return data, {}

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch("tools.mastering.fix_dynamic_track.fix_dynamic", side_effect=mock_fix_dynamic):
            result = json.loads(_run(server.master_album("test-album")))

        assert not fix_dynamic_called[0], "fix_dynamic should NOT have been called"
        assert result["failed_stage"] == "verification"

    def test_auto_recovery_fails_gracefully(self, tmp_path):
        """Fix attempted but still out of spec → returns failure JSON."""
        import numpy as np_
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        def mock_analyze(filepath):
            name = Path(filepath).name
            # Always returns LUFS too low with peak at ceiling — even after fix
            return self._mock_analyze(name, lufs=-16.0, peak_db=-1.0)

        def mock_fix_dynamic(data, rate, target_lufs=-14.0, eq_settings=None, ceiling_db=-1.0):
            # Fix doesn't actually help
            return data, {
                "original_lufs": -16.0,
                "final_lufs": -15.5,
                "final_peak_db": -1.0,
            }

        fake_audio = np_.zeros((100, 2))

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch("tools.mastering.fix_dynamic_track.fix_dynamic", side_effect=mock_fix_dynamic), \
             patch("soundfile.read", return_value=(fake_audio, 44100)), \
             patch("soundfile.write"):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["failed_stage"] == "verification"
        assert result["stages"]["verification"]["all_within_spec"] is False

    def test_auto_recovery_reported_in_warnings(self, tmp_path):
        """Recovery details should appear in warnings list."""
        import numpy as np_
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        # Stage 2: 2 calls (idx 0-1), Stage 5: 2 calls (idx 2-3),
        # Re-verify: 2 calls (idx 4-5)
        analyze_call_count = [0]

        def mock_analyze(filepath):
            idx = analyze_call_count[0]
            analyze_call_count[0] += 1
            name = Path(filepath).name
            if name == "02-track-2.wav" and idx >= 4:
                return self._mock_analyze(name, lufs=-14.0, peak_db=-1.1)
            if name == "02-track-2.wav":
                return self._mock_analyze(name, lufs=-16.0, peak_db=-1.0)
            return self._mock_analyze(name, lufs=-14.0, peak_db=-1.5)

        def mock_fix_dynamic(data, rate, target_lufs=-14.0, eq_settings=None, ceiling_db=-1.0):
            return data, {
                "original_lufs": -16.0,
                "final_lufs": -14.0,
                "final_peak_db": -1.1,
            }

        fake_audio = np_.zeros((100, 2))

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch("tools.mastering.fix_dynamic_track.fix_dynamic", side_effect=mock_fix_dynamic), \
             patch("soundfile.read", return_value=(fake_audio, 44100)), \
             patch("soundfile.write"):
            result = json.loads(_run(server.master_album("test-album")))

        recovery_warnings = [w for w in result["warnings"] if isinstance(w, dict) and w.get("type") == "auto_recovery"]
        assert len(recovery_warnings) == 1
        assert "02-track-2.wav" in recovery_warnings[0]["tracks_fixed"]

    def test_fade_out_passed_to_master_track(self, tmp_path):
        """master_album should read fade_out from track metadata and pass it to master_track."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        # Set fade_out in track metadata
        state["albums"]["test-album"]["tracks"] = {
            "01-track-1": {
                "title": "Track 1",
                "status": "Generated",
                "explicit": False,
                "has_suno_link": True,
                "sources_verified": "N/A",
                "fade_out": 3.0,
                "mtime": 1234567890.0,
            },
        }

        captured_kwargs = []

        def mock_master(input_path, output_path, **kwargs):
            captured_kwargs.append(kwargs)
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name, lufs=-14.0)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch.object(server, "write_state"):
            json.loads(_run(server.master_album("test-album")))

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["fade_out"] == 3.0

    def test_auto_recovery_re_verifies_all_tracks(self, tmp_path):
        """After fixing one track, ALL tracks should be re-verified."""
        import numpy as np_
        audio_dir, state = self._make_audio_dir(tmp_path, 3)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        analyzed_files = []
        analyze_call_count = [0]

        def mock_analyze(filepath):
            idx = analyze_call_count[0]
            analyze_call_count[0] += 1
            name = Path(filepath).name
            analyzed_files.append(name)
            # Stage 2: idx 0-2, Stage 5 verify: idx 3-5, re-verify: idx 6-8
            # Track 1 fails in verify (idx 3-5) but passes in re-verify (idx 6+)
            if name == "01-track-1.wav" and idx >= 6:
                return self._mock_analyze(name, lufs=-14.0, peak_db=-1.5)
            if name == "01-track-1.wav":
                return self._mock_analyze(name, lufs=-16.0, peak_db=-1.0)
            return self._mock_analyze(name, lufs=-14.0, peak_db=-1.5)

        def mock_fix_dynamic(data, rate, target_lufs=-14.0, eq_settings=None, ceiling_db=-1.0):
            return data, {
                "original_lufs": -16.0,
                "final_lufs": -14.0,
                "final_peak_db": -1.1,
            }

        fake_audio = np_.zeros((100, 2))

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track", side_effect=mock_analyze), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch("tools.mastering.fix_dynamic_track.fix_dynamic", side_effect=mock_fix_dynamic), \
             patch("soundfile.read", return_value=(fake_audio, 44100)), \
             patch("soundfile.write"):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["stages"]["verification"]["status"] == "pass"
        # Stage 2: 3 calls, Stage 5 verify: 3 calls, re-verify: 3 calls = 9 total
        # The re-verify calls (idx 6-8) should include all 3 tracks
        re_verify_calls = analyzed_files[6:]
        assert len(re_verify_calls) == 3, (
            f"Expected 3 re-verification calls, got {len(re_verify_calls)}: {re_verify_calls}"
        )


# =============================================================================
# Tests for reset_mastering MCP tool
# =============================================================================


class TestResetMastering:
    """Tests for the reset_mastering MCP tool."""

    def _make_audio_tree(self, tmp_path, subfolders=("mastered",)):
        """Create a fake audio dir with subfolders containing dummy files."""
        audio_dir = (
            tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        )
        for sf in subfolders:
            d = audio_dir / sf
            d.mkdir(parents=True)
            (d / "track1.wav").write_bytes(b"\x00" * 1024)
            (d / "track2.wav").write_bytes(b"\x00" * 2048)
        # Ensure the base audio_dir exists
        audio_dir.mkdir(parents=True, exist_ok=True)
        return audio_dir

    def test_dry_run_reports_without_deleting(self, tmp_path):
        audio_dir = self._make_audio_tree(tmp_path, ["mastered"])
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.reset_mastering("test-album", dry_run=True)))

        assert result["dry_run"] is True
        assert result["results"]["mastered"]["status"] == "would_delete"
        assert result["results"]["mastered"]["file_count"] == 2
        # Files should still exist
        assert (audio_dir / "mastered" / "track1.wav").exists()

    def test_delete_mastered(self, tmp_path):
        audio_dir = self._make_audio_tree(tmp_path, ["mastered"])
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.reset_mastering("test-album", dry_run=False)))

        assert result["dry_run"] is False
        assert result["results"]["mastered"]["status"] == "deleted"
        assert not (audio_dir / "mastered").exists()

    def test_delete_multiple_subfolders(self, tmp_path):
        audio_dir = self._make_audio_tree(tmp_path, ["mastered", "polished"])
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(
                server.reset_mastering(
                    "test-album", subfolders=["mastered", "polished"], dry_run=False,
                )
            ))

        assert result["results"]["mastered"]["status"] == "deleted"
        assert result["results"]["polished"]["status"] == "deleted"
        assert not (audio_dir / "mastered").exists()
        assert not (audio_dir / "polished").exists()

    def test_rejects_disallowed_subfolders(self):
        """originals, stems, and arbitrary names must be rejected."""
        state = _fresh_state()
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(
                server.reset_mastering("test-album", subfolders=["originals"])
            ))
        assert "error" in result
        assert "originals" in result["error"]

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(
                server.reset_mastering("test-album", subfolders=["stems"])
            ))
        assert "error" in result

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(
                server.reset_mastering("test-album", subfolders=["foo"])
            ))
        assert "error" in result

    def test_missing_subfolder_reported_not_found(self, tmp_path):
        self._make_audio_tree(tmp_path, ["mastered"])  # no polished/
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(
                server.reset_mastering(
                    "test-album", subfolders=["mastered", "polished"], dry_run=False,
                )
            ))

        assert result["results"]["mastered"]["status"] == "deleted"
        assert result["results"]["polished"]["status"] == "not_found"

    def test_missing_audio_dir_returns_error(self):
        state = _fresh_state()
        state["config"]["audio_root"] = "/nonexistent/path"
        mock_cache = MockStateCache(state)

        with patch.object(_shared_mod, "cache", mock_cache):
            result = json.loads(_run(server.reset_mastering("test-album")))

        assert "error" in result


# =============================================================================
# Tests for cleanup_legacy_venvs MCP tool
# =============================================================================


class TestCleanupLegacyVenvs:
    """Tests for the cleanup_legacy_venvs MCP tool."""

    def test_dry_run_reports_stale_venvs(self, tmp_path):
        tools_root = tmp_path / ".bitwize-music"
        tools_root.mkdir()
        stale = tools_root / "mastering-env"
        stale.mkdir()
        (stale / "bin").mkdir()
        (stale / "bin" / "python3").write_bytes(b"\x00" * 512)

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = json.loads(_run(server.cleanup_legacy_venvs(dry_run=True)))

        assert result["dry_run"] is True
        assert result["results"]["mastering-env"]["status"] == "would_delete"
        assert result["stale_venvs_found"] == 1
        # Directory should still exist
        assert stale.exists()

    def test_delete_stale_venvs(self, tmp_path):
        tools_root = tmp_path / ".bitwize-music"
        tools_root.mkdir()
        for name in ("mastering-env", "promotion-env", "cloud-env"):
            d = tools_root / name
            d.mkdir()
            (d / "dummy").write_bytes(b"\x00" * 100)

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = json.loads(_run(server.cleanup_legacy_venvs(dry_run=False)))

        assert result["stale_venvs_found"] == 3
        for name in ("mastering-env", "promotion-env", "cloud-env"):
            assert result["results"][name]["status"] == "deleted"
            assert not (tools_root / name).exists()

    def test_no_stale_venvs(self, tmp_path):
        tools_root = tmp_path / ".bitwize-music"
        tools_root.mkdir()
        # Only the active venv exists
        (tools_root / "venv").mkdir()

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = json.loads(_run(server.cleanup_legacy_venvs(dry_run=True)))

        assert result["stale_venvs_found"] == 0
        for name in ("mastering-env", "promotion-env", "cloud-env"):
            assert result["results"][name]["status"] == "not_found"

    def test_partial_stale_venvs(self, tmp_path):
        tools_root = tmp_path / ".bitwize-music"
        tools_root.mkdir()
        (tools_root / "cloud-env").mkdir()
        (tools_root / "cloud-env" / "file.txt").write_bytes(b"\x00" * 50)

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = json.loads(_run(server.cleanup_legacy_venvs(dry_run=False)))

        assert result["stale_venvs_found"] == 1
        assert result["results"]["cloud-env"]["status"] == "deleted"
        assert result["results"]["mastering-env"]["status"] == "not_found"


# =============================================================================
# Tests for mastering staging directory behaviour
# =============================================================================


class TestMasterAlbumStaging:
    """Tests that mastering uses a staging directory to prevent orphaned files."""

    def setup_method(self):
        self._orig_cache = _shared_mod.cache
        _shared_mod.cache = MockStateCache(_fresh_state())

    def teardown_method(self):
        _shared_mod.cache = self._orig_cache

    def _make_audio_dir(self, tmp_path, num_tracks=3):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        for i in range(num_tracks):
            (audio_dir / f"{i+1:02d}-track-{i+1}.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        return audio_dir, state

    def _mock_analyze(self, filename, lufs=-14.0):
        return {
            "filename": filename,
            "duration": 180.0,
            "sample_rate": 44100,
            "lufs": lufs,
            "peak_db": -1.5,
            "rms_db": -18.0,
            "dynamic_range": 17.0,
            "band_energy": {"sub_bass": 5, "bass": 20, "low_mid": 15,
                            "mid": 30, "high_mid": 20, "high": 8, "air": 2},
            "tinniness_ratio": 0.3,
        }

    def _mock_qc_result(self, filename, verdict="PASS"):
        return {
            "filename": filename,
            "checks": {
                "format": {"status": "PASS", "value": "PCM_16 44100Hz 2ch", "detail": "OK"},
                "mono": {"status": "PASS", "value": "0.0 dB", "detail": "OK"},
                "phase": {"status": "PASS", "value": "0.95", "detail": "OK"},
                "clipping": {"status": "PASS", "value": "0 regions", "detail": "OK"},
                "clicks": {"status": "PASS", "value": "0 found", "detail": "OK"},
                "silence": {"status": "PASS", "value": "L:0.0s T:0.0s", "detail": "OK"},
                "spectral": {"status": "PASS", "value": "B:30% M:40% H:30%", "detail": "OK"},
            },
            "verdict": verdict,
        }

    def test_failed_mastering_leaves_no_orphans(self, tmp_path):
        """If mastering raises mid-batch, mastered/ should be absent or empty."""
        audio_dir, state = self._make_audio_dir(tmp_path, num_tracks=3)
        mock_cache = MockStateCache(state)

        call_count = [0]

        def mock_master(input_path, output_path, **kwargs):
            call_count[0] += 1
            if call_count[0] >= 3:
                raise RuntimeError("simulated mastering crash")
            # Write to the output path that was given (staging dir)
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)):
            with pytest.raises(RuntimeError, match="simulated mastering crash"):
                _run(server.master_album("test-album"))

        # mastered/ must not exist or must be empty — no orphaned files
        mastered_dir = audio_dir / "mastered"
        if mastered_dir.exists():
            orphans = list(mastered_dir.iterdir())
            assert orphans == [], f"mastered/ contains orphaned files: {orphans}"

        # staging dir must also be cleaned up
        staging_dir = audio_dir / ".mastering_staging"
        assert not staging_dir.exists(), ".mastering_staging was not cleaned up after failure"

    def test_successful_mastering_populates_mastered_dir(self, tmp_path):
        """On full success, mastered/ contains all tracks and staging is gone."""
        audio_dir, state = self._make_audio_dir(tmp_path, num_tracks=2)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name, lufs=-14.0)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["stage_reached"] == "complete"

        # All 2 WAV files must be present in mastered/
        mastered_dir = audio_dir / "mastered"
        assert mastered_dir.exists(), "mastered/ was not created"
        mastered_wavs = sorted(f.name for f in mastered_dir.iterdir() if f.suffix == ".wav")
        assert mastered_wavs == ["01-track-1.wav", "02-track-2.wav"]

        # Staging dir must be gone
        staging_dir = audio_dir / ".mastering_staging"
        assert not staging_dir.exists(), ".mastering_staging was not cleaned up after success"

    def test_stale_staging_dir_is_cleared_before_run(self, tmp_path):
        """A leftover .mastering_staging from a previous crash is wiped before the next run."""
        audio_dir, state = self._make_audio_dir(tmp_path, num_tracks=1)
        mock_cache = MockStateCache(state)

        # Plant a stale staging file from a previous hypothetical run
        staging_dir = audio_dir / ".mastering_staging"
        staging_dir.mkdir()
        stale_file = staging_dir / "stale-artifact.wav"
        stale_file.write_bytes(b"stale")

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {
                "original_lufs": -20.0,
                "final_lufs": -14.0,
                "gain_applied": 6.0,
                "final_peak": -1.5,
            }

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name, lufs=-14.0)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["stage_reached"] == "complete"

        # stale artifact must NOT appear in mastered/
        mastered_dir = audio_dir / "mastered"
        mastered_names = [f.name for f in mastered_dir.iterdir()]
        assert "stale-artifact.wav" not in mastered_names

    def test_all_silent_cleans_staging(self, tmp_path):
        """When all tracks are skipped (silent), staging is cleaned up on the fail path."""
        audio_dir, state = self._make_audio_dir(tmp_path, num_tracks=1)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            return {"skipped": True}

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc_result(Path(f).name)):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["failed_stage"] == "mastering"

        staging_dir = audio_dir / ".mastering_staging"
        assert not staging_dir.exists(), ".mastering_staging was not cleaned up on silent-track failure"


# =============================================================================
# Tests for stage 5.5 — codec preview + mono fold-down (issue #296)
# =============================================================================


def _write_inverted_phase_wav(path) -> None:
    """1-second 44.1k stereo where R = -L — guaranteed mono fold-down FAIL."""
    import struct
    rate = 44100
    duration = 1.0
    n_samples = int(rate * duration)
    t = np.linspace(0, duration, n_samples, endpoint=False)
    mono = (0.3 * np.sin(2 * np.pi * 1000 * t)) * 32767
    left = mono.astype(np.int16)
    right = (-mono).astype(np.int16)
    interleaved = np.column_stack([left, right]).flatten().tobytes()

    n_channels, bits = 2, 16
    byte_rate = rate * n_channels * bits // 8
    block_align = n_channels * bits // 8
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, n_channels, rate, byte_rate, block_align, bits)
    data = struct.pack("<4sI", b"data", len(interleaved)) + interleaved
    riff = struct.pack("<4sI4s", b"RIFF", 4 + len(fmt) + len(data), b"WAVE") + fmt + data
    with open(str(path), "wb") as f:
        f.write(riff)


class TestMasterAlbumMasteringSamplesStage:
    """Stage 5.5: codec preview and mono fold-down QC artifacts."""

    def _make_audio_dir(self, tmp_path, num_tracks=2):
        audio_dir = tmp_path / "artists" / "test-artist" / "albums" / "electronic" / "test-album"
        audio_dir.mkdir(parents=True)
        for i in range(num_tracks):
            (audio_dir / f"{i+1:02d}-track-{i+1}.wav").write_bytes(b"")
        state = _fresh_state()
        state["config"]["audio_root"] = str(tmp_path)
        state["config"]["artist_name"] = "test-artist"
        return audio_dir, state

    def _mock_analyze(self, filename, lufs=-14.0, peak_db=-1.5):
        return {
            "filename": filename, "duration": 180.0, "sample_rate": 44100,
            "lufs": lufs, "peak_db": peak_db, "rms_db": -18.0, "dynamic_range": 17.0,
            "band_energy": {"sub_bass": 5, "bass": 20, "low_mid": 15,
                            "mid": 30, "high_mid": 20, "high": 8, "air": 2},
            "tinniness_ratio": 0.3,
        }

    def _mock_qc(self, filename):
        return {
            "filename": filename,
            "checks": {
                "format": {"status": "PASS", "value": "ok", "detail": "ok"},
                "mono": {"status": "PASS", "value": "0", "detail": "ok"},
            },
            "verdict": "PASS",
        }

    def test_stage_runs_and_writes_to_mastering_samples_dir(self, tmp_path):
        """In-phase mastered output → mastering_samples populated, mastered/ untouched."""
        audio_dir, state = self._make_audio_dir(tmp_path, 2)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_tiny_stereo_wav(output_path)
            return {"original_lufs": -20.0, "final_lufs": -14.0,
                    "gain_applied": 6.0, "final_peak": -1.5}

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc(Path(f).name)), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["failed_stage"] is None
        assert "mastering_samples" in result["stages"]
        samples_stage = result["stages"]["mastering_samples"]
        assert samples_stage["status"] == "pass"
        assert samples_stage["mono_fold"]["passed"] == 2
        assert samples_stage["mono_fold"]["failed"] == 0

        samples_dir = audio_dir / "mastering_samples"
        assert (samples_dir / "01-track-1.MONO_FOLD.md").exists()
        assert (samples_dir / "01-track-1.mono.wav").exists()

        # mastered/ stays WAV-only
        mastered_files = sorted(p.name for p in (audio_dir / "mastered").iterdir())
        assert mastered_files == ["01-track-1.wav", "02-track-2.wav"]

    def test_phase_inversion_short_circuits_pipeline_with_failed_stage(self, tmp_path):
        """When mock_master writes inverted-phase audio, stage 5.5 hard-fails."""
        audio_dir, state = self._make_audio_dir(tmp_path, 1)
        mock_cache = MockStateCache(state)

        def mock_master(input_path, output_path, **kwargs):
            _write_inverted_phase_wav(output_path)
            return {"original_lufs": -20.0, "final_lufs": -14.0,
                    "gain_applied": 6.0, "final_peak": -1.5}

        with patch.object(_shared_mod, "cache", mock_cache), \
             patch.object(_processing_helpers, "_check_mastering_deps", return_value=None), \
             patch("tools.mastering.master_tracks.load_genre_presets", return_value={}), \
             patch("tools.mastering.master_tracks.master_track", side_effect=mock_master), \
             patch("tools.mastering.analyze_tracks.analyze_track",
                   side_effect=lambda f: self._mock_analyze(Path(f).name)), \
             patch("tools.mastering.qc_tracks.qc_track",
                   side_effect=lambda f, c=None: self._mock_qc(Path(f).name)), \
             patch.object(server, "write_state"):
            result = json.loads(_run(server.master_album("test-album")))

        assert result["failed_stage"] == "mastering_samples"
        assert result["stage_reached"] == "mastering_samples"
        # Post-QC and status_update should NOT have run
        assert "post_qc" not in result["stages"]
        assert "status_update" not in result["stages"]
        # Failure detail surfaces the offending band
        detail = result["failure_detail"]
        assert "phase cancellation" in detail["reason"].lower()
        assert "01-track-1.wav" in detail["tracks_failed"]
        assert detail["details"][0]["worst_band"]["name"] is not None
