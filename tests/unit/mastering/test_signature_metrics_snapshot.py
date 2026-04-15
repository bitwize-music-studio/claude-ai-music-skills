"""Snapshot tests: STL-95, low-RMS, short_term_range on standard fixtures (regression catch, #290).

These tests assert that the signature metrics produced by analyze_track()
on a known synthetic fixture stay within expected ranges. If a refactor
accidentally breaks STL-95 computation, these tests catch it before CI merges.

Ranges are intentionally wide (±3 dB or ±2 LU) to survive minor algorithm
tuning while still catching complete breakage.

Note: analyze_track() returns ``short_term_range`` (max_short_term_lufs -
min_short_term_lufs) rather than a standalone ``lra`` key; the test below
validates that field accordingly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tests.fixtures.audio import make_full_mix, write_wav  # noqa: E402
from tools.mastering.analyze_tracks import analyze_track  # noqa: E402


@pytest.fixture(scope="module")
def full_mix_wav(tmp_path_factory: pytest.TempPathFactory) -> str:
    tmp = tmp_path_factory.mktemp("snapshots")
    # STL-95 requires >= 20 short-term windows (3s window / 1s hop → ~23s minimum).
    # Use 25s to comfortably satisfy the gate.
    data, rate = make_full_mix(duration=25.0)
    return write_wav(str(tmp / "full_mix.wav"), data, rate)


def test_stl_95_is_finite_and_negative(full_mix_wav: str) -> None:
    """STL-95 must be a finite negative float (loudest 5% of short-term windows)."""
    result = analyze_track(full_mix_wav)
    stl_95 = result.get("stl_95")
    assert stl_95 is not None, "analyze_track must return stl_95 key"
    assert isinstance(stl_95, float)
    assert stl_95 < 0.0, f"STL-95 should be negative, got {stl_95}"
    assert stl_95 > -60.0, f"STL-95 unexpectedly quiet: {stl_95}"


def test_low_rms_is_finite(full_mix_wav: str) -> None:
    """low_rms (20–200 Hz band, STL-95 windowed) is a finite float."""
    result = analyze_track(full_mix_wav)
    low_rms = result.get("low_rms")
    assert low_rms is not None, "analyze_track must return low_rms key"
    assert isinstance(low_rms, float)
    assert low_rms < 0.0, f"low_rms should be negative dB, got {low_rms}"


def test_short_term_range_is_non_negative(full_mix_wav: str) -> None:
    """short_term_range (loudness range) is >= 0 LU."""
    result = analyze_track(full_mix_wav)
    short_term_range = result.get("short_term_range")
    assert short_term_range is not None, "analyze_track must return short_term_range key"
    assert isinstance(short_term_range, (int, float))
    assert short_term_range >= 0.0, f"short_term_range must be non-negative, got {short_term_range}"


def test_stl_95_within_4_lu_of_lufs(full_mix_wav: str) -> None:
    """STL-95 should be close to integrated LUFS (within ~4 LU for steady signals)."""
    result = analyze_track(full_mix_wav)
    stl_95 = result["stl_95"]
    lufs = result["lufs"]
    delta = abs(stl_95 - lufs)
    assert delta < 4.0, (
        f"STL-95 ({stl_95:.1f}) and LUFS ({lufs:.1f}) diverged by {delta:.1f} LU — "
        f"STL-95 computation may be broken."
    )


def test_peak_db_is_finite(full_mix_wav: str) -> None:
    """peak_db is a finite float in a plausible range for the test fixture."""
    result = analyze_track(full_mix_wav)
    peak_db = result.get("peak_db")
    assert peak_db is not None
    assert isinstance(peak_db, float)
    assert -60.0 < peak_db < 0.0, f"peak_db out of expected range: {peak_db}"
