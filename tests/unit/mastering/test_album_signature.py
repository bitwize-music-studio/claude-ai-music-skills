#!/usr/bin/env python3
"""Unit tests for album signature aggregation (#290 phase 3a)."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.mastering.album_signature import (
    build_signature,
    compute_anchor_deltas,
)


def _analysis(**overrides) -> dict:
    """Minimal analyze_track()-shaped dict for tests."""
    base = {
        "filename": "01.wav",
        "duration": 180.0,
        "sample_rate": 96000,
        "lufs": -14.0,
        "peak_db": -1.0,
        "rms_db": -20.0,
        "dynamic_range": 8.0,
        "band_energy": {
            "sub_bass": 8.0, "bass": 18.0, "low_mid": 20.0,
            "mid": 25.0, "high_mid": 14.0, "high": 10.0, "air": 5.0,
        },
        "tinniness_ratio": 0.3,
        "max_short_term_lufs": -10.0,
        "max_momentary_lufs": -8.0,
        "short_term_range": 6.5,
        "stl_95": -10.5,
        "low_rms": -18.0,
        "vocal_rms": -16.0,
        "signature_meta": {
            "stl_window_count": 60,
            "stl_top_5pct_count": 3,
            "vocal_rms_source": "band_fallback",
        },
    }
    base.update(overrides)
    return base


class TestBuildSignatureHappyPath:
    def test_three_track_album_returns_tracks_and_album_blocks(self):
        results = [
            _analysis(filename="01.wav", lufs=-14.0, stl_95=-10.0, peak_db=-1.0),
            _analysis(filename="02.wav", lufs=-13.8, stl_95=-10.2, peak_db=-1.1),
            _analysis(filename="03.wav", lufs=-14.2, stl_95=-10.4, peak_db=-0.9),
        ]
        sig = build_signature(results)

        assert sig["album"]["track_count"] == 3
        assert len(sig["tracks"]) == 3
        assert sig["tracks"][0]["index"] == 1
        assert sig["tracks"][2]["index"] == 3
        assert sig["tracks"][0]["filename"] == "01.wav"

        # Median of {-14.0, -13.8, -14.2} is -14.0
        assert sig["album"]["median"]["lufs"] == pytest.approx(-14.0)
        # Median of {-10.0, -10.2, -10.4} is -10.2
        assert sig["album"]["median"]["stl_95"] == pytest.approx(-10.2)
        # Range: max(-13.8) - min(-14.2) = 0.4
        assert sig["album"]["range"]["lufs"] == pytest.approx(0.4)


class TestBuildSignatureMissingMetrics:
    def test_none_stl_95_excluded_from_median(self):
        results = [
            _analysis(filename="01.wav", stl_95=-10.0),
            _analysis(filename="02.wav", stl_95=None),
            _analysis(filename="03.wav", stl_95=-10.4),
        ]
        sig = build_signature(results)

        # Median across {-10.0, -10.4} (two finite values) == -10.2
        assert sig["album"]["median"]["stl_95"] == pytest.approx(-10.2)
        assert sig["album"]["eligible_count"]["stl_95"] == 2

    def test_all_none_metric_returns_none_aggregate(self):
        results = [
            _analysis(vocal_rms=None),
            _analysis(vocal_rms=None),
        ]
        sig = build_signature(results)

        assert sig["album"]["median"]["vocal_rms"] is None
        assert sig["album"]["p95"]["vocal_rms"] is None
        assert sig["album"]["min"]["vocal_rms"] is None
        assert sig["album"]["max"]["vocal_rms"] is None
        assert sig["album"]["range"]["vocal_rms"] is None
        assert sig["album"]["eligible_count"]["vocal_rms"] == 0

    def test_nonfinite_lufs_excluded(self):
        results = [
            _analysis(lufs=-14.0),
            _analysis(lufs=float("-inf")),
            _analysis(lufs=float("nan")),
            _analysis(lufs=-13.8),
        ]
        sig = build_signature(results)

        # Only -14.0 and -13.8 contribute
        assert sig["album"]["median"]["lufs"] == pytest.approx(-13.9)
        assert sig["album"]["range"]["lufs"] == pytest.approx(0.2)


class TestBuildSignatureBoundaryCases:
    def test_empty_album_returns_empty_tracks_and_none_aggregates(self):
        sig = build_signature([])

        assert sig["tracks"] == []
        assert sig["album"]["track_count"] == 0
        for key in ("lufs", "stl_95", "low_rms", "vocal_rms"):
            assert sig["album"]["median"][key] is None
            assert sig["album"]["range"][key] is None

    def test_single_track_range_is_zero(self):
        results = [_analysis(lufs=-14.0, stl_95=-10.0)]
        sig = build_signature(results)

        assert sig["album"]["median"]["lufs"] == pytest.approx(-14.0)
        assert sig["album"]["range"]["lufs"] == pytest.approx(0.0)

    def test_p95_with_odd_count_uses_interpolation(self):
        results = [_analysis(lufs=v) for v in (-15.0, -14.5, -14.0, -13.5, -13.0)]
        sig = build_signature(results)

        # numpy.percentile(..., 95) with linear interpolation on this
        # 5-value set returns -13.1 (between -13.5 and -13.0).
        assert sig["album"]["p95"]["lufs"] == pytest.approx(-13.1, abs=1e-6)


class TestComputeAnchorDeltas:
    def test_deltas_are_track_minus_anchor(self):
        results = [
            _analysis(filename="01.wav", lufs=-13.0, stl_95=-10.0),
            _analysis(filename="02.wav", lufs=-14.0, stl_95=-10.5),  # anchor
            _analysis(filename="03.wav", lufs=-15.0, stl_95=-11.5),
        ]
        deltas = compute_anchor_deltas(results, anchor_index_1based=2)

        # Track 1 - Anchor: -13.0 - -14.0 = +1.0
        assert deltas[0]["delta_lufs"] == pytest.approx(1.0)
        assert deltas[0]["delta_stl_95"] == pytest.approx(0.5)
        assert deltas[0]["is_anchor"] is False

        # Track 2 (anchor) - itself = 0.0
        assert deltas[1]["delta_lufs"] == pytest.approx(0.0)
        assert deltas[1]["is_anchor"] is True

        # Track 3 - Anchor: -15.0 - -14.0 = -1.0
        assert deltas[2]["delta_lufs"] == pytest.approx(-1.0)
        assert deltas[2]["delta_stl_95"] == pytest.approx(-1.0)
        assert deltas[2]["is_anchor"] is False

    def test_none_in_track_or_anchor_yields_none_delta(self):
        results = [
            _analysis(filename="01.wav", vocal_rms=None),  # track missing
            _analysis(filename="02.wav", vocal_rms=-16.0),  # anchor present
            _analysis(filename="03.wav", vocal_rms=-15.0),
        ]
        deltas = compute_anchor_deltas(results, anchor_index_1based=2)

        assert deltas[0]["delta_vocal_rms"] is None
        assert deltas[1]["delta_vocal_rms"] == pytest.approx(0.0)
        assert deltas[2]["delta_vocal_rms"] == pytest.approx(1.0)

    def test_none_in_anchor_propagates_to_every_row(self):
        results = [
            _analysis(filename="01.wav", low_rms=-18.0),
            _analysis(filename="02.wav", low_rms=None),    # anchor missing
        ]
        deltas = compute_anchor_deltas(results, anchor_index_1based=2)

        assert deltas[0]["delta_low_rms"] is None
        assert deltas[1]["delta_low_rms"] is None
        # Anchor row is still marked, just without a delta value
        assert deltas[1]["is_anchor"] is True

    def test_empty_results_raises(self):
        with pytest.raises(ValueError, match="empty"):
            compute_anchor_deltas([], anchor_index_1based=1)

    def test_out_of_range_anchor_raises(self):
        results = [_analysis(filename="01.wav"), _analysis(filename="02.wav")]
        with pytest.raises(ValueError, match="out of range"):
            compute_anchor_deltas(results, anchor_index_1based=3)
        with pytest.raises(ValueError, match="out of range"):
            compute_anchor_deltas(results, anchor_index_1based=0)
        with pytest.raises(ValueError, match="out of range"):
            compute_anchor_deltas(results, anchor_index_1based=-1)

    def test_all_aggregate_keys_are_represented(self):
        results = [
            _analysis(filename="01.wav"),
            _analysis(filename="02.wav"),
        ]
        deltas = compute_anchor_deltas(results, anchor_index_1based=1)
        expected_keys = {
            "index", "filename", "is_anchor",
            "delta_lufs", "delta_peak_db", "delta_stl_95",
            "delta_short_term_range", "delta_low_rms", "delta_vocal_rms",
        }
        assert set(deltas[0].keys()) == expected_keys


def test_build_signature_embeds_delivery_targets_when_provided() -> None:
    from tools.mastering.album_signature import build_signature
    analysis = [
        {"filename": "01.wav", "lufs": -14.0, "peak_db": -3.0, "stl_95": -14.2,
         "short_term_range": 8.0, "low_rms": -22.0, "vocal_rms": -17.5,
         "band_energy": {"mid": 25.0}, "duration": 120.0, "sample_rate": 96000},
        {"filename": "02.wav", "lufs": -14.1, "peak_db": -3.1, "stl_95": -14.3,
         "short_term_range": 8.1, "low_rms": -22.1, "vocal_rms": -17.6,
         "band_energy": {"mid": 25.1}, "duration": 125.0, "sample_rate": 96000},
    ]
    sig = build_signature(
        analysis,
        delivery_targets={
            "target_lufs": -14.0,
            "tp_ceiling_db": -1.0,
            "lra_target_lu": 8.0,
            "output_bits": 24,
            "output_sample_rate": 96000,
        },
        tolerances={
            "coherence_stl_95_lu": 1.0,
            "coherence_lra_floor_lu": 6.0,
            "coherence_low_rms_db": 2.0,
            "coherence_vocal_rms_db": 1.5,
        },
    )
    assert sig["album"]["delivery_targets"]["target_lufs"] == -14.0
    assert sig["album"]["delivery_targets"]["tp_ceiling_db"] == -1.0
    assert sig["album"]["delivery_targets"]["lra_target_lu"] == 8.0
    assert sig["album"]["tolerances"]["coherence_stl_95_lu"] == 1.0


def test_build_signature_omits_delivery_block_when_args_absent() -> None:
    """Backward compat: existing callers that don't pass targets keep working."""
    from tools.mastering.album_signature import build_signature
    analysis = [
        {"filename": "01.wav", "lufs": -14.0, "peak_db": -3.0, "stl_95": -14.2,
         "short_term_range": 8.0, "low_rms": -22.0, "vocal_rms": -17.5,
         "band_energy": {"mid": 25.0}, "duration": 120.0, "sample_rate": 96000},
    ]
    sig = build_signature(analysis)
    assert "delivery_targets" not in sig["album"]
    assert "tolerances" not in sig["album"]
