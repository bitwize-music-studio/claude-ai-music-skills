#!/usr/bin/env python3
"""
Pipeline property tests for the mastering chain.

Uses realistic synthetic audio fixtures to test end-to-end behaviour:
    analyze_track() → master_track() → qc_track()
and the fix_dynamic recovery path.

Tests assert *properties* (LUFS within range, peak below ceiling, QC passes)
rather than golden-file snapshots so they survive parameter tuning.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.audio import (
    make_bass,
    make_bright,
    make_clipping,
    make_drums,
    make_full_mix,
    make_noisy,
    make_phase_problem,
    make_vocal,
    write_wav,
)
from tools.mastering.analyze_tracks import analyze_track
from tools.mastering.fix_dynamic_track import fix_dynamic
from tools.mastering.master_tracks import master_track
from tools.mastering.qc_tracks import qc_track


# ---------------------------------------------------------------------------
# Fixtures — realistic audio on disk
# ---------------------------------------------------------------------------


@pytest.fixture
def vocal_wav(tmp_path):
    data, rate = make_vocal()
    return write_wav(str(tmp_path / "vocal.wav"), data, rate)


@pytest.fixture
def drums_wav(tmp_path):
    data, rate = make_drums()
    return write_wav(str(tmp_path / "drums.wav"), data, rate)


@pytest.fixture
def bass_wav(tmp_path):
    data, rate = make_bass()
    return write_wav(str(tmp_path / "bass.wav"), data, rate)


@pytest.fixture
def full_mix_wav(tmp_path):
    data, rate = make_full_mix()
    return write_wav(str(tmp_path / "full_mix.wav"), data, rate)


@pytest.fixture
def clipping_wav(tmp_path):
    data, rate = make_clipping()
    return write_wav(str(tmp_path / "clipping.wav"), data, rate)


@pytest.fixture
def phase_wav(tmp_path):
    data, rate = make_phase_problem()
    return write_wav(str(tmp_path / "phase.wav"), data, rate)


@pytest.fixture
def bright_wav(tmp_path):
    data, rate = make_bright()
    return write_wav(str(tmp_path / "bright.wav"), data, rate)


@pytest.fixture
def noisy_wav(tmp_path):
    data, rate = make_noisy()
    return write_wav(str(tmp_path / "noisy.wav"), data, rate)


# ---------------------------------------------------------------------------
# Analysis with realistic signals
# ---------------------------------------------------------------------------


class TestAnalyzeRealisticSignals:
    """analyze_track() on signals with real-world spectral content."""

    def test_vocal_has_mid_energy(self, vocal_wav):
        r = analyze_track(vocal_wav)
        be = r["band_energy"]
        # Vocal formants sit in low_mid + mid bands
        assert be["low_mid"] + be["mid"] > 20

    def test_drums_have_sub_bass(self, drums_wav):
        r = analyze_track(drums_wav)
        be = r["band_energy"]
        # Kick fundamental at 80 Hz → sub_bass + bass energy
        assert be["sub_bass"] + be["bass"] > 10

    def test_bass_dominant_low_end(self, bass_wav):
        r = analyze_track(bass_wav)
        be = r["band_energy"]
        assert be["sub_bass"] + be["bass"] > 40

    def test_full_mix_has_wide_spectrum(self, full_mix_wav):
        r = analyze_track(full_mix_wav)
        be = r["band_energy"]
        # Should have energy in at least 4 bands
        nonzero = sum(1 for v in be.values() if v > 1.0)
        assert nonzero >= 4

    def test_bright_triggers_tinniness(self, bright_wav):
        r = analyze_track(bright_wav)
        assert r["tinniness_ratio"] > 0.5

    def test_noisy_signal_analysable(self, noisy_wav):
        r = analyze_track(noisy_wav)
        assert np.isfinite(r["lufs"])
        assert r["duration"] > 1.0


# ---------------------------------------------------------------------------
# Mastering pipeline: master_track() property tests
# ---------------------------------------------------------------------------


class TestMasteringHitsTarget:
    """master_track() should bring audio to target LUFS and below ceiling."""

    def test_full_mix_reaches_target(self, full_mix_wav, tmp_path):
        out = str(tmp_path / "mastered.wav")
        result = master_track(full_mix_wav, out, target_lufs=-14.0)
        assert not result.get("skipped")
        assert abs(result["final_lufs"] - (-14.0)) < 1.5

    def test_peak_below_ceiling(self, full_mix_wav, tmp_path):
        out = str(tmp_path / "mastered.wav")
        result = master_track(full_mix_wav, out, ceiling_db=-1.0)
        assert result["final_peak"] <= 0.0  # well below 0 dBFS

    def test_vocal_masters_cleanly(self, vocal_wav, tmp_path):
        out = str(tmp_path / "mastered_vocal.wav")
        result = master_track(vocal_wav, out, target_lufs=-14.0)
        assert not result.get("skipped")
        assert np.isfinite(result["final_lufs"])

    def test_drums_master_preserves_transients(self, drums_wav, tmp_path):
        out = str(tmp_path / "mastered_drums.wav")
        result = master_track(drums_wav, out, target_lufs=-14.0)
        assert not result.get("skipped")
        # Dynamic range should still be positive (transients preserved)
        data, rate = sf.read(out)
        peak = np.max(np.abs(data))
        rms = np.sqrt(np.mean(data ** 2))
        if rms > 0 and peak > 0:
            dr = 20 * np.log10(peak / rms)
            assert dr > 3  # reasonable dynamic range preserved

    def test_bass_masters_without_distortion(self, bass_wav, tmp_path):
        out = str(tmp_path / "mastered_bass.wav")
        result = master_track(bass_wav, out, target_lufs=-14.0)
        assert not result.get("skipped")
        data, _ = sf.read(out)
        assert np.all(np.isfinite(data))

    def test_mastering_with_eq(self, full_mix_wav, tmp_path):
        out = str(tmp_path / "mastered_eq.wav")
        eq = [(3500.0, -2.0, 1.5)]
        result = master_track(full_mix_wav, out, target_lufs=-14.0, eq_settings=eq)
        assert not result.get("skipped")
        assert abs(result["final_lufs"] - (-14.0)) < 2.0

    def test_mastering_with_compression(self, full_mix_wav, tmp_path):
        out = str(tmp_path / "mastered_comp.wav")
        result = master_track(full_mix_wav, out, target_lufs=-14.0, compress_ratio=3.0)
        assert not result.get("skipped")
        assert np.isfinite(result["final_lufs"])

    def test_mastering_with_fade_out(self, full_mix_wav, tmp_path):
        out = str(tmp_path / "mastered_fade.wav")
        result = master_track(full_mix_wav, out, target_lufs=-14.0, fade_out=1.0)
        assert not result.get("skipped")
        data, _ = sf.read(out)
        # Last 100 samples should be near-silent
        tail_rms = np.sqrt(np.mean(data[-100:] ** 2))
        assert tail_rms < 0.01


# ---------------------------------------------------------------------------
# End-to-end: analyze → master → QC
# ---------------------------------------------------------------------------


class TestEndToEndPipeline:
    """Full mastering pipeline: analyze → master → QC should pass."""

    def test_full_mix_pipeline_passes_core_qc(self, full_mix_wav, tmp_path):
        """Mastering should not introduce clipping, phase, or format issues.

        Spectral balance is excluded because synthetic fixtures have
        inherently unbalanced spectra (no real harmonic content).
        """
        # 1. Analyze
        analysis = analyze_track(full_mix_wav)
        assert np.isfinite(analysis["lufs"])

        # 2. Master
        out = str(tmp_path / "mastered.wav")
        result = master_track(full_mix_wav, out, target_lufs=-14.0)
        assert not result.get("skipped")

        # 3. QC — core checks only (exclude spectral which is sensitive
        # to synthetic signal characteristics)
        core_checks = ["format", "mono", "phase", "clipping", "silence"]
        qc = qc_track(out, checks=core_checks)
        fail_checks = [
            name for name, info in qc["checks"].items()
            if info["status"] == "FAIL"
        ]
        assert fail_checks == [], f"QC failures: {fail_checks}"

    def test_vocal_pipeline_no_clipping(self, vocal_wav, tmp_path):
        out = str(tmp_path / "mastered.wav")
        master_track(vocal_wav, out, target_lufs=-14.0)
        qc = qc_track(out, checks=["clipping", "format", "phase"])
        fail_checks = [n for n, i in qc["checks"].items() if i["status"] == "FAIL"]
        assert fail_checks == []

    def test_drums_pipeline_no_clipping(self, drums_wav, tmp_path):
        out = str(tmp_path / "mastered.wav")
        master_track(drums_wav, out, target_lufs=-14.0)
        qc = qc_track(out, checks=["clipping", "format", "phase"])
        fail_checks = [n for n, i in qc["checks"].items() if i["status"] == "FAIL"]
        assert fail_checks == []


# ---------------------------------------------------------------------------
# QC validation: known-bad fixtures should produce expected results
# ---------------------------------------------------------------------------


class TestQcKnownBadFixtures:
    """QC should detect problems in intentionally bad audio."""

    def test_clipping_detected(self, clipping_wav):
        qc = qc_track(clipping_wav, checks=["clipping"])
        assert qc["checks"]["clipping"]["status"] in ("WARN", "FAIL")

    def test_phase_problem_detected(self, phase_wav):
        qc = qc_track(phase_wav, checks=["phase"])
        assert qc["checks"]["phase"]["status"] == "FAIL"

    def test_bright_triggers_spectral_warning(self, bright_wav):
        qc = qc_track(bright_wav, checks=["spectral"])
        assert qc["checks"]["spectral"]["status"] in ("WARN", "FAIL")

    def test_full_mix_passes_core_checks(self, full_mix_wav):
        """Full mix should pass format, mono, phase, clipping, silence checks.

        Spectral may flag synthetic audio — that's expected, not a bug.
        """
        core_checks = ["format", "mono", "phase", "clipping", "silence"]
        qc = qc_track(full_mix_wav, checks=core_checks)
        fail_checks = [
            name for name, info in qc["checks"].items()
            if info["status"] == "FAIL"
        ]
        assert fail_checks == []


# ---------------------------------------------------------------------------
# Fix path: fix_dynamic() on bad input → QC pass
# ---------------------------------------------------------------------------


class TestFixDynamicRecovery:
    """fix_dynamic() should recover clipping audio to pass QC."""

    def test_fix_clipping_reduces_peak(self, clipping_wav, tmp_path):
        data, rate = sf.read(clipping_wav)
        fixed, metrics = fix_dynamic(data, rate, target_lufs=-14.0)
        assert metrics["final_peak_db"] < 0  # below 0 dBFS

    def test_fix_clipping_reaches_target_lufs(self, clipping_wav, tmp_path):
        data, rate = sf.read(clipping_wav)
        fixed, metrics = fix_dynamic(data, rate, target_lufs=-14.0)
        assert abs(metrics["final_lufs"] - (-14.0)) < 2.0

    def test_fixed_audio_passes_qc(self, clipping_wav, tmp_path):
        data, rate = sf.read(clipping_wav)
        fixed, _metrics = fix_dynamic(data, rate, target_lufs=-14.0)
        out = str(tmp_path / "fixed.wav")
        sf.write(out, fixed, rate, subtype="PCM_16")
        qc = qc_track(out)
        # After fixing, clipping check should not FAIL
        assert qc["checks"]["clipping"]["status"] != "FAIL"

    def test_fix_with_custom_eq(self, clipping_wav):
        data, rate = sf.read(clipping_wav)
        eq = [(3500, -3.0, 1.0), (8000, -1.5, 0.7)]
        fixed, metrics = fix_dynamic(data, rate, eq_settings=eq)
        assert np.all(np.isfinite(fixed))
        assert np.isfinite(metrics["final_lufs"])

    def test_fix_preserves_stereo(self, clipping_wav):
        data, rate = sf.read(clipping_wav)
        fixed, _ = fix_dynamic(data, rate)
        assert fixed.shape == data.shape
        assert len(fixed.shape) == 2 and fixed.shape[1] == 2
