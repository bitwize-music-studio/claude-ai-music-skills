#!/usr/bin/env python3
"""Mono fold-down QC analysis — sum stereo to mono, measure per-band deltas.

Used to surface phase-cancellation and phantom-center issues that the full
stereo master hides but a mono playback (phone speaker, Echo, club mono sum)
exposes. See issue #296.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pyloudnorm as pyln
from scipy import signal

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

logger = logging.getLogger(__name__)


# Frequency bands — identical layout to tools/mastering/analyze_tracks.py so
# operators comparing reports aren't surprised by band boundaries.
FREQUENCY_BANDS: dict[str, tuple[float, float]] = {
    "sub_bass": (20.0, 60.0),
    "bass": (60.0, 250.0),
    "low_mid": (250.0, 500.0),
    "mid": (500.0, 2000.0),
    "high_mid": (2000.0, 6000.0),
    "high": (6000.0, 12000.0),
    "air": (12000.0, 20000.0),
}

VOCAL_BAND_HZ: tuple[float, float] = (1000.0, 4000.0)

# Bands with energy below this (relative to total) are ignored for band-drop
# checks — silence-fold artifacts shouldn't trigger a FAIL.
_BAND_MIN_PRESENT_DB = -60.0

DEFAULT_THRESHOLDS: dict[str, float] = {
    "band_drop_fail_db": 6.0,
    "lufs_warn_db": 3.0,
    "vocal_warn_db": 2.0,
    "correlation_warn": 0.3,
}


def fold_to_mono(data: np.ndarray) -> np.ndarray:
    """Downmix stereo to mono via simple mean — codebase convention.

    A 1-D input is returned unchanged.
    """
    if data.ndim == 1:
        return data
    return np.asarray(np.mean(data, axis=1))


def _ensure_stereo(data: np.ndarray) -> np.ndarray:
    if data.ndim == 1:
        return np.column_stack([data, data])
    return data


def _integrated_lufs(samples: np.ndarray, rate: int) -> float | None:
    stereo = _ensure_stereo(samples)
    meter = pyln.Meter(rate)
    try:
        lufs = meter.integrated_loudness(stereo)
    except ValueError:
        return None  # audio shorter than the analysis block — treat as unmeasurable
    return float(lufs) if np.isfinite(lufs) else None


def _band_energy_db(samples: np.ndarray, rate: int) -> dict[str, float]:
    """Return per-band energy in dB. Silent bands are -inf."""
    if np.max(np.abs(samples)) < 1e-12:
        return {name: float("-inf") for name in FREQUENCY_BANDS}
    freqs, psd = signal.welch(samples, rate, nperseg=8192)
    out: dict[str, float] = {}
    for name, (low, high) in FREQUENCY_BANDS.items():
        mask = (freqs >= low) & (freqs < high)
        energy = float(np.sum(psd[mask]))
        out[name] = 10 * np.log10(energy) if energy > 0 else float("-inf")
    return out


def _bandlimited_rms_db(samples: np.ndarray, rate: int, low_hz: float, high_hz: float) -> float:
    if np.max(np.abs(samples)) < 1e-12:
        return float("-inf")
    freqs, psd = signal.welch(samples, rate, nperseg=8192)
    mask = (freqs >= low_hz) & (freqs < high_hz)
    energy = float(np.sum(psd[mask]))
    return 10 * np.log10(energy) if energy > 0 else float("-inf")


def _average_channel_band_energy(data: np.ndarray, rate: int) -> dict[str, float]:
    """For stereo input, average per-band energy across channels (in linear domain)."""
    if data.ndim < 2:
        return _band_energy_db(data, rate)
    per_ch = [_band_energy_db(data[:, ch], rate) for ch in range(data.shape[1])]
    out: dict[str, float] = {}
    for name in FREQUENCY_BANDS:
        linear_vals = [10 ** (p[name] / 10) for p in per_ch if np.isfinite(p[name])]
        if linear_vals:
            out[name] = 10 * np.log10(float(np.mean(linear_vals)))
        else:
            out[name] = float("-inf")
    return out


def _average_channel_bandlimited_rms_db(
    data: np.ndarray, rate: int, low_hz: float, high_hz: float
) -> float:
    if data.ndim < 2:
        return _bandlimited_rms_db(data, rate, low_hz, high_hz)
    per_ch = [_bandlimited_rms_db(data[:, ch], rate, low_hz, high_hz) for ch in range(data.shape[1])]
    linear_vals = [10 ** (d / 10) for d in per_ch if np.isfinite(d)]
    if not linear_vals:
        return float("-inf")
    return float(10 * np.log10(float(np.mean(linear_vals))))


def _stereo_correlation(data: np.ndarray) -> float:
    if data.ndim < 2 or data.shape[1] < 2:
        return 1.0
    left = data[:, 0]
    right = data[:, 1]
    if np.std(left) < 1e-12 or np.std(right) < 1e-12:
        return 1.0
    corr = np.corrcoef(left, right)[0, 1]
    return float(corr) if np.isfinite(corr) else 0.0


def mono_fold_metrics(
    data: np.ndarray,
    rate: int,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Measure mono fold-down deltas.

    Args:
        data: Audio samples. Stereo (N, 2) or mono (N,).
        rate: Sample rate in Hz.
        thresholds: Optional override for DEFAULT_THRESHOLDS.

    Returns:
        Dict with mono_audio, lufs, vocal_rms, band_deltas, stereo_correlation,
        worst_band, band_drop_fail, verdict, thresholds.
    """
    active = {**DEFAULT_THRESHOLDS, **(thresholds or {})}

    mono = fold_to_mono(data)

    stereo_lufs = _integrated_lufs(data, rate)
    mono_lufs = _integrated_lufs(mono, rate)
    lufs_delta: float | None
    if stereo_lufs is not None and mono_lufs is not None:
        lufs_delta = mono_lufs - stereo_lufs
    else:
        lufs_delta = None

    stereo_vocal_db = _average_channel_bandlimited_rms_db(data, rate, *VOCAL_BAND_HZ)
    mono_vocal_db = _bandlimited_rms_db(mono, rate, *VOCAL_BAND_HZ)
    vocal_delta: float | None
    if np.isfinite(stereo_vocal_db) and np.isfinite(mono_vocal_db):
        vocal_delta = float(mono_vocal_db - stereo_vocal_db)
    else:
        vocal_delta = None

    stereo_bands = _average_channel_band_energy(data, rate)
    mono_bands = _band_energy_db(mono, rate)

    band_deltas: dict[str, dict[str, Any]] = {}
    worst: dict[str, Any] = {"name": None, "delta_db": 0.0}
    any_hard_fail = False

    # When the mono fold is silent in a band but stereo had real energy, report
    # the drop bounded to the 16-bit noise floor — below this nothing is audible,
    # and it keeps JSON/markdown finite. A caller can still suppress the fail
    # with a threshold wider than this bound.
    _CANCEL_DROP_DB = -96.0

    for name, (hz_low, hz_high) in FREQUENCY_BANDS.items():
        s = stereo_bands[name]
        m = mono_bands[name]
        stereo_present = np.isfinite(s) and s > _BAND_MIN_PRESENT_DB
        if np.isfinite(s) and np.isfinite(m):
            delta = float(m - s)
        elif stereo_present and not np.isfinite(m):
            delta = _CANCEL_DROP_DB
        else:
            delta = 0.0

        band_deltas[name] = {
            "delta_db": delta,
            "hz_low": hz_low,
            "hz_high": hz_high,
            "stereo_db": float(s) if np.isfinite(s) else None,
            "mono_db": float(m) if np.isfinite(m) else None,
        }

        if stereo_present:
            if delta < worst["delta_db"]:
                worst = {"name": name, "delta_db": delta}
            if delta < -active["band_drop_fail_db"]:
                any_hard_fail = True

    corr = _stereo_correlation(data)

    verdict = "PASS"
    if any_hard_fail:
        verdict = "FAIL"
    else:
        if lufs_delta is not None and abs(lufs_delta) > active["lufs_warn_db"]:
            verdict = "WARN"
        if vocal_delta is not None and abs(vocal_delta) > active["vocal_warn_db"]:
            verdict = "WARN"
        if corr < active["correlation_warn"]:
            verdict = "WARN"

    return {
        "mono_audio": mono,
        "lufs": {
            "stereo": stereo_lufs,
            "mono": mono_lufs,
            "delta_db": lufs_delta,
        },
        "vocal_rms": {
            "stereo_db": float(stereo_vocal_db) if np.isfinite(stereo_vocal_db) else None,
            "mono_db": float(mono_vocal_db) if np.isfinite(mono_vocal_db) else None,
            "delta_db": vocal_delta,
        },
        "band_deltas": band_deltas,
        "stereo_correlation": corr,
        "worst_band": worst,
        "band_drop_fail": any_hard_fail,
        "verdict": verdict,
        "thresholds": active,
    }
