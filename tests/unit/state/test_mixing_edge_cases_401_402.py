"""Edge-case regression tests for the mix analyzer (#401, #402).

Exercises `_build_analyzer().analyze_one` directly (the callable is split out
of `analyze_mix_issues` precisely so its logic can be tested without mounting
an album directory) to cover two degenerate audio buffers:

- #401: a zero-length WAV (0 samples) must not crash the analyze/polish run
  with a ValueError from reducing an empty array.
- #402: a sub-10-sample buffer must not produce a NaN noise floor (which
  serializes to the invalid JSON token ``NaN``) or emit a RuntimeWarning.
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SERVER_DIR = PROJECT_ROOT / "servers" / "bitwize-music-server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))


def _analyzer():
    from handlers.processing.mixing import _build_analyzer

    return _build_analyzer(dark_ratio=0.10, harsh_ratio=0.25)


# --------------------------------------------------------------------------
# #401 — zero-length WAV must not crash the reduction path
# --------------------------------------------------------------------------

def test_zero_length_stereo_returns_structured_error_no_exception():
    """A (0, 2) buffer returns a structured per-file error, never raises.

    Before the fix, ``np.max(np.abs(data))`` raised ``ValueError: zero-size
    array to reduction operation maximum which has no identity``.
    """
    analyze_one = _analyzer()
    data = np.zeros((0, 2), dtype=np.float64)

    result = analyze_one(data, 44100, filename="empty.wav")

    assert result["filename"] == "empty.wav"
    assert "empty_audio" in result["issues"]
    assert "error" in result
    assert "0 samples" in result["error"]
    # No metrics should have been computed from the empty array.
    assert "peak" not in result
    assert "noise_floor" not in result


def test_zero_length_mono_1d_is_guarded_before_2d_indexing():
    """A 1-D (0,) buffer is caught by the length guard before ``data[:, 0]``.

    Guards against the guard itself throwing IndexError on a 1-D empty array.
    """
    analyze_one = _analyzer()
    data = np.zeros((0,), dtype=np.float64)

    result = analyze_one(data, 44100, filename="empty-mono.wav")

    assert "empty_audio" in result["issues"]
    assert "error" in result


def test_zero_length_result_serializes_to_valid_json():
    """The empty-audio error dict round-trips through _safe_json cleanly."""
    from handlers._shared import _safe_json

    analyze_one = _analyzer()
    result = analyze_one(np.zeros((0, 2), dtype=np.float64), 44100, filename="empty.wav")

    encoded = _safe_json(result)
    assert "NaN" not in encoded
    decoded = json.loads(encoded)
    assert decoded["issues"] == ["empty_audio"]


# --------------------------------------------------------------------------
# #402 — sub-10-sample buffer must yield a clean noise floor, no NaN/warning
# --------------------------------------------------------------------------

def test_short_buffer_noise_floor_is_none_and_no_runtime_warning():
    """A 5-sample buffer yields noise_floor=None with no RuntimeWarning.

    ``len(sorted_abs) // 10 == 0`` makes the quietest-10% slice empty; before
    the fix ``np.mean([])`` returned NaN and emitted a RuntimeWarning.
    """
    analyze_one = _analyzer()
    mono = np.linspace(0.0, 0.01, 5, dtype=np.float64)
    data = np.column_stack([mono, mono])

    with warnings.catch_warnings():
        # Any RuntimeWarning (e.g. "Mean of empty slice") becomes an error.
        warnings.simplefilter("error", RuntimeWarning)
        result = analyze_one(data, 44100, filename="short.wav")

    assert result["noise_floor"] is None
    # Sentinel None means the elevated-noise guard never fires.
    assert "elevated_noise_floor" not in result["issues"]


@pytest.mark.parametrize("n_samples", [1, 5, 9])
def test_sub_10_sample_buffers_never_produce_nan_json(n_samples):
    """Buffers of 1-9 samples serialize without the invalid ``NaN`` token."""
    from handlers._shared import _safe_json

    analyze_one = _analyzer()
    mono = np.linspace(0.0, 0.02, n_samples, dtype=np.float64)
    data = np.column_stack([mono, mono])

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        result = analyze_one(data, 44100, filename=f"n{n_samples}.wav")

    assert result["noise_floor"] is None
    encoded = _safe_json(result)
    assert "NaN" not in encoded
    assert json.loads(encoded)["noise_floor"] is None


# --------------------------------------------------------------------------
# Regression guard — a normal buffer still analyzes correctly
# --------------------------------------------------------------------------

def test_normal_buffer_still_computes_finite_noise_floor():
    """A full-length signal still produces a finite noise floor and metrics."""
    analyze_one = _analyzer()
    rate = 48000
    t = np.linspace(0.0, 2.0, 2 * rate, endpoint=False)
    mono = (0.3 * np.sin(2 * np.pi * 100 * t)).astype(np.float64)
    data = np.column_stack([mono, mono])

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        result = analyze_one(data, rate, filename="normal.wav")

    assert isinstance(result["noise_floor"], float)
    assert np.isfinite(result["noise_floor"])
    assert isinstance(result["peak"], float)
    assert result["peak"] == pytest.approx(0.3, abs=1e-3)
    assert "error" not in result
    assert isinstance(result["issues"], list) and result["issues"]
