"""Tests for tools/mastering/ceiling_guard.py (#290 phase 5, step 8)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.ceiling_guard import (  # noqa: E402
    CeilingGuardError,
    apply_pull_down_db,
    compute_overshoots,
)


def test_compute_overshoots_empty_returns_empty() -> None:
    assert compute_overshoots([]) == {
        "median_lufs": None,
        "threshold_lu": None,
        "tracks": [],
    }


def test_compute_overshoots_all_within_spec() -> None:
    tracks = [
        {"filename": "01.wav", "lufs": -14.0},
        {"filename": "02.wav", "lufs": -14.5},
        {"filename": "03.wav", "lufs": -13.5},
    ]
    result = compute_overshoots(tracks)
    assert result["median_lufs"] == -14.0
    assert result["threshold_lu"] == -12.0
    assert len(result["tracks"]) == 3
    for row in result["tracks"]:
        assert row["overshoot_lu"] <= 0.0
        assert row["classification"] == "in_spec"


def test_compute_overshoots_small_overshoot_flags_correctable() -> None:
    # Sorted middle two values are -14.0 and -13.8, so true median = -13.9,
    # threshold = -11.9. Track 4 at -11.7 → overshoot 0.2 LU (correctable).
    tracks = [
        {"filename": "01.wav", "lufs": -14.0},
        {"filename": "02.wav", "lufs": -14.2},
        {"filename": "03.wav", "lufs": -13.8},
        {"filename": "04.wav", "lufs": -11.7},
    ]
    result = compute_overshoots(tracks)
    assert result["median_lufs"] == pytest.approx(-13.9, abs=1e-9)
    assert result["threshold_lu"] == pytest.approx(-11.9, abs=1e-9)
    row4 = result["tracks"][3]
    assert row4["filename"] == "04.wav"
    assert row4["overshoot_lu"] == pytest.approx(0.2, abs=1e-9)
    assert row4["classification"] == "correctable"
    assert row4["pull_down_db"] == pytest.approx(-0.2, abs=1e-9)


def test_compute_overshoots_large_overshoot_flags_halt() -> None:
    # True median of [-14.2, -14.0, -13.8, -11.0] = -13.9, threshold = -11.9.
    # Track 4 at -11.0 → overshoot 0.9 LU > 0.5 → halt.
    tracks = [
        {"filename": "01.wav", "lufs": -14.0},
        {"filename": "02.wav", "lufs": -14.2},
        {"filename": "03.wav", "lufs": -13.8},
        {"filename": "04.wav", "lufs": -11.0},
    ]
    result = compute_overshoots(tracks)
    row4 = result["tracks"][3]
    assert row4["classification"] == "halt"
    assert row4["overshoot_lu"] == pytest.approx(0.9, abs=1e-9)
    assert row4["pull_down_db"] is None


def test_compute_overshoots_boundary_exactly_half_lu_is_correctable() -> None:
    # Exactly 0.5 LU overshoot is correctable (inclusive bound per spec).
    tracks = [
        {"filename": "01.wav", "lufs": -14.0},
        {"filename": "02.wav", "lufs": -14.0},
        {"filename": "03.wav", "lufs": -11.5},
    ]
    result = compute_overshoots(tracks)
    row3 = result["tracks"][2]
    assert row3["classification"] == "correctable"
    assert row3["overshoot_lu"] == pytest.approx(0.5, abs=1e-9)


def test_compute_overshoots_odd_count_uses_true_median() -> None:
    # 5 tracks, sorted LUFS: -15, -14.5, -14, -13.5, -13 → median -14
    tracks = [
        {"filename": "01.wav", "lufs": -15.0},
        {"filename": "02.wav", "lufs": -14.5},
        {"filename": "03.wav", "lufs": -14.0},
        {"filename": "04.wav", "lufs": -13.5},
        {"filename": "05.wav", "lufs": -13.0},
    ]
    result = compute_overshoots(tracks)
    assert result["median_lufs"] == pytest.approx(-14.0, abs=1e-9)
    assert result["threshold_lu"] == pytest.approx(-12.0, abs=1e-9)


def test_compute_overshoots_preserves_input_order() -> None:
    # Unsorted input; output must match input order by filename.
    tracks = [
        {"filename": "03.wav", "lufs": -13.5},
        {"filename": "01.wav", "lufs": -14.0},
        {"filename": "02.wav", "lufs": -14.5},
    ]
    result = compute_overshoots(tracks)
    assert [r["filename"] for r in result["tracks"]] == ["03.wav", "01.wav", "02.wav"]


def test_apply_pull_down_db_applies_scalar_gain(tmp_path: Path) -> None:
    path = tmp_path / "track.wav"
    rate = 44100
    samples = np.full((rate, 2), 0.5, dtype=np.float32)
    sf.write(str(path), samples, rate, subtype="PCM_24")

    apply_pull_down_db(path, gain_db=-6.0, output_bits=24)

    read_back, rb_rate = sf.read(str(path))
    assert rb_rate == rate
    expected = 0.5 * (10 ** (-6.0 / 20.0))
    np.testing.assert_allclose(read_back, expected, atol=1e-3)


def test_apply_pull_down_db_rejects_positive_gain(tmp_path: Path) -> None:
    path = tmp_path / "track.wav"
    sf.write(str(path), np.zeros((44100, 2), dtype=np.float32), 44100, subtype="PCM_24")
    with pytest.raises(CeilingGuardError, match="must be <= 0"):
        apply_pull_down_db(path, gain_db=0.5, output_bits=24)


def test_apply_pull_down_db_zero_gain_is_noop(tmp_path: Path) -> None:
    # Zero gain is legal (edge case: classified correctable with 0.0 overshoot).
    path = tmp_path / "track.wav"
    rate = 44100
    samples = np.full((rate, 2), 0.25, dtype=np.float32)
    sf.write(str(path), samples, rate, subtype="PCM_24")

    apply_pull_down_db(path, gain_db=0.0, output_bits=24)

    read_back, _ = sf.read(str(path))
    np.testing.assert_allclose(read_back, 0.25, atol=1e-3)


def test_apply_pull_down_db_honors_16bit_output(tmp_path: Path) -> None:
    path = tmp_path / "track.wav"
    rate = 44100
    samples = np.full((rate, 2), 0.5, dtype=np.float32)
    sf.write(str(path), samples, rate, subtype="PCM_24")

    apply_pull_down_db(path, gain_db=-3.0, output_bits=16)

    info = sf.info(str(path))
    assert info.subtype == "PCM_16"


def test_apply_pull_down_db_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(CeilingGuardError, match="not found"):
        apply_pull_down_db(tmp_path / "no-such.wav", gain_db=-0.3, output_bits=24)
