#!/usr/bin/env python3
"""Integration tests exercising QC and analysis against realistic fixtures.

These tests use the procedural audio generators in tests/fixtures/audio/ —
musically-realistic content (transients, sibilance, harmonic stacks, partial
phase shifts) that exercises code paths a pure sine wave can't trigger.

See tests/fixtures/README.md for the fixture catalog and rationale.
"""

import sys
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.qc_tracks import (
    _check_clicks,
    _check_mono_compat,
    _check_silence,
    _check_spectral,
)


def test_sibilance_triggers_tinniness_warning(bright_wav):
    """High-mid-heavy content should trip the spectral tinniness check.

    Pure sine waves at a single frequency can't exercise the high_mid/mid
    ratio path — it requires energy distributed across bands with a high-mid
    spike, which is what the bright generator synthesizes.
    """
    data, rate = sf.read(bright_wav)
    result = _check_spectral(data, rate)

    assert result["status"] == "WARN"
    assert "tinniness" in result["detail"].lower() or "high-mid" in result["detail"].lower()


def test_partial_phase_shift_fails_mono_fold(phase_partial_wav):
    """A 90-degree phase shift produces realistic (non-trivial) cancellation.

    Distinct from the make_phase_problem fixture's perfect L = -R inversion:
    here the cancellation is partial and frequency-dependent, more like
    real-world stereo widening artifacts.
    """
    data, rate = sf.read(phase_partial_wav)
    mono_result = _check_mono_compat(data)

    # Should show a measurable but non-total mono fold loss
    assert mono_result["status"] == "FAIL"
    loss_db = float(mono_result["value"].split()[0])
    assert 1.0 < loss_db < 20.0  # not a perfect cancellation


def test_clicks_and_pops_detected(clicks_and_pops_wav):
    """Injected DC pops on top of musical content should trip click QC.

    The tonal bed keeps RMS above the silent-window cutoff, so the click
    detector actually sees the spikes (a pure-silence + spike fixture would
    skip every window).
    """
    data, rate = sf.read(clicks_and_pops_wav)
    result = _check_clicks(data, rate)

    assert result["status"] == "FAIL"
    assert "0 found" not in result["value"]


def test_silent_internal_gap_fails_silence_qc(silent_gaps_wav):
    """A 1-second silent gap between audio segments triggers internal-gap FAIL.

    The silence check distinguishes leading/trailing/internal silence; only
    a multi-segment fixture exercises the internal-gap path.
    """
    data, rate = sf.read(silent_gaps_wav)
    result = _check_silence(data, rate)

    assert result["status"] == "FAIL"
    assert "internal gap" in result["detail"].lower()


def test_lufs_spread_across_dynamic_content(full_mix_wav, clipping_wav, bass_wav):
    """LUFS measurement should vary substantially across realistic content.

    A single sine wave at one amplitude can't validate that the LUFS meter
    actually distinguishes loudness across material — this asserts a wide
    spread across full-mix, clipped, and bass-only fixtures.
    """
    measurements = {}
    for name, path in [("full_mix", full_mix_wav), ("clipping", clipping_wav), ("bass", bass_wav)]:
        data, rate = sf.read(path)
        measurements[name] = pyln.Meter(rate).integrated_loudness(data)

    spread = max(measurements.values()) - min(measurements.values())
    assert spread > 10.0, f"Expected >10 LU spread, got {spread:.1f} ({measurements})"

    # Sanity: full_mix should be closest to streaming target (-14 LUFS)
    assert measurements["clipping"] > measurements["full_mix"]
    assert measurements["full_mix"] < -10  # not crushingly hot
