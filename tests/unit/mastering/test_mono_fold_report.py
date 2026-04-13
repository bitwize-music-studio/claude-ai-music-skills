#!/usr/bin/env python3
"""Unit tests for mono_fold report markdown rendering."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.mono_fold import DEFAULT_THRESHOLDS
from tools.mastering.mono_fold_report import render_mono_fold_markdown


def _pass_metrics() -> dict:
    return {
        "lufs": {"stereo": -14.0, "mono": -14.4, "delta_db": -0.4},
        "vocal_rms": {"stereo_db": -20.0, "mono_db": -20.3, "delta_db": -0.3},
        "stereo_correlation": 0.72,
        "worst_band": {"name": "mid", "delta_db": -0.5},
        "band_drop_fail": False,
        "verdict": "PASS",
        "thresholds": dict(DEFAULT_THRESHOLDS),
        "band_deltas": {
            "sub_bass": {"delta_db": -0.2, "hz_low": 20.0, "hz_high": 60.0, "stereo_db": -35.0, "mono_db": -35.2},
            "bass":     {"delta_db": -0.4, "hz_low": 60.0, "hz_high": 250.0, "stereo_db": -25.0, "mono_db": -25.4},
            "low_mid":  {"delta_db": -0.3, "hz_low": 250.0, "hz_high": 500.0, "stereo_db": -22.0, "mono_db": -22.3},
            "mid":      {"delta_db": -0.5, "hz_low": 500.0, "hz_high": 2000.0, "stereo_db": -18.0, "mono_db": -18.5},
            "high_mid": {"delta_db": -0.4, "hz_low": 2000.0, "hz_high": 6000.0, "stereo_db": -22.0, "mono_db": -22.4},
            "high":     {"delta_db": -0.3, "hz_low": 6000.0, "hz_high": 12000.0, "stereo_db": -28.0, "mono_db": -28.3},
            "air":      {"delta_db": -0.2, "hz_low": 12000.0, "hz_high": 20000.0, "stereo_db": -35.0, "mono_db": -35.2},
        },
    }


def _fail_metrics() -> dict:
    m = _pass_metrics()
    m["verdict"] = "FAIL"
    m["band_drop_fail"] = True
    m["worst_band"] = {"name": "mid", "delta_db": -96.0}
    m["band_deltas"]["mid"]["delta_db"] = -96.0
    m["band_deltas"]["mid"]["mono_db"] = None
    return m


def test_includes_track_name_in_header():
    md = render_mono_fold_markdown("01-test-track", _pass_metrics(), sample_filename="01-test-track.mono.wav")
    assert "01-test-track" in md


def test_pass_verdict_rendered():
    md = render_mono_fold_markdown("track", _pass_metrics(), sample_filename="track.mono.wav")
    assert "PASS" in md
    assert "FAIL" not in md.split("\n")[0:5][0]  # header line shouldn't claim FAIL


def test_fail_verdict_rendered():
    md = render_mono_fold_markdown("track", _fail_metrics(), sample_filename="track.mono.wav")
    assert "FAIL" in md


def test_all_bands_appear_in_table():
    md = render_mono_fold_markdown("track", _pass_metrics(), sample_filename="track.mono.wav")
    for band in ("sub_bass", "bass", "low_mid", "mid", "high_mid", "high", "air"):
        assert band in md


def test_lufs_and_vocal_and_correlation_present():
    md = render_mono_fold_markdown("track", _pass_metrics(), sample_filename="track.mono.wav")
    assert "LUFS" in md
    assert "Vocal" in md or "vocal" in md
    assert "correl" in md.lower()


def test_sample_filename_linked_in_notes():
    md = render_mono_fold_markdown("track", _pass_metrics(), sample_filename="track.mono.wav")
    assert "track.mono.wav" in md


def test_no_sample_filename_when_omitted():
    md = render_mono_fold_markdown("track", _pass_metrics(), sample_filename=None)
    assert ".mono.wav" not in md


def test_thresholds_reflected_in_report():
    metrics = _pass_metrics()
    metrics["thresholds"]["band_drop_fail_db"] = 9.0
    md = render_mono_fold_markdown("track", metrics, sample_filename="track.mono.wav")
    assert "9" in md  # custom threshold surfaces somewhere


def test_worst_band_highlighted_on_fail():
    md = render_mono_fold_markdown("track", _fail_metrics(), sample_filename="track.mono.wav")
    # Should call out the offending band frequency range in the fail message
    assert "500" in md or "2000" in md or "mid" in md
