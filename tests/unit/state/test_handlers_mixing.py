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
import logging
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
    import mcp.server.fastmcp  # noqa: F401
except ImportError:

    class _FakeFastMCP:
        def __init__(self, name="", **kwargs):
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

    # -- genre defaulting from the album's state entry (#556) -------------

    def test_derives_genre_from_state_when_omitted(self, tmp_path):
        """A plain polish_audio(album_slug) call, with no genre argument,
        picks up the album's genre from state so genre-scoped overrides
        apply without the caller passing genre explicitly."""
        audio_dir = _setup_audio_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_helpers_mod, "_derive_album_genre", return_value="hip-hop"):
            raw = _run(_mixing_mod.polish_audio("test", dry_run=True))
        result = json.loads(raw)
        assert "error" not in result
        assert result["settings"]["genre"] == "hip-hop"

    def test_explicit_genre_wins_over_derived(self, tmp_path):
        """An explicit genre argument always wins over derivation — the
        derivation helper must not even be consulted."""
        audio_dir = _setup_audio_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_helpers_mod, "_derive_album_genre") as mock_derive:
            raw = _run(_mixing_mod.polish_audio("test", genre="pop", dry_run=True))
        result = json.loads(raw)
        assert result["settings"]["genre"] == "pop"
        mock_derive.assert_not_called()

    def test_derivation_failure_keeps_no_genre_behavior(self, tmp_path):
        """When derivation can't find a genre (album missing from state,
        unexpected layout, ...), fall back to today's no-genre behavior
        instead of erroring."""
        audio_dir = _setup_audio_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_helpers_mod, "_derive_album_genre", return_value=""):
            raw = _run(_mixing_mod.polish_audio("test", dry_run=True))
        result = json.loads(raw)
        assert "error" not in result
        assert result["settings"]["genre"] is None

    def test_unknown_derived_genre_falls_back_with_warning(self, tmp_path, caplog):
        """A DERIVED genre unrecognized by the mix presets is a
        derivation failure, not a hard error (#556 fix round): an
        album's own state-recorded genre can simply predate or fall
        outside a preset's genre list, and unlike an EXPLICIT unknown
        genre (test_invalid_genre, above) there was previously no way to
        opt out of it once it's in state — genre="" just re-derives the
        same bad value. polish_audio now warns, naming the genre, and
        proceeds with today's no-genre behavior."""
        audio_dir = _setup_audio_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_helpers_mod, "_derive_album_genre", return_value="nonexistent-genre-xyz"), \
             caplog.at_level(logging.WARNING):
            raw = _run(_mixing_mod.polish_audio("test", dry_run=True))
        result = json.loads(raw)
        assert "error" not in result
        assert result["settings"]["genre"] is None
        assert any(
            "nonexistent-genre-xyz" in r.message for r in caplog.records
        ), "expected a warning naming the unrecognized derived genre"

    def test_dark_cabaret_shaped_case_state_genre_absent_from_presets(
        self, tmp_path, caplog,
    ):
        """End-to-end reproduction of the reported regression: an album
        whose state entry genuinely records a real-but-unpresetted genre
        (not a mocked return value) still polishes successfully, using
        the shipped defaults, with a warning rather than a hard failure.
        """
        audio_dir = _setup_audio_dir(tmp_path)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(
                 _shared_mod.cache, "get_state",
                 return_value={"albums": {"test": {"genre": "dark-cabaret"}}},
             ), \
             caplog.at_level(logging.WARNING):
            raw = _run(_mixing_mod.polish_audio("test", dry_run=True))
        result = json.loads(raw)
        assert "error" not in result
        assert result["settings"]["genre"] is None
        assert any("dark-cabaret" in r.message for r in caplog.records)

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

    def test_vocal_stem_does_not_false_positive_clicks(self, tmp_path):
        """Formant-shaped vocal with sibilant bursts must not emit a
        `click_removal` recommendation — vocal consonants have high
        instantaneous derivatives but their energy is spread across the
        10 ms detector window. Regression for #323 where the old
        sample-wise 6·σ(diff) detector flagged tens of thousands of
        "clicks" on every clean vocal stem.
        """
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        data, rate = make_vocal(duration=3.0)
        write_wav(str(audio_dir / "vocal.wav"), data, rate)

        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.analyze_mix_issues("test"))
        result = json.loads(raw)
        track = result["tracks"][0]
        assert track["click_count"] < 10, (
            f"vocal stem produced {track['click_count']} false-positive clicks"
        )
        assert "clicks_detected" not in track["issues"]
        assert "click_removal" not in track["recommendations"]

    @staticmethod
    def _shipped_presets_only(monkeypatch):
        """Resolve mix + mastering presets from the shipped files only.

        `_get_stem_settings` merges `{overrides}/mix-presets.yaml` and,
        through `_resolve_master_click_thresholds`, the mastering genre
        presets — both from the developer's real `~/.bitwize-music`
        config. An assertion about a shipped default has to be told to
        ignore them (#553).
        """
        import tools.mastering.master_tracks as mast
        import tools.mixing.mix_tracks as mt

        monkeypatch.setattr(mt, "_get_overrides_path", lambda: None)
        monkeypatch.setattr(mt, "MIX_PRESETS", mt.load_mix_presets())
        monkeypatch.setattr(mast, "_get_overrides_path", lambda: None)
        monkeypatch.setattr(mast, "GENRE_PRESETS", mast.load_genre_presets())

    def test_vocal_click_removal_wired_through_polish(self, tmp_path, monkeypatch):
        """Genuine clicks on a vocal stem still get removed by polish when
        click_removal is enabled for that stem (#323 comment) — the
        underlying declick mechanism is unchanged. Vocal click_removal
        now defaults to *off* (#553: a peak/RMS ratio detector can't
        distinguish a consonant from a click on a clean synthetic vocal,
        measured as 35 "clicks" removed = 35 consonants damaged), so this
        test enables it explicitly via a preset override — the same path
        a user re-enabling it for imported recorded vocals would take.
        """
        import tools.mixing.mix_tracks as mt
        from tools.mixing.mix_tracks import _deep_merge, mix_track_stems

        self._shipped_presets_only(monkeypatch)

        # Patch the loader, not the `MIX_PRESETS` snapshot: every polish
        # entry point re-reads the presets on the way in (#553), so a
        # snapshot patched here would be replaced before it was consulted.
        real_load = mt.load_mix_presets
        monkeypatch.setattr(mt, "load_mix_presets", lambda: _deep_merge(
            real_load(), {"defaults": {"vocals": {"click_removal": True}}},
        ))

        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        rate = 44100
        t = np.linspace(0, 1.0, rate, endpoint=False)
        # Quiet vocal-like background with single-sample spikes.
        mono = (0.02 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
        for i in range(10):
            mono[2000 + i * 4000] = 0.9
        data = np.column_stack([mono, mono])
        stem_path = audio_dir / "vocals.wav"
        write_wav(str(stem_path), data, rate)

        result = mix_track_stems(
            {"vocals": str(stem_path)},
            str(audio_dir / "out.wav"),
        )

        by_stem = {s["stem"]: s for s in result["stems_processed"]}
        assert by_stem["vocals"]["clicks_removed"] >= 1, (
            f"vocal declicker did not run: {by_stem['vocals']}"
        )

    def test_vocal_click_removal_off_by_default(self, tmp_path, monkeypatch):
        """#553: without an override, the same genuine clicks on a vocal
        stem are left untouched — click_removal defaults to off for
        vocals now, so `clicks_removed` should come back 0."""
        from tools.mixing.mix_tracks import mix_track_stems

        self._shipped_presets_only(monkeypatch)

        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        rate = 44100
        t = np.linspace(0, 1.0, rate, endpoint=False)
        mono = (0.02 * np.sin(2 * np.pi * 440 * t)).astype(np.float64)
        for i in range(10):
            mono[2000 + i * 4000] = 0.9
        data = np.column_stack([mono, mono])
        stem_path = audio_dir / "vocals.wav"
        write_wav(str(stem_path), data, rate)

        result = mix_track_stems(
            {"vocals": str(stem_path)},
            str(audio_dir / "out.wav"),
        )

        by_stem = {s["stem"]: s for s in result["stems_processed"]}
        assert by_stem["vocals"]["clicks_removed"] == 0

    def test_actual_clicks_still_detected(self, tmp_path):
        """Single-sample discontinuities inserted into an otherwise clean
        tone must still trigger the `click_removal` recommendation — the
        detector recalibration for #323 must not regress genuine click
        detection.
        """
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir()
        rate = 44100
        duration = 3.0
        t = np.linspace(0, duration, int(rate * duration), endpoint=False)
        mono = 0.02 * np.sin(2 * np.pi * 440 * t)
        # 30 single-sample spikes spaced ~100 ms apart — each lifts one
        # 10 ms window's peak-to-RMS ratio well above 15.
        for i in range(30):
            idx = 2000 + i * 4410
            mono[idx] = 0.9
        data = np.column_stack([mono, mono]).astype(np.float64)
        write_wav(str(audio_dir / "clicky.wav"), data, rate)

        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)):
            raw = _run(_mixing_mod.analyze_mix_issues("test"))
        result = json.loads(raw)
        track = result["tracks"][0]
        assert "clicks_detected" in track["issues"]
        assert track["recommendations"].get("click_removal") is True

    # -- genre defaulting from the album's state entry (#556) -------------

    def test_derives_genre_from_state_when_omitted(self, tmp_path):
        """analyze_mix_issues(album_slug), with no genre argument, resolves
        the album's genre from state and threads it into the analyzer core
        — the same value polish_audio would derive for the same album."""
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        captured_genres = []

        def spy_analyze_core(data, rate, *, filename, stem_name=None, genre=""):
            captured_genres.append(genre)
            return {"filename": filename, "issues": ["none_detected"], "recommendations": {}}

        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_helpers_mod, "_derive_album_genre", return_value="electronic"), \
             patch.object(_mixing_mod, "_build_analyzer", return_value=spy_analyze_core):
            raw = _run(_mixing_mod.analyze_mix_issues("test"))
        result = json.loads(raw)
        assert "error" not in result
        assert captured_genres == ["electronic"]

    def test_explicit_genre_wins_over_derived(self, tmp_path):
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        captured_genres = []

        def spy_analyze_core(data, rate, *, filename, stem_name=None, genre=""):
            captured_genres.append(genre)
            return {"filename": filename, "issues": ["none_detected"], "recommendations": {}}

        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_helpers_mod, "_derive_album_genre") as mock_derive, \
             patch.object(_mixing_mod, "_build_analyzer", return_value=spy_analyze_core):
            raw = _run(_mixing_mod.analyze_mix_issues("test", genre="pop"))
        result = json.loads(raw)
        assert "error" not in result
        assert captured_genres == ["pop"]
        mock_derive.assert_not_called()

    def test_derivation_failure_keeps_no_genre_behavior(self, tmp_path):
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_helpers_mod, "_derive_album_genre", return_value=""):
            raw = _run(_mixing_mod.analyze_mix_issues("test"))
        result = json.loads(raw)
        assert "error" not in result
        assert result["album_summary"]["tracks_analyzed"] == 1


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

    # -- genre plumbing between stage 1 (analyze) and stage 2 (polish),
    #    and defaulting genre from the album's state entry (#556) --------

    def test_stage1_and_stage2_resolve_the_same_genre(self, tmp_path):
        """Headline regression test: stage 1 (analyze_mix_issues) used to
        be called with no genre at all, so an explicit genre only reached
        stage 2 (polish) — the two stages could resolve different
        genre-scoped settings for the same run. Both must now see the
        identical genre string."""
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        import tools.mixing.mix_tracks as mt

        captured_analyze_genre = []
        real_analyze = _mixing_mod.analyze_mix_issues

        async def spy_analyze(album_slug, genre=""):
            captured_analyze_genre.append(genre)
            return await real_analyze(album_slug, genre)

        captured_polish_genre = []
        real_mix_full = mt.mix_track_full

        def spy_mix_full(*args, **kwargs):
            captured_polish_genre.append(kwargs.get("genre"))
            return real_mix_full(*args, **kwargs)

        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_mixing_mod, "analyze_mix_issues", side_effect=spy_analyze), \
             patch.object(mt, "mix_track_full", side_effect=spy_mix_full):
            raw = _run(_mixing_mod.polish_album("test", genre="hip-hop"))

        result = json.loads(raw)
        assert result["stage_reached"] == "complete"
        assert captured_analyze_genre == ["hip-hop"]
        assert captured_polish_genre and all(g == "hip-hop" for g in captured_polish_genre)

    def test_derives_genre_once_and_shares_it_across_both_stages(self, tmp_path):
        """With no genre argument, polish_album derives it once from state
        and forwards the SAME resolved value to both stages — not an
        independent re-derivation per stage, which could in principle
        disagree if state changed mid-run."""
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        import tools.mixing.mix_tracks as mt

        captured_analyze_genre = []
        real_analyze = _mixing_mod.analyze_mix_issues

        async def spy_analyze(album_slug, genre=""):
            captured_analyze_genre.append(genre)
            return await real_analyze(album_slug, genre)

        captured_polish_genre = []
        real_mix_full = mt.mix_track_full

        def spy_mix_full(*args, **kwargs):
            captured_polish_genre.append(kwargs.get("genre"))
            return real_mix_full(*args, **kwargs)

        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_helpers_mod, "_derive_album_genre", return_value="electronic") as mock_derive, \
             patch.object(_mixing_mod, "analyze_mix_issues", side_effect=spy_analyze), \
             patch.object(mt, "mix_track_full", side_effect=spy_mix_full):
            raw = _run(_mixing_mod.polish_album("test"))

        result = json.loads(raw)
        assert result["stage_reached"] == "complete"
        assert captured_analyze_genre == ["electronic"]
        assert captured_polish_genre and all(g == "electronic" for g in captured_polish_genre)
        assert mock_derive.call_count == 1

    def test_derivation_failure_keeps_no_genre_behavior(self, tmp_path):
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_helpers_mod, "_derive_album_genre", return_value=""):
            raw = _run(_mixing_mod.polish_album("test"))
        result = json.loads(raw)
        assert result["stage_reached"] == "complete"

    def test_unknown_derived_genre_falls_back_with_warning(self, tmp_path, caplog):
        """#556 fix round: a DERIVED genre unrecognized by the mix
        presets must not fail the polish stage — polish_album validates
        it BEFORE forwarding to stage 2, softens it to no-genre with a
        warning, and the pipeline completes normally. (The original fix
        hard-failed this exact case — polish_audio's own "Unknown genre"
        check can't tell a derived genre from one the caller typed once
        it's a plain non-empty argument, so polish_album must resolve
        this itself before stage 2 ever sees it.)"""
        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             patch.object(_helpers_mod, "_derive_album_genre", return_value="nonexistent-genre-xyz"), \
             caplog.at_level(logging.WARNING):
            raw = _run(_mixing_mod.polish_album("test"))
        result = json.loads(raw)
        assert result["stage_reached"] == "complete"
        assert "failed_stage" not in result
        assert any(
            "nonexistent-genre-xyz" in r.message for r in caplog.records
        ), "expected a warning naming the unrecognized derived genre"

    def test_qc_genre_unknown_to_mastering_presets_falls_back_with_warning(
        self, tmp_path, monkeypatch, caplog,
    ):
        """#556 item 3: qc_track raises ValueError for a genre absent
        from the mastering presets. A genre resolvable in MIX presets
        (so the polish stage succeeds) but absent from the separate
        MASTERING preset genre list used to crash stage 3's verify loop
        with an unhandled exception out of run_in_executor. It now warns
        and QCs genre-less instead.
        """
        from tests.unit.mixing._presets import install_override

        install_override(
            tmp_path, monkeypatch,
            "genres:\n  custom-genre:\n    full_mix: {}\n",
        )

        audio_dir = _setup_audio_dir(tmp_path, num_tracks=1)
        with patch.object(_helpers_mod, "_check_mixing_deps", return_value=None), \
             patch.object(_helpers_mod, "_resolve_audio_dir", return_value=(None, audio_dir)), \
             caplog.at_level(logging.WARNING):
            raw = _run(_mixing_mod.polish_album("test", genre="custom-genre"))
        result = json.loads(raw)
        assert result["stage_reached"] == "complete"
        assert result["stages"]["polish"]["status"] == "pass"
        assert result["stages"]["verify"]["status"] in ("pass", "warn", "fail")
        assert any(
            "custom-genre" in r.message for r in caplog.records
        ), "expected a warning naming the genre unknown to mastering presets"


# ---------------------------------------------------------------------------
# Tests: _derive_album_genre (#556)
# ---------------------------------------------------------------------------


class TestDeriveAlbumGenre:
    """Tests for handlers.processing._helpers._derive_album_genre.

    This is the state-cache lookup the polish handlers use to default
    `genre` when the caller omits it — same authoritative source
    `_resolve_audio_dir` already reads to build the album's path, not a
    re-derivation from path segments.
    """

    def test_reads_genre_from_state(self, monkeypatch):
        monkeypatch.setattr(
            _shared_mod.cache, "get_state",
            lambda: {"albums": {"my-album": {"genre": "electronic"}}},
        )
        assert _helpers_mod._derive_album_genre("my-album") == "electronic"

    def test_album_missing_from_state_returns_empty(self, monkeypatch):
        monkeypatch.setattr(_shared_mod.cache, "get_state", lambda: {"albums": {}})
        assert _helpers_mod._derive_album_genre("my-album") == ""

    def test_genre_field_missing_returns_empty(self, monkeypatch):
        monkeypatch.setattr(
            _shared_mod.cache, "get_state",
            lambda: {"albums": {"my-album": {}}},
        )
        assert _helpers_mod._derive_album_genre("my-album") == ""

    def test_empty_state_returns_empty(self, monkeypatch):
        monkeypatch.setattr(_shared_mod.cache, "get_state", lambda: {})
        assert _helpers_mod._derive_album_genre("my-album") == ""

    def test_malformed_slug_returns_empty_not_a_crash(self):
        assert _helpers_mod._derive_album_genre("bad/slug") == ""

    def test_normalizes_slug_before_lookup(self, monkeypatch):
        """State keys are normalized slugs — a raw title-like input must
        still find the entry."""
        monkeypatch.setattr(
            _shared_mod.cache, "get_state",
            lambda: {"albums": {"my-album": {"genre": "pop"}}},
        )
        assert _helpers_mod._derive_album_genre("My Album") == "pop"
